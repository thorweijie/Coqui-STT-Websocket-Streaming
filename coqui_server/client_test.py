import time
import websocket

ws = websocket.WebSocket()
ws.connect("ws://localhost:5004/api/v1/stt")

time.sleep(10)
ws.send("Hello")
result = ws.recv()
print(result)  # Print text transcription received from server
