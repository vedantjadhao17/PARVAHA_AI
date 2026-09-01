import asyncio
import websockets
import json
import time

async def listen():
    try:
        async with websockets.connect("ws://localhost:8000/ws/corridor") as ws:
            print("Connected to WS.")
            for i in range(45):
                start = time.time()
                message = await ws.recv()
                data = json.loads(message)
                elapsed = time.time() - start
                
                print(f"Message {i+1}: time_s={data.get('time_s')} J1_Queue={data.get('junctions', {}).get('J1_SAN', {}).get('queue_m')} (Elapsed: {elapsed:.2f}s)")
                
    except Exception as e:
        print("Error:", e)

asyncio.run(listen())
