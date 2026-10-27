#!/usr/bin/env python3
"""
WebSocket wrapper test to mimic networking.py implementation.
"""

import sys
import os
import asyncio
import threading
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import websockets

class TestServer:
    """Test server class similar to WebSocketServer."""

    def __init__(self, host="localhost", port=8771):
        self.host = host
        self.port = port
        self.server = None

    async def _handle_client(self, websocket, path):
        """Handle a connected client."""
        print(f"[SERVER] Handler called with path: {path}")
        try:
            async for message in websocket:
                print(f"[SERVER] Received message: {message}")
                # Echo the message back
                await websocket.send(f"Echo: {message}")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"[SERVER] Connection closed: {e}")
        except Exception as e:
            print(f"[SERVER] Error in handler: {e}")
            import traceback
            traceback.print_exc()

    def start(self):
        """Start the WebSocket server."""
        async def run_server():
            # Create a wrapper function to ensure correct argument passing
            # The websockets library sometimes calls handlers with only the websocket object
            # instead of (websocket, path), so we extract the path from the request
            async def handler_wrapper(websocket, path=None):
                # If path is not provided (None), try to extract it from the request
                if path is None and hasattr(websocket, 'request') and hasattr(websocket.request, 'path'):
                    path = websocket.request.path
                # If we still don't have a path, default to "/"
                if path is None:
                    path = "/"
                print(f"[SERVER] Wrapper called, path resolved to: {path}")
                return await self._handle_client(websocket, path)

            self.server = await websockets.serve(
                handler_wrapper,
                host=self.host,
                port=self.port
            )
            print(f"[SERVER] WebSocket server started on {self.host}:{self.port}")
            await self.server.wait_closed()

        # Run the asyncio event loop in this thread
        asyncio.run(run_server())

    def stop(self):
        """Stop the WebSocket server."""
        if self.server:
            self.server.close()

async def test_direct_websocket():
    """Test direct websocket communication."""
    print("[TEST] Starting direct websocket test with wrapper...")

    # Start server
    server = TestServer("localhost", 8772)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()

    # Give server time to start
    await asyncio.sleep(1)

    try:
        # Connect client
        print("[TEST] Connecting client...")
        websocket = await websockets.connect("ws://localhost:8772")
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
        print("[TEST] Stopping server...")
        server.stop()
        # Give time for cleanup
        await asyncio.sleep(1)

def main():
    """Run the test."""
    print("=== WebSocket Wrapper Test ===")
    try:
        result = asyncio.run(test_direct_websocket())
        if result:
            print("\n[PASS] Wrapper test passed!")
        else:
            print("\n[FAIL] Wrapper test failed!")
    except Exception as e:
        print(f"[ERROR] Failed to run test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()