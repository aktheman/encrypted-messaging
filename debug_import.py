#!/usr/bin/env python3
"""
Debug script to check imports and class instantiation.
"""

import sys
import os
print(f"Python executable: {sys.executable}")
print(f"Current working directory: {os.getcwd()}")
print(f"sys.path: {sys.path}")

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("\n=== Trying to import networking ===")
try:
    import networking
    print("[PASS] Successfully imported networking")
    print(f"networking module: {networking}")
    print(f"networking.WebSocketServer: {networking.WebSocketServer}")

    print("\n=== Trying to instantiate WebSocketServer ===")
    server = networking.WebSocketServer("localhost", 8772, secure=True)
    print(f"[PASS] Successfully created WebSocketServer instance: {server}")
    print(f"Server._handle_client: {server._handle_client}")
    print(f"Server._handle_client type: {type(server._handle_client)}")

    print("\n=== Trying to start server ===")
    server.start()
    print("[PASS] Server start() called successfully")

    # Give it a moment to start
    import time
    time.sleep(1)

    print("\n=== Trying to stop server ===")
    server.stop()
    print("✓ Server stop() called successfully")

except Exception as e:
    print(f"[FAIL] Error: {e}")
    import traceback
    traceback.print_exc()