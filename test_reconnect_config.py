#!/usr/bin/env python3
"""
Test WebSocket reconnection configuration.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import networking

def test_reconnect_parameters():
    """Test that reconnection parameters can be configured."""
    print("Testing WebSocketClient reconnection parameter configuration...")

    # Test default values
    client1 = networking.WebSocketClient("localhost", 8765, secure=False)
    assert client1._max_reconnect_attempts == 10
    assert client1._base_reconnect_delay == 1.0
    assert client1._max_reconnect_delay == 60.0  # Updated value
    print("[PASS] Default values correct")

    # Test custom values
    client2 = networking.WebSocketClient("localhost", 8765, secure=False,
                                         max_reconnect_attempts=5,
                                         base_reconnect_delay=2.0,
                                         max_reconnect_delay=30.0)
    assert client2._max_reconnect_attempts == 5
    assert client2._base_reconnect_delay == 2.0
    assert client2._max_reconnect_delay == 30.0
    print("[PASS] Custom values correct")

    # Test WebSocketMessageQueue passes through parameters
    mq = networking.WebSocketMessageQueue("localhost", 8765, is_server=False, secure=False,
                                          max_reconnect_attempts=7,
                                          base_reconnect_delay=1.5,
                                          max_reconnect_delay=40.0)
    assert mq.client._max_reconnect_attempts == 7
    assert mq.client._base_reconnect_delay == 1.5
    assert mq.client._max_reconnect_delay == 40.0
    print("[PASS] WebSocketMessageQueue passes through parameters correctly")

    # Test callback attributes exist
    assert hasattr(client1, 'on_connect')
    assert hasattr(client1, 'on_disconnect')
    assert hasattr(client1, 'on_reconnecting')
    assert hasattr(client1, 'on_error')
    print("[PASS] Callback attributes exist")

    print("\n[PASS] All reconnection configuration tests passed!")

if __name__ == "__main__":
    test_reconnect_parameters()