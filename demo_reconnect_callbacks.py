#!/usr/bin/env python3
"""
Demo WebSocket reconnection callbacks and configuration.
"""

import sys
import os
import time
import threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import networking

def demo_reconnect_callbacks():
    """Demo how to use reconnection callbacks."""
    print("=== WebSocket Reconnection Callbacks Demo ===")

    # Connection state tracking
    connect_count = 0
    disconnect_count = 0
    reconnecting_count = 0
    error_count = 0

    def on_connect():
        nonlocal connect_count
        connect_count += 1
        print(f"[CALLBACK] Connected! (#{connect_count})")

    def on_disconnect():
        nonlocal disconnect_count
        disconnect_count += 1
        print(f"[CALLBACK] Disconnected! (#{disconnect_count})")

    def on_reconnecting():
        nonlocal reconnecting_count
        reconnecting_count += 1
        print(f"[CALLBACK] Reconnecting... (attempt #{reconnecting_count})")

    def on_error(error):
        nonlocal error_count
        error_count += 1
        print(f"[CALLBACK] Error: {error} (#{error_count})")

    # Create client with custom reconnection settings and callbacks
    client = networking.WebSocketClient(
        host="localhost",
        port=8766,  # Use different port to avoid conflicts
        secure=False,
        max_reconnect_attempts=3,      # Try 3 times before giving up
        base_reconnect_delay=0.5,      # Start with 0.5s delay
        max_reconnect_delay=5.0        # Max 5s delay
    )

    # Assign callbacks
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_reconnecting = on_reconnecting
    client.on_error = on_error

    print(f"Client configured with:")
    print(f"  Max reconnect attempts: {client._max_reconnect_attempts}")
    print(f"  Base reconnect delay: {client._base_reconnect_delay}s")
    print(f"  Max reconnect delay: {client._max_reconnect_delay}s")
    print()

    # Note: We won't actually connect to a server in this demo since
    # there's no server running, but we can see the callbacks work
    # when we start/stop the client

    print("Starting client (will attempt to connect and fail)...")
    client.start()
    time.sleep(2)  # Let it try to connect and fail a few times

    print("\nStopping client...")
    client.stop()

    print(f"\nFinal counts:")
    print(f"  Connect callbacks: {connect_count}")
    print(f"  Disconnect callbacks: {disconnect_count}")
    print(f"  Reconnecting callbacks: {reconnecting_count}")
    print(f"  Error callbacks: {error_count}")
    print()

    print("[PASS] Reconnection callbacks demo completed!")

if __name__ == "__main__":
    demo_reconnect_callbacks()