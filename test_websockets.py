#!/usr/bin/env python3
"""
Simple test to isolate websockets serve issue.
"""

import asyncio
import websockets

async def handler(websocket, path):
    print(f"Handler called with websocket={websocket}, path={path}")
    try:
        async for message in websocket:
            print(f"Received: {message}")
            await websocket.send(f"Echo: {message}")
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed")

async def main():
    # Test 1: Direct function
    print("=== Test 1: Direct function ===")
    try:
        server = await websockets.serve(handler, "localhost", 8768)
        print("Server started successfully with direct function")
        server.close()
        await server.wait_closed()
    except Exception as e:
        print(f"Failed with direct function: {e}")

    # Test 2: Method of an object
    print("\n=== Test 2: Method of an object ===")
    class TestClass:
        async def method_handler(self, websocket, path):
            print(f"Method handler called with websocket={websocket}, path={path}")

    try:
        obj = TestClass()
        server = await websockets.serve(obj.method_handler, "localhost", 8769)
        print("Server started successfully with method handler")
        server.close()
        await server.wait_closed()
    except Exception as e:
        print(f"Failed with method handler: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())