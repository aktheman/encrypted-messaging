#!/usr/bin/env python3
"""
Test to reproduce the threaded websockets issue.
"""

import asyncio
import websockets
import threading
import time

class WebSocketServer:
    def __init__(self, host: str = "localhost", port: int = 8770):
        self.host = host
        self.port = port
        self.server = None
        self._server_thread = None

    async def _handle_client(self, websocket, path):
        """Handle a connected client."""
        print(f"[_handle_client] Called with websocket={type(websocket)}, path={path}")
        try:
            async for message in websocket:
                print(f"Received: {message}")
                await websocket.send(f"Echo: {message}")
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed")

    def _run_server(self):
        """Run the server in a separate thread."""
        async def run_server():
            self.server = await websockets.serve(
                self._handle_client,
                self.host,
                self.port
            )
            print("Server started in thread")
            await self.server.wait_closed()

        # Run the asyncio event loop in this thread
        asyncio.run(run_server())

    def start(self):
        """Start the WebSocket server."""
        self._server_thread = threading.Thread(target=self._run_server, daemon=True)
        self._server_thread.start()
        print("Server thread started")

    def stop(self):
        """Stop the WebSocket server."""
        if self.server:
            self.server.close()
        if self._server_thread:
            self._server_thread.join(timeout=5)

def main():
    print("=== Testing threaded WebSocket server ===")
    server = WebSocketServer("localhost", 8770)
    try:
        server.start()
        time.sleep(2)  # Let it run for a bit
        print("Test completed successfully")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        server.stop()

if __name__ == "__main__":
    main()