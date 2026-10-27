#!/usr/bin/env python3
"""
Test basic functionality to ensure nothing is broken.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import networking
import time
import threading

def test_basic_functionality():
    """Test that basic functionality still works."""
    print("Testing basic functionality (non-TLS WebSocket)...")

    # Create server and client without TLS
    server = networking.WebSocketMessageQueue("localhost", 8775, is_server=True, secure=False)
    client = networking.WebSocketMessageQueue("localhost", 8775, is_server=False, secure=False)

    # Flag to track if we received the message
    message_received = threading.Event()
    received_message = None

    def message_callback(msg_json):
        nonlocal received_message
        try:
            msg = networking.Message.from_json(msg_json)
            received_message = msg
            message_received.set()
        except Exception as e:
            print(f"Error processing message: {e}")

    # Set up callback for server to receive messages
    server.set_message_callback(message_callback)

    try:
        # Start server and client
        print("Starting WebSocket server...")
        server.start()
        time.sleep(0.5)  # Give server time to start

        print("Starting WebSocket client...")
        client.start()
        time.sleep(0.5)  # Give client time to connect

        # Create a test message
        test_msg = networking.Message(
            sender_name="test_sender",
            recipient_name="test_recipient",
            ciphertext=b"test_ciphertext_123",
            nonce=b"test_nonce_456",
            ephemeral_public_key=b"test_ephem_key",
            salt=b"test_salt",
            timestamp=int(time.time()),
            is_group=False
        )

        print("Sending test message...")
        # Send message from client to server
        if client.send_message(test_msg):
            print("[PASS] Message sent successfully")
        else:
            print("[FAIL] Failed to send message")
            return False

        # Wait for message to be received (with timeout)
        print("Waiting for message to be received...")
        if message_received.wait(timeout=5.0):
            print("[PASS] Message received successfully")

            # Verify the message content
            if (received_message.sender_name == "test_sender" and
                received_message.recipient_name == "test_recipient" and
                received_message.ciphertext == b"test_ciphertext_123"):
                print("[PASS] Message content verified correctly")
                return True
            else:
                print("✗ Message content mismatch")
                return False
        else:
            print("✗ Timeout waiting for message")
            return False

    except Exception as e:
        print(f"[FAIL] Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Clean up
        print("Cleaning up...")
        client.stop()
        server.stop()

if __name__ == "__main__":
    print("=== Basic Functionality Test ===")
    if test_basic_functionality():
        print("\n[PASS] Basic functionality test passed!")
        sys.exit(0)
    else:
        print("\n[FAIL] Basic functionality test failed!")
        sys.exit(1)