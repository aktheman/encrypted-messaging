#!/usr/bin/env python3
"""
Exact reproduction of the networking.py class structure.
"""

import asyncio
import websockets
import ssl
import threading
import time
import os
from typing import Set
from queue import Queue

# Copy the exact structure from networking.py
class WebSocketServer:
    """WebSocket server with TLS support and client management."""

    def __init__(self, host: str = "localhost", port: int = 8771, secure: bool = False):
        self.host = host
        self.port = port
        self.secure = secure
        self.running = False
        self.server = None
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.messages: Queue = Queue()
        self._server_thread: Optional[threading.Thread] = None
        self._ssl_context: Optional[ssl.SSLContext] = None

        if secure:
            self._setup_ssl_context()

    def _setup_ssl_context(self):
        """Setup SSL context for TLS support.
        In a production environment, you would load proper certificates here.
        For this prototype, we'll create a basic context.
        """
        self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        # Note: For actual TLS, you'd need to load certificates:
        # self._ssl_context.load_cert_chain("cert.pem", "key.pem")

    async def _handle_client(self, websocket, path):
        """Handle a connected client."""
        print(f"[_handle_client] Called with websocket={type(websocket)}, path={path}")
        # Add client to the set
        self.clients.add(websocket)
        try:
            # Handle messages from this client
            async for message in websocket:
                # Put received messages in the queue for processing
                self.messages.put(message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            # Remove client when disconnected
            self.clients.discard(websocket)

    def start(self):
        """Start the WebSocket server."""
        if self.running:
            return

        self.running = True
        self._server_thread = threading.Thread(target=self._run_server, daemon=True)
        self._server_thread.start()

    def _run_server(self):
        """Run the server in a separate thread."""
        async def run_server():
            # Prepare server arguments
            server_args = {
                "host": self.host,
                "port": self.port
            }

            # Add SSL context if TLS is enabled
            if self.secure and self._ssl_context:
                server_args["ssl"] = self._ssl_context

            self.server = await websockets.serve(
                self._handle_client,
                **server_args
            )
            await self.server.wait_closed()

        # Run the asyncio event loop in this thread
        asyncio.run(run_server())

    def stop(self):
        """Stop the WebSocket server."""
        self.running = False
        if self.server:
            self.server.close()
        if self._server_thread:
            self._server_thread.join(timeout=5)

# Test it
def main():
    print("=== Testing exact reproduction of WebSocketServer ===")
    server = WebSocketServer("localhost", 8771, secure=True)
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