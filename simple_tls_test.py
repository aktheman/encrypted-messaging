#!/usr/bin/env python3
"""
Simple TLS test without Unicode characters.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import networking
import time
import threading

def test_simple_tls():
    """Test TLS WebSocket server and client creation and basic operation."""
    print("Creating TLS WebSocket server...")
    server = networking.WebSocketServer("localhost", 8773, secure=True)

    print("Creating TLS WebSocket client...")
    client = networking.WebSocketClient("localhost", 8773, secure=True)

    print("Starting server...")
    server.start()
    time.sleep(0.5)

    print("Starting client...")
    client.start()
    time.sleep(0.5)

    print("Stopping client...")
    client.stop()

    print("Stopping server...")
    server.stop()

    print("Test completed successfully!")
    return True

if __name__ == "__main__":
    try:
        if test_simple_tls():
            print("[PASS] Simple TLS test passed")
            sys.exit(0)
        else:
            print("[FAIL] Simple TLS test failed")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)