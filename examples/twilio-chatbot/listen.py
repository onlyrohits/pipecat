import asyncio
import websockets
import base64

async def connect_and_print_audio():
    uri = "wss://easy-badly-gazelle.ngrok-free.app/ws"
    
    async with websockets.connect(uri) as websocket:
        print(f"Connected to {uri}")
        
        try:
            while True:
                message = await websocket.recv()
                
                # Assuming the audio data is sent as base64 encoded string
                try:
                    audio_data = base64.b64decode(message)
                    print(f"Received audio data: {len(audio_data)} bytes")
                    # Here you would typically process or save the audio data
                    # For demonstration, we'll just print the first few bytes
                    print(f"First few bytes: {audio_data[:20]}")
                except:
                    # If it's not base64 encoded audio, print it as is
                    print(f"Received message: {message}")
        
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed")

asyncio.get_event_loop().run_until_complete(connect_and_print_audio())
