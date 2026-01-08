from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()

html = """
<!DOCTYPE html>
<html>
<head>
    <title>Simple WebSocket Test</title>
</head>
<body>
    <h1>Simple WebSocket Test</h1>
    <div id="status">Status: Disconnected</div>
    <button id="connectBtn">Connect</button>
    <div id="messages"></div>
    
    <script>
        let ws;
        const connectBtn = document.getElementById('connectBtn');
        const statusDiv = document.getElementById('status');
        const messagesDiv = document.getElementById('messages');
        
        function log(msg) {
            console.log(msg);
            messagesDiv.innerHTML += '<p>' + msg + '</p>';
        }
        
        connectBtn.onclick = function() {
            log('Creating WebSocket...');
            
            // Try different approaches
            const protocols = ['ws://localhost:8001/ws', 'ws://127.0.0.1:8001/ws'];
            let attempt = 0;
            
            function tryConnect(url) {
                log('Trying: ' + url);
                ws = new WebSocket(url);
                
                ws.onopen = function() {
                    log('WebSocket OPENED with: ' + url);
                    statusDiv.textContent = 'Status: Connected';
                    connectBtn.disabled = true;
                    ws.send('Hello Server!');
                };
                
                ws.onmessage = function(event) {
                    log('Received: ' + event.data);
                };
                
                ws.onerror = function(error) {
                    log('Error with ' + url + ': ' + JSON.stringify(error));
                    if (attempt < protocols.length - 1) {
                        attempt++;
                        log('Trying next URL...');
                        tryConnect(protocols[attempt]);
                    } else {
                        statusDiv.textContent = 'Status: All attempts failed';
                    }
                };
                
                ws.onclose = function(event) {
                    log('WebSocket CLOSED. Code: ' + event.code + ', Reason: ' + event.reason);
                    statusDiv.textContent = 'Status: Disconnected';
                    connectBtn.disabled = false;
                };
            }
            
            tryConnect(protocols[0]);
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
    print("WebSocket connected!")
    
    try:
        # Keep connection alive with heartbeat
        while True:
            try:
                # Wait for message with timeout
                data = await websocket.receive_text()
                print(f"Received: {data}")
                await websocket.send_text(f"Echo: {data}")
            except Exception as e:
                print(f"Error in loop: {e}")
                break
                
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print("WebSocket disconnected")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
