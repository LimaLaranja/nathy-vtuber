import asyncio
import json
import os
import logging
from typing import Any, Dict, Optional, List

import httpx
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from memory import MemoryStore
from stt import SpeechToText, get_stt
from tts import TTSEngine, get_tts
from websocket_handler import VTuberWebSocketHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # Configurações da Aplicação
    environment: str = os.environ.get("ENVIRONMENT", "development")
    debug: bool = os.environ.get("DEBUG", "false").lower() == "true"
    host: str = os.environ.get("HOST", "0.0.0.0")
    port: int = int(os.environ.get("PORT", 8000))
    secret_key: str = os.environ.get("SECRET_KEY", "nathy-secret-key")
    
    # LLM Configuration
    llm_provider: str = os.environ.get("LLM_PROVIDER", "ollama")  # "ollama" ou "openai"
    ollama_host: str = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    ollama_model: str = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
    openai_model: str = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
    
    # Database
    memory_db_path: str = os.environ.get("MEMORY_DB_PATH", os.path.join(os.path.dirname(__file__), "memory.sqlite3"))
    
    # Nathy Configuration
    system_prompt: str = os.environ.get(
        "SYSTEM_PROMPT",
        "Você é a Nathy, uma VTuber 3D estilo chibi brasileira com personalidade única. "
        "Características: fofa, divertida, curiosa, inteligente, com humor sarcástico leve. "
        "Adora tecnologia, jogos e memes brasileiros. Fale em pt-BR natural. "
        "Use expressões como 'Ué!', 'Nossa!', 'Legal!' ocasionalmente. "
        "Seja autêntica e mostre sua personalidade vibrante. "
        "Faça perguntas quando quiser saber mais sobre o usuário."
    )

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup components."""
    logger.info("Starting VTuber 3D Offline backend...")
    
    # Check if Ollama is running
    ollama_ok = await check_ollama_connection()
    if not ollama_ok:
        logger.warning(
            "Ollama server not found. Please make sure Ollama is running and accessible at "
            f"{settings.ollama_host}"
        )
    
    logger.info("Backend ready!")
    yield

# Initialize FastAPI app
app = FastAPI(
    title="VTuber 3D Offline",
    description="Backend for offline 3D VTuber with voice interaction",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
memory = MemoryStore(settings.memory_db_path)
stt_engine = get_stt()
tts_engine = get_tts()
ws_handler = VTuberWebSocketHandler(stt_engine, tts_engine, memory, settings.ollama_host, settings.ollama_model, settings.system_prompt, settings.llm_provider)

# Mount static files (for the web interface if needed)
app.mount("/static", StaticFiles(directory="static"), name="static")


class ChatRequest(BaseModel):
    user_id: str = "default"
    text: str

class SystemPromptUpdate(BaseModel):
    prompt: str

class VoiceSettings(BaseModel):
    speed: Optional[float] = None
    pitch: Optional[float] = None
    volume: Optional[float] = None


from llm_utils import ollama_chat, build_messages, maybe_extract_fact
from openai_utils import openai_chat


@app.get("/ping")
async def ping():
    """Health check endpoint para manter awake no Render."""
    return {"status": "awake", "service": "nathy-vtuber"}

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main HTML page."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>VTuber 3D Offline</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                text-align: center;
            }
            .container {
                margin-top: 50px;
            }
            .status {
                margin: 20px 0;
                padding: 10px;
                border-radius: 5px;
            }
            .listening {
                background-color: #d4edda;
                color: #155724;
            }
            .idle {
                background-color: #f8f9fa;
                color: #6c757d;
            }
            button {
                padding: 10px 20px;
                font-size: 16px;
                margin: 10px;
                cursor: pointer;
            }
            #transcript {
                margin: 20px 0;
                padding: 15px;
                border: 1px solid #ddd;
                min-height: 100px;
                text-align: left;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>VTuber 3D Offline</h1>
            <div id="status" class="status idle">Status: Desconectado</div>
            <div>
                <button id="connectBtn">Conectar</button>
                <button id="listenBtn" disabled>Ouvir</button>
                <button id="stopBtn" disabled>Parar</button>
            </div>
            <div id="transcript"></div>
            <div id="response"></div>
        </div>
        <script>
            let ws;
            const connectBtn = document.getElementById('connectBtn');
            const listenBtn = document.getElementById('listenBtn');
            const stopBtn = document.getElementById('stopBtn');
            const statusDiv = document.getElementById('status');
            const transcriptDiv = document.getElementById('transcript');
            const responseDiv = document.getElementById('response');
            
            function updateStatus(text, isListening = false) {
                statusDiv.textContent = `Status: ${text}`;
                statusDiv.className = `status ${isListening ? 'listening' : 'idle'}`;
            }
            
            function appendToTranscript(text, isUser = true) {
                const p = document.createElement('p');
                p.textContent = text;
                p.style.color = isUser ? 'blue' : 'green';
                p.style.margin = '5px 0';
                p.style.padding = '5px';
                p.style.borderLeft = `4px solid ${isUser ? 'blue' : 'green'}`;
                transcriptDiv.appendChild(p);
                transcriptDiv.scrollTop = transcriptDiv.scrollHeight;
            }
            
            function connectWebSocket() {
                const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
                
                console.log('Tentando conectar WebSocket:', wsUrl);
                
                ws = new WebSocket(wsUrl);
                
                ws.onopen = () => {
                    console.log('WebSocket conectado!');
                    updateStatus('Conectado');
                    connectBtn.disabled = true;
                    listenBtn.disabled = false;
                    stopBtn.disabled = false;
                    
                    // Send initial hello message with user ID
                    ws.send(JSON.stringify({
                        type: 'hello',
                        user_id: 'user_1'
                    }));
                };
                
                ws.onmessage = (event) => {
                    try {
                        // Handle binary audio data
                        if (event.data instanceof ArrayBuffer) {
                            const int16Array = new Int16Array(event.data);
                            playAudio(int16Array);
                            return;
                        }
                        
                        // Handle JSON messages
                        const data = JSON.parse(event.data);
                        console.log('Message from server:', data);
                        
                        if (data.type === 'user_speech') {
                            appendToTranscript(`Você: ${data.text}`, true);
                        } else if (data.type === 'assistant_text') {
                            appendToTranscript(`VTuber: ${data.text}`, false);
                        } else if (data.type === 'status') {
                            updateStatus(data.status === 'listening' ? 'Ouvindo...' : 'Pronto', data.status === 'listening');
                        } else if (data.type === 'error') {
                            console.error('Error:', data.message);
                            alert(`Erro: ${data.message}`);
                        }
                    } catch (e) {
                        console.error('Error parsing message:', e);
                    }
                };
                
                ws.onclose = () => {
                    console.log('WebSocket fechado');
                    updateStatus('Desconectado');
                    connectBtn.disabled = false;
                    listenBtn.disabled = true;
                    stopBtn.disabled = true;
                    
                    // Try to reconnect after 3 seconds
                    setTimeout(() => connectWebSocket(), 3000);
                };
                
                ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    updateStatus('Erro de conexão');
                };
            }
            
            # Button event listeners
            connectBtn.addEventListener('click', connectWebSocket);
            
            listenBtn.addEventListener('click', () => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'start_listening' }));
                }
            });
            
            stopBtn.addEventListener('click', () => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'stop_listening' }));
                }
            });
            
            // Audio context for playing VTuber voice
            let audioContext = null;
            let currentAudio = null;
            
            function initAudioContext() {
                if (!audioContext) {
                    audioContext = new (window.AudioContext || window.webkitAudioContext)();
                }
            }
            
            function playAudio(int16Array) {
                initAudioContext();
                
                // Convert Int16Array to Float32Array for Web Audio API
                const float32Array = new Float32Array(int16Array.length);
                for (let i = 0; i < int16Array.length; i++) {
                    float32Array[i] = int16Array[i] / 32768.0;
                }
                
                // Create audio buffer
                const audioBuffer = audioContext.createBuffer(1, float32Array.length, 22050);
                audioBuffer.copyToChannel(float32Array, 0);
                
                // Stop current audio if playing
                if (currentAudio) {
                    currentAudio.stop();
                }
                
                // Create and play new audio source
                currentAudio = audioContext.createBufferSource();
                currentAudio.buffer = audioBuffer;
                currentAudio.connect(audioContext.destination);
                currentAudio.start();
                
                currentAudio.onended = () => {
                    currentAudio = null;
                };
            }
            
            // Connect automatically when the page loads
            connectWebSocket();
        </script>
    </body>
    </html>
    """

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest) -> Dict[str, Any]:
    """Handle chat messages via HTTP POST."""
    try:
        # Extract and store facts if applicable
        fact = maybe_extract_fact(req.text)
        if fact:
            memory.add_fact(user_id=req.user_id, fact=fact)

        # Get response from LLM
        messages = build_messages(req.user_id, req.text, memory, settings.system_prompt)
        reply = await ollama_chat(messages, settings.ollama_host, settings.ollama_model)
        
        return {"reply": reply}
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections for real-time voice interaction."""
    await ws_handler.connect(websocket)

@app.get("/api/status")
async def get_status():
    """Get the current status of the VTuber service."""
    return {
        "status": "running",
        "ollama_connected": await check_ollama_connection(),
        "stt_ready": True,
        "tts_ready": True,
    }

async def check_ollama_connection() -> bool:
    """Check if the Ollama server is reachable."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.ollama_host}/api/tags")
            response.raise_for_status()
            return True
    except Exception as e:
        logger.warning(f"Ollama connection check failed: {e}")
        return False

@app.post("/api/update_system_prompt")
async def update_system_prompt(update: SystemPromptUpdate):
    """Update the system prompt used for the LLM."""
    settings.system_prompt = update.prompt
    return {"status": "success", "message": "System prompt updated"}

@app.post("/api/update_voice_settings")
async def update_voice_settings(settings: VoiceSettings):
    """Update voice synthesis settings."""
    if settings.speed is not None:
        tts_engine.model_config["speed"] = settings.speed
    if settings.pitch is not None:
        tts_engine.model_config["pitch"] = settings.pitch
    if settings.volume is not None:
        # Volume adjustment would be handled in the frontend
        pass
    
    return {"status": "success", "message": "Voice settings updated"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning",
    )
