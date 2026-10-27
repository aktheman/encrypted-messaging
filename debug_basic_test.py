#!/usr/bin/env python3
"""
Debug test for basic (non-TLS) functionality.
"""

import sys
import os
import json
import time
import threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from networking import WebSocketMessageQueue
from messaging import Message

def debug_basic_test():
    """Debug test for basic functionality."""
    print("Debugging basic WebSocket functionality...")

    # Create server and client WITHOUT TLS
    server = WebSocketMessageQueue("localhost", 8769, is_server=True, secure=False)
    client = WebSocketMessageQueue("localhost", 8769, is_server=False, secure=False)

    # Flag to track if we received the message
    message_received = threading.Event()
    received_message = None

    def message_callback(msg_json):
        nonlocal received_message
        print(f"[DEBUG] Message callback invoked with: {msg_json[:100]}...")
        try:
            msg = Message.from_json(msg_json)
            received_message = msg
            message_received.set()
            print(f"[DEBUG] Message parsed successfully: {msg.sender_name}")
        except Exception as e:
            print(f"[ERROR] Error processing message: {e}")
            import traceback
            traceback.print_exc()

    # Set up callback for server to receive messages
    server.set_message_callback(message_callback)

    try:
        # Start server and client
        print("[DEBUG] Starting WebSocket server...")
        server.start()
        time.sleep(1)  # Give server time to start

        print("[DEBUG] Starting WebSocket client...")
        client.start()
        time.sleep(1)  # Give client time to connect

        # Create a test message
        test_msg = Message(
            sender_name="test_sender",
            recipient_name="test_recipient",
            ciphertext=b"test_ciphertext_123",
            nonce=b"test_nonce_456",
            ephemeral_public_key=b"test_ephem_key",
            salt=b"test_salt",
            timestamp=int(time.time()),
            is_group=False
        )

        print(f"[DEBUG] Sending test message: {test_msg.sender_name} -> {test_msg.recipient_name}")
        # Send message from client (this will go to server)
        if client.send_message(test_msg):
            print("[PASS] Message sent successfully")
        else:
            print("[FAIL] Failed to send message")
            return False

        # Wait for message to be received (with timeout)
        print("[DEBUG] Waiting for message to be received...")
        if message_received.wait(timeout=10.0):
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
            # Let's check what's in the queues
            print(f"[DEBUG] Server message queue size: {server.server.messages.qsize()}")
            print(f"[DEBUG] Client message queue size: {client.client.messages.qsize()}")
            return False

    except Exception as e:
        print(f"[FAIL] Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Clean up
        print("[DEBUG] Cleaning up...")
        client.stop()
        server.stop()

if __name__ == "__main__":
    print("=== Debug Basic Functionality Test ===")
    if debug_basic_test():
        print("\n[PASS] Debug test passed!")
        sys.exit(0)
    else:
        print("\n[FAIL] Debug test failed!")
        sys.exit(1)