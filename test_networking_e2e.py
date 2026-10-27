#!/usr/bin/env python3
"""
End-to-end test for WebSocket networking with encrypted messaging.
"""
import os
import sys
import time
import tempfile
import shutil
import threading

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from messaging import SecureMessenger


def test_websocket_networking():
    """Test WebSocket networking with two clients."""

    # Create temp directories
    temp_dir = tempfile.mkdtemp(prefix="encrypted_messaging_test_")
    data_dir = os.path.join(temp_dir, "data")
    queue_dir = os.path.join(temp_dir, "queue")

    print(f"Test directory: {temp_dir}")

    try:
        # 1. Start server
        server_data_dir = os.path.join(data_dir, "server")
        os.makedirs(server_data_dir, exist_ok=True)

        server = SecureMessenger(
            "Server",
            server_data_dir,
            queue_dir,
            use_networking=True,
            host="localhost",
            port=8765,
            is_server=True,
            secure=False,
            auth_method="tofu"
        )

        server_pubkey = server.identity_manager.get_public_key_hex()
        server_signing_key = server.identity_manager.get_signing_public_key_hex()
        print(f"[SERVER] Public key: {server_pubkey}")

        # 2. Start Alice
        alice_data_dir = os.path.join(data_dir, "alice")
        os.makedirs(alice_data_dir, exist_ok=True)

        alice = SecureMessenger(
            "Alice",
            alice_data_dir,
            queue_dir,
            use_networking=True,
            host="localhost",
            port=8765,
            is_server=False,
            secure=False,
            auth_method="tofu"
        )

        alice_pubkey = alice.identity_manager.get_public_key_hex()
        alice_signing_key = alice.identity_manager.get_signing_public_key_hex()
        print(f"[ALICE] Public key: {alice_pubkey}")

        # Wait for Alice to connect
        time.sleep(2)

        # 3. Start Bob
        bob_data_dir = os.path.join(data_dir, "bob")
        os.makedirs(bob_data_dir, exist_ok=True)

        bob = SecureMessenger(
            "Bob",
            bob_data_dir,
            queue_dir,
            use_networking=True,
            host="localhost",
            port=8765,
            is_server=False,
            secure=False,
            auth_method="tofu"
        )

        bob_pubkey = bob.identity_manager.get_public_key_hex()
        bob_signing_key = bob.identity_manager.get_signing_public_key_hex()
        print(f"[BOB] Public key: {bob_pubkey}")

        # Wait for Bob to connect
        time.sleep(2)

        # 4. Add contacts - Alice adds Bob, Bob adds Alice
        print("\n--- Adding contacts ---")
        alice.add_contact("Bob", bob_pubkey, bob_signing_key)
        bob.add_contact("Alice", alice_pubkey, alice_signing_key)
        print("[ALICE] Added Bob as contact")
        print("[BOB] Added Alice as contact")

        # 5. Alice sends message to Bob
        print("\n--- Sending messages ---")
        success = alice.send_message("Bob", "Hello Bob from Alice via WebSocket!")
        print(f"[ALICE] Send result: {success}")

        # Wait for message to propagate
        time.sleep(2)

        # 6. Bob receives message
        print("\n--- Bob checking for messages ---")
        messages = bob.receive_and_process_messages()
        print(f"[BOB] Received {len(messages)} messages")
        for sender, text in messages:
            print(f"[BOB] From {sender}: {text}")

        # 7. Bob replies
        if messages:
            success = bob.send_message("Alice", "Hi Alice! Got your message via WebSocket!")
            print(f"[BOB] Reply sent: {success}")

            time.sleep(2)

            # 8. Alice receives reply
            print("\n--- Alice checking for reply ---")
            messages = alice.receive_and_process_messages()
            print(f"[ALICE] Received {len(messages)} messages")
            for sender, text in messages:
                print(f"[ALICE] From {sender}: {text}")

        # Verify
        print("\n--- Test Result ---")
        if messages:
            print("SUCCESS: WebSocket networking with encrypted messaging works!")
            return True
        else:
            print("FAILURE: No messages received")
            return False

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        time.sleep(1)
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = test_websocket_networking()
    sys.exit(0 if success else 1)