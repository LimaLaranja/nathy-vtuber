from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import json
import re
from datetime import datetime

# Simple knowledge base for the VTuber
class VTuberBrain:
    def __init__(self):
        self.knowledge = {
            "greetings": {
                "patterns": [r"oi", r"olá", r"hello", r"bom dia", r"boa tarde", r"boa noite"],
                "responses": [
                    "Olá! Sou sua VTuber assistente! Como posso ajudar?",
                    "Oi! Que bom conversar com você!",
                    "Olá! Estou aqui para conversar com você!"
                ]
            },
            "how_are_you": {
                "patterns": [r"como vai", r"como esta", r"tudo bem", r"como voce esta"],
                "responses": [
                    "Estou ótima! Pronta para conversar e aprender com você!",
                    "Tudo bem por aqui! E você, como está?",
                    "Estou funcionando perfeitamente! Obrigada por perguntar!"
                ]
            },
            "what_are_you": {
                "patterns": [r"quem e voce", r"o que e voce", r"voce e", r"vtuber"],
                "responses": [
                    "Sou uma VTuber assistente! Estou aqui para conversar e aprender.",
                    "Sou uma VTuber virtual criada para interagir com você!",
                    "Sou sua assistente VTuber! Posso conversar e aprender coisas novas."
                ]
            },
            "thanks": {
                "patterns": [r"obrigado", r"obrigada", r"valeu", r"agradec"],
                "responses": [
                    "De nada! Fico feliz em ajudar!",
                    "Por nada! Sempre que precisar, estou aqui!",
                    "Imagina! É um prazer conversar com você!"
                ]
            },
            "bye": {
                "patterns": [r"tchau", r"adeus", r"ate logo", r"ate mais"],
                "responses": [
                    "Tchau! Foi ótimo conversar com você!",
                    "Até logo! Volte sempre!",
                    "Tchau! Tenha um ótimo dia!"
                ]
            }
        }
        self.user_facts = {}  # Store facts learned from user
        self.conversation_history = []  # Keep track of conversation
    
    def get_response(self, user_input, user_id="default"):
        user_input_lower = user_input.lower()
        
        # Store in conversation history
        self.conversation_history.append({
            "timestamp": datetime.now(),
            "user_id": user_id,
            "message": user_input
        })
        
        # Check for learning patterns
        if self._is_learning_pattern(user_input_lower):
            return self._learn_from_user(user_input)
        
        # Check knowledge base
        for category, data in self.knowledge.items():
            for pattern in data["patterns"]:
                if re.search(pattern, user_input_lower):
                    return self._get_random_response(data["responses"])
        
        # Check if user is asking about learned facts
        if self._is_fact_question(user_input_lower):
            return self._answer_fact_question(user_input_lower)
        
        # Default responses
        default_responses = [
            "Isso é interessante! Pode me contar mais?",
            "Hmm, estou aprendendo sobre isso. O que você acha?",
            "Legal! Não sei muito sobre isso, mas estou curiosa para aprender!",
            "Que interessante! Você pode me ensinar mais sobre isso?",
            "Estou processando isso... Pode explicar de outra forma?"
        ]
        
        return self._get_random_response(default_responses)
    
    def _is_learning_pattern(self, text):
        learning_patterns = [
            r"eu sou", r"meu nome e", r"eu moro", r"eu gosto", r"eu nao gosto",
            r"saiba que", r"aprenda que", r"lembre que", r"eu trabalho", r"eu estudo"
        ]
        return any(re.search(pattern, text) for pattern in learning_patterns)
    
    def _learn_from_user(self, text):
        # Extract and store facts
        fact_patterns = {
            r"meu nome e (\w+)": "nome",
            r"eu moro em ([\w\s]+)": "morada", 
            r"eu gosto de ([\w\s]+)": "gosta",
            r"eu trabalho como ([\w\s]+)": "trabalho",
            r"eu estudo ([\w\s]+)": "estudo"
        }
        
        for pattern, fact_type in fact_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fact_value = match.group(1).strip()
                self.user_facts[fact_type] = fact_value
                return f"Entendido! Vou lembrar que você {fact_type} é {fact_value}. Obrigada por me ensinar!"
        
        return "Obrigada por compartilhar isso comigo! Estou aprendendo cada vez mais."
    
    def _is_fact_question(self, text):
        question_patterns = [
            r"voce lembra", r"voce sabe", r"eu ja falei", r"eu ja disse"
        ]
        return any(re.search(pattern, text) for pattern in question_patterns)
    
    def _answer_fact_question(self, text):
        if "nome" in text and "nome" in self.user_facts:
            return f"Sim! Seu nome é {self.user_facts['nome']}, certo?"
        elif "trabalho" in text and "trabalho" in self.user_facts:
            return f"Claro! Você trabalha como {self.user_facts['trabalho']}."
        elif "gosta" in text and "gosta" in self.user_facts:
            return f"Sim! Você gosta de {self.user_facts['gosta']}."
        
        return "Hmm, não me lembro disso... Pode me lembrar novamente?"
    
    def _get_random_response(self, responses):
        import random
        return random.choice(responses)

