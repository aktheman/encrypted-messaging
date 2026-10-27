#!/usr/bin/env python3
"""
Test that mimics the exact usage in test_tls_e2e.py.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import networking
import time
import threading

def test_like_e2e():
    """Test usage similar to test_tls_e2e.py."""
    print("Creating WebSocketMessageQueue instances (like in test_tls_e2e.py)...")

    # This is what test_tls_e2e.py does:
    server = networking.WebSocketMessageQueue("localhost", 8774, is_server=True, secure=False)
    client = networking.WebSocketMessageQueue("localhost", 8774, is_server=False, secure=False)

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
        print("Starting TLS WebSocket server...")
        server.start()
        time.sleep(0.5)  # Give server time to start

        print("Starting TLS WebSocket client...")
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

        print("Sending test message from client to server...")
        # Send message from client (this will go to server)
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
                print("[FAIL] Message content mismatch")
                print(f"  Expected: sender=test_sender, recipient=test_recipient, ciphertext=b'test_ciphertext_123'")
                print(f"  Got: sender={received_message.sender_name}, recipient={received_message.recipient_name}, ciphertext={received_message.ciphertext}")
                return False
        else:
            print("[FAIL] Timeout waiting for message")
            return False

    except Exception as e:
        print(f"✗ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Clean up
        print("Cleaning up...")
        client.stop()
        server.stop()

if __name__ == "__main__":
    print("=== Testing actual usage pattern ===")
    if test_like_e2e():
        print("\n[PASS] Actual usage test passed!")
        sys.exit(0)
    else:
        print("\n[FAIL] Actual usage test failed!")
        sys.exit(1)