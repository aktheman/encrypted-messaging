#!/usr/bin/env python3
"""
Direct websocket test to isolate networking layer issues.
"""

import sys
import os
import asyncio
import threading
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import websockets
import json

async def echo_server(websocket, path):
    """Simple echo server for testing."""
    print(f"[SERVER] New connection from {websocket.remote_address}")
    try:
        async for message in websocket:
            print(f"[SERVER] Received message: {message}")
            # Echo the message back
            await websocket.send(message)
            print(f"[SERVER] Echoed message back")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"[SERVER] Connection closed: {e}")
    finally:
        print(f"[SERVER] Connection closed")

async def test_direct_websocket():
    """Test direct websocket communication."""
    print("[TEST] Starting direct websocket test...")

    # Start server
    server = await websockets.serve(echo_server, "localhost", 8770)
    print("[TEST] WebSocket server started on port 8770")

    # Give server time to start
    await asyncio.sleep(0.5)

    try:
        # Connect client
        print("[TEST] Connecting client...")
        websocket = await websockets.connect("ws://localhost:8770")
        print("[TEST] Client connected")

        # Send test message
        test_message = '{"test": "message"}'
        print(f"[TEST] Sending message: {test_message}")
        await websocket.send(test_message)
        print("[TEST] Message sent")

        # Receive response
        response = await websocket.recv()
        print(f"[TEST] Received response: {response}")

        # Close connection
        await websocket.close()
        print("[TEST] Client connection closed")

        return True

    except Exception as e:
        print(f"[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Stop server
        server.close()
        await server.wait_closed()
        print("[TEST] WebSocket server stopped")

def main():
    """Run the test."""
    print("=== Direct WebSocket Test ===")
    try:
        result = asyncio.run(test_direct_websocket())
        if result:
            print("\n[PASS] Direct websocket test passed!")
        else:
            print("\n[FAIL] Direct websocket test failed!")
    except Exception as e:
        print(f"[ERROR] Failed to run test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()