# Initialize VTuber brain
vtuber_brain = VTuberBrain()

app = FastAPI()

html = """
<!DOCTYPE html>
<html>
<head>
    <title>VTuber Simples</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        .status { margin: 10px 0; padding: 10px; background: #f0f0f0; }
        .transcript { height: 200px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; margin: 10px 0; }
        button { padding: 10px 20px; margin: 5px; }
        .connected { background: #d4edda; }
        .disconnected { background: #f8d7da; }
    </style>
</head>
<body>
    <h1>VTuber Simples</h1>
    <div id="status" class="status disconnected">Status: Desconectado</div>
    <button id="connectBtn">Conectar</button>
    <button id="disconnectBtn" disabled>Desconectar</button>
    
    <div class="transcript" id="transcript"></div>
    
    <div style="margin: 10px 0;">
        <input type="text" id="chatInput" placeholder="Digite sua mensagem..." style="width: 70%; padding: 10px;">
        <button id="sendBtn" disabled>Enviar</button>
    </div>
    
    <script>
        let ws;
        const connectBtn = document.getElementById('connectBtn');
        const disconnectBtn = document.getElementById('disconnectBtn');
        const sendBtn = document.getElementById('sendBtn');
        const chatInput = document.getElementById('chatInput');
        const statusDiv = document.getElementById('status');
        const transcriptDiv = document.getElementById('transcript');
        
        function log(msg) {
            console.log(msg);
            transcriptDiv.innerHTML += '<p>' + new Date().toLocaleTimeString() + ': ' + msg + '</p>';
            transcriptDiv.scrollTop = transcriptDiv.scrollHeight;
        }
        
        function updateStatus(text, connected = false) {
            statusDiv.textContent = 'Status: ' + text;
            statusDiv.className = 'status ' + (connected ? 'connected' : 'disconnected');
        }
        
        function connect() {
            log('Tentando conectar WebSocket...');
            updateStatus('Conectando...', false);
            
            ws = new WebSocket('ws://localhost:8000/ws');
            
            ws.onopen = function() {
                log('WebSocket CONECTADO!');
                updateStatus('Conectado', true);
                connectBtn.disabled = true;
                disconnectBtn.disabled = false;
                sendBtn.disabled = false;
                
                ws.send(JSON.stringify({
                    type: 'hello',
                    user_id: 'user_1'
                }));
            };
            
            ws.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === "response" || data.type === "welcome") {
                        log('VTuber: ' + data.message);
                    } else {
                        log('Mensagem recebida: ' + JSON.stringify(data));
                    }
                } catch (e) {
                    log('Mensagem recebida: ' + event.data);
                }
            };
            
            ws.onerror = function(error) {
                log('ERRO WebSocket: ' + JSON.stringify(error));
                updateStatus('Erro', false);
            };
            
            ws.onclose = function(event) {
                log('WebSocket FECHADO. Código: ' + event.code + ', Razão: ' + event.reason);
                updateStatus('Desconectado', false);
                connectBtn.disabled = false;
                disconnectBtn.disabled = true;
                sendBtn.disabled = true;
            };
        }
        
        function sendMessage() {
            const message = chatInput.value.trim();
            if (message && ws && ws.readyState === WebSocket.OPEN) {
                log('Você: ' + message);
                ws.send(JSON.stringify({
                    type: 'chat',
                    text: message
                }));
                chatInput.value = '';
            }
        }
        
        function disconnect() {
            if (ws) {
                ws.close();
            }
        }
        
        connectBtn.onclick = connect;
        disconnectBtn.onclick = disconnect;
        sendBtn.onclick = sendMessage;
        chatInput.onkeypress = function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        };
    </script>
</body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("VTuber WebSocket conectado!")
    
    try:
        while True:
            try:
                data = await websocket.receive_text()
                print(f"Recebido: {data}")
                
                # Parse message
                try:
                    message = json.loads(data)
                    msg_type = message.get("type", "")
                    
                    if msg_type == "hello":
                        # Welcome message
                        await websocket.send_text(json.dumps({
                            "type": "welcome",
                            "message": "Olá! Eu sou sua VTuber assistente!"
                        }))
                    elif msg_type == "chat":
                        # Simple chat response
                        user_text = message.get("text", "")
                        response = vtuber_brain.get_response(user_text, "user_1")
                        await websocket.send_text(json.dumps({
                            "type": "response",
                            "message": response
                        }))
                    else:
                        # Echo for unknown messages
                        await websocket.send_text(data)
                        
                except json.JSONDecodeError:
                    # Simple echo for non-JSON
                    await websocket.send_text(data)
                
            except Exception as e:
                print(f"Erro no loop: {e}")
                break
                
    except Exception as e:
        print(f"Erro WebSocket: {e}")
    finally:
        print("VTuber WebSocket desconectado")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
