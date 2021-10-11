import sys
import websocket
    
ws = websocket.WebSocket()
ws.connect("ws://localhost:8080/api/v1/stt")

with open(f"{sys.argv[1]}", mode='rb') as file:  # b is important -> binary
    audio = file.read()
    ws.send_binary(audio)
    result =  ws.recv()
    print(result) # Print text transcription received from server