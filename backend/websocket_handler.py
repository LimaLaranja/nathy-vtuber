import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional, Any, AsyncGenerator

import numpy as np
import sounddevice as sd
import soundfile as sf
from fastapi import WebSocket, WebSocketDisconnect
from faster_whisper import WhisperModel

from stt import SpeechToText, STTResult
from tts import TTSEngine, TTSResult
from llm_utils import ollama_chat, build_messages, maybe_extract_fact
from openai_utils import openai_chat
from memory import MemoryStore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Audio configuration
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024
SILENCE_THRESHOLD = 0.01  # Adjust based on your microphone sensitivity
SILENCE_DURATION = 1.5  # seconds of silence to consider end of speech


@dataclass
class AudioBuffer:
    """Circular buffer for audio data."""
    data: np.ndarray
    sample_rate: int
    max_duration: float = 30.0  # Maximum duration in seconds
    
    def __post_init__(self):
        max_samples = int(self.sample_rate * self.max_duration)
        self.data = np.zeros(max_samples, dtype=np.float32)
        self.start_idx = 0
        self.end_idx = 0
        self.is_recording = False
        
    def append(self, audio_chunk: np.ndarray):
        """Append audio data to the buffer."""
        chunk_size = len(audio_chunk)
        if chunk_size == 0:
            return
            
        # Calculate available space
        available = len(self.data) - (self.end_idx - self.start_idx) % len(self.data)
        if available < chunk_size:
            # Buffer is full, discard old data
            self.start_idx = (self.start_idx + (chunk_size - available)) % len(self.data)
            
        # Add new data
        end = (self.end_idx + chunk_size) % len(self.data)
        if end > self.end_idx:
            self.data[self.end_idx:end] = audio_chunk
        else:
            # Handle wrap-around
            remaining = len(self.data) - self.end_idx
            self.data[self.end_idx:] = audio_chunk[:remaining]
            self.data[:end] = audio_chunk[remaining:]
            
        self.end_idx = end
        
    def get_audio(self, start_time: float, end_time: float) -> np.ndarray:
        """Get audio data between start_time and end_time in seconds."""
        start_sample = int(start_time * self.sample_rate)
        end_sample = int(end_time * self.sample_rate)
        start_idx = (self.start_idx + start_sample) % len(self.data)
        end_idx = (self.start_idx + end_sample) % len(self.data)
        
        if end_idx > start_idx:
            return self.data[start_idx:end_idx]
        else:
            return np.concatenate([self.data[start_idx:], self.data[:end_idx]])
    
    def clear(self):
        """Clear the buffer."""
        self.start_idx = 0
        self.end_idx = 0
        self.is_recording = False


class VTuberWebSocketHandler:
    """Handles WebSocket connections for the VTuber application."""
    
    def __init__(self, stt_engine: SpeechToText, tts_engine: TTSEngine, memory: MemoryStore, 
                 ollama_host: str, ollama_model: str, system_prompt: str, llm_provider: str = "ollama"):
        self.stt_engine = stt_engine
        self.tts_engine = tts_engine
        self.memory = memory
        self.ollama_host = ollama_host
        self.ollama_model = ollama_model
        self.llm_provider = llm_provider
        self.system_prompt = system_prompt
        self.websocket = None
        self.current_user_id = None
        self.is_listening = False
        self.audio_buffer = AudioBuffer(sample_rate=SAMPLE_RATE)
        self.vad_threshold = SILENCE_THRESHOLD
        self.last_audio_time = 0
        self.silence_start_time = None
        self.vad_threshold = 0.5  # Voice activity detection threshold
        self.current_user_id = "default"
        self.websocket: Optional[WebSocket] = None
        
    async def connect(self, websocket: WebSocket, user_id: str = "default"):
        """Handle a new WebSocket connection."""
        self.websocket = websocket
        self.current_user_id = user_id
        await websocket.accept()
        
        try:
            # Initialize audio stream
            await self._start_audio_stream()
            
            # Main message loop
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    await self._handle_message(message)
                except json.JSONDecodeError:
                    logger.error("Invalid JSON received")
                    await self._send_error("Invalid JSON format")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await self._send_error(f"Error processing message: {str(e)}")
                    
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await self.cleanup()
    
    async def _start_audio_stream(self):
        """Start the audio input stream."""
        if self.stream is not None:
            self.stream.close()
            
        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"Audio stream status: {status}")
                
            if indata.size > 0:
                audio_chunk = indata[:, 0]  # Take first channel if stereo
                self.audio_buffer.append(audio_chunk)
                
                # Simple VAD (Voice Activity Detection)
                volume_norm = np.linalg.norm(audio_chunk) / np.sqrt(len(audio_chunk))
                is_speaking = volume_norm > self.vad_threshold
                
                current_time = time.time()
                
                if is_speaking:
                    self.last_audio_time = current_time
                    self.silence_start_time = None
                    if not self.audio_buffer.is_recording:
                        self.audio_buffer.is_recording = True
                        logger.info("Started recording")
                elif self.audio_buffer.is_recording:
                    if self.silence_start_time is None:
                        self.silence_start_time = current_time
                    
                    # If we've had silence for the threshold duration, process the audio
                    if current_time - self.silence_start_time >= SILENCE_DURATION:
                        logger.info("End of speech detected, processing...")
                        asyncio.create_task(self._process_audio())
        
        # Start the audio stream
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            callback=audio_callback,
            blocksize=CHUNK_SIZE,
            dtype='float32'
        )
        self.stream.start()
        logger.info("Audio stream started")
    
    async def _process_audio(self):
        """Process the recorded audio with STT and get a response from the LLM."""
        if not self.audio_buffer.is_recording:
            return
            
        self.audio_buffer.is_recording = False
        
        try:
            # Get the last N seconds of audio (adjust as needed)
            audio_duration = min(10.0, (self.audio_buffer.end_idx - self.audio_buffer.start_idx) / SAMPLE_RATE)
            audio_data = self.audio_buffer.get_audio(
                start_time=0,
                end_time=audio_duration
            )
            
            if len(audio_data) == 0:
                logger.warning("No audio data to process")
                return
                
            # Normalize audio
            audio_data = audio_data / np.max(np.abs(audio_data) + 1e-5)
            
            # Transcribe with STT
            result = self.stt_engine.transcribe(
                audio_data,
                sample_rate=SAMPLE_RATE,
                language="pt",
                initial_prompt="Transcrição de voz para uma assistente virtual."
            )
            
            if not result.text.strip():
                logger.info("No speech detected in audio")
                return
                
            logger.info(f"STT Result: {result.text}")
            
            # Send the transcription to the client
            await self._send_message({
                "type": "user_speech",
                "text": result.text,
                "language": result.language,
                "confidence": result.confidence
            })
            
            # Process with LLM and get response
            response_text = await ollama_chat(build_messages(self.current_user_id, result.text, self.memory, self.system_prompt), self.ollama_host, self.ollama_model)
            
            # Extract and store facts if applicable
            fact = maybe_extract_fact(result.text)
            if fact:
                self.memory.add_fact(user_id=self.current_user_id, fact=fact)
            
            # Send the response text to client
            await self._send_message({
                "type": "assistant_text",
                "text": response_text
            })
            
            # Generate speech with TTS
            tts_result = self.tts_engine.synthesize(response_text)
            
            # Send audio data to client
            await self._send_audio(tts_result.audio, tts_result.sample_rate)
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            try:
                await self._send_error(f"Error processing audio: {str(e)}")
            except:
                pass  # Ignore errors if connection is closed
        finally:
            # Clear the buffer for the next recording
            self.audio_buffer.clear()
    
    async def _process_text_message(self, text: str):
        """Process text messages from the input field."""
        try:
            logger.info(f"Processing text message: {text}")
            
            # Send the text to the client for display
            await self._send_message({
                "type": "transcription",
                "text": text
            })
            
            # Process with LLM and get response
            try:
                if self.llm_provider == "openai":
                    response_text = await openai_chat(build_messages(self.current_user_id, text, self.memory, self.system_prompt))
                else:
                    response_text = await ollama_chat(build_messages(self.current_user_id, text, self.memory, self.system_prompt), self.ollama_host, self.ollama_model)
            except Exception as llm_error:
                logger.warning(f"LLM error, using fallback: {llm_error}")
                # Fallback response when LLM is not available
                response_text = self._generate_fallback_response(text)
            
            # Extract and store facts if applicable
            fact = maybe_extract_fact(text)
            if fact:
                self.memory.add_fact(user_id=self.current_user_id, fact=fact)
            
            # Send the response text to client
            await self._send_message({
                "type": "response",
                "text": response_text
            })
            
            # Generate speech with TTS
            tts_result = self.tts_engine.synthesize(response_text)
            
            # Send audio data to client
            await self._send_audio(tts_result.audio, tts_result.sample_rate)
            
        except Exception as e:
            logger.error(f"Error processing text message: {e}")
            try:
                await self._send_error(f"Error processing text message: {str(e)}")
            except:
                pass  # Ignore errors if connection is closed
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming WebSocket messages."""
        msg_type = message.get("type")
        
        if msg_type == "start_listening":
            self.is_listening = True
            await self._send_message({"type": "status", "status": "listening"})
            
        elif msg_type == "stop_listening":
            self.is_listening = False
            await self._send_message({"type": "status", "status": "idle"})
            
        elif msg_type == "text":
            # Handle text messages from the input field
            text = message.get("text", "").strip()
            if text:
                await self._process_text_message(text)
                
        elif msg_type == "audio_config":
            # Update audio configuration if needed
            if "vad_threshold" in message:
                self.vad_threshold = float(message["vad_threshold"])
                
        elif msg_type == "ping":
            await self._send_message({"type": "pong"})
            
    async def _send_message(self, data: Dict[str, Any]):
        """Send a JSON message to the client."""
        if self.websocket:
            try:
                await self.websocket.send_text(json.dumps(data, ensure_ascii=False))
            except Exception as e:
                logger.error(f"Error sending message: {e}")
    
    async def _send_error(self, message: str):
        """Send an error message to the client."""
        try:
            await self._send_message({
                "type": "error",
                "message": message
            })
        except Exception as e:
            logger.error(f"Error sending error message: {e}")
    
    async def _send_audio(self, audio_data: np.ndarray, sample_rate: int):
        """Send audio data to the client."""
        if self.websocket:
            try:
                # Convert to 16-bit PCM
                audio_int16 = (audio_data * 32767).astype(np.int16)
                await self.websocket.send_bytes(audio_int16.tobytes())
            except Exception as e:
                logger.error(f"Error sending audio: {e}")
    
    def _generate_fallback_response(self, user_text: str) -> str:
        """Generate fallback responses when Ollama is not available."""
        import random
        
        text_lower = user_text.lower()
        
        # Greeting patterns
        if any(word in text_lower for word in ['oi', 'ola', 'olá', 'eai', 'e aí']):
            greetings = [
                "Oieee! Tudo bem? 😊",
                "Olá! Que bom conversar com você! 🌸",
                "E aí! Sumida! 😄",
                "Oiiee! Como vai? ✨"
            ]
            return random.choice(greetings)
        
        # Question patterns
        elif '?' in user_text or any(word in text_lower for word in ['qual', 'como', 'onde', 'quando', 'por que']):
            responses = [
                "Hmm, boa pergunta! Mas sem o Ollama eu não consigo pensar muito fundo... 🤔",
                "Nossa, você me pegou! Preciso do meu cérebro AI para responder direito! 🧠",
                "Essa é difícil! Meu superpoder AI está em manutenção! 😅",
                "Bom... sem meus superpoderes de IA, fico um pouco limitada! 🤖"
            ]
            return random.choice(responses)
        
        # Compliment patterns
        elif any(word in text_lower for word in ['linda', 'bonita', 'legal', 'gostosa', 'maravilhosa']):
            responses = [
                "Awwwn, você é muito gentil! 😊💕",
                "Nossa, obrigada! Fiquei toda corada! 🌸",
                "Para de! Você me deixa sem jeito! 😄",
                "Mashiaaa! Você é o melhor! ✨"
            ]
            return random.choice(responses)
        
        # Default responses
        else:
            responses = [
                "Legal! Mas sem o Ollama eu não consigo responder muito bem... 😅",
                "Hmm, interessante! Preciso do meu cérebro AI para conversar direitinho! 🤖",
                "Nossa, você sabe que sem meu superpoder de IA fico meio limitada? 🤔",
                "Legal demais! Mas para responder melhor, preciso do Ollama rodando! 🌸"
            ]
            return random.choice(responses)
    
    async def cleanup(self):
        """Clean up resources."""
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        self.audio_buffer.clear()
        self.is_listening = False
        logger.info("WebSocket handler cleaned up")
