#!/usr/bin/env python3
"""
Demo script for TUI - runs two clients that can message each other via file-based queue.
This demonstrates the TUI functionality without needing a WebSocket server.
"""
import os
import sys
import time
import tempfile
import shutil
import threading

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from messaging import SecureMessenger, MessageQueue


def simulate_delivery(queue_dir, stop_event):
    """Background thread to simulate message delivery from outbox to inbox."""
    import json
    while not stop_event.is_set():
        # Check outbox for messages
        outbox_path = os.path.join(queue_dir, "outbox")
        if os.path.exists(outbox_path):
            for msg_file in os.listdir(outbox_path):
                if msg_file.endswith(".msg"):
                    src = os.path.join(outbox_path, msg_file)
                    try:
                        # Read message to get recipient
                        with open(src, 'r') as f:
                            msg_data = json.load(f)
                        recipient = msg_data.get('recipient_name', '')

                        # Determine target inbox
                        target_inbox = f"inbox_{recipient}"
                        inbox_path = os.path.join(queue_dir, target_inbox)

                        if os.path.exists(inbox_path):
                            dst = os.path.join(inbox_path, msg_file)
                            shutil.move(src, dst)
                            print(f"[DELIVERY] Delivered {msg_file} to {target_inbox}")
                        else:
                            print(f"[DELIVERY] No inbox found for recipient: {recipient}")
                    except Exception as e:
                        print(f"[DELIVERY] Error: {e}")
        time.sleep(0.5)


def run_alice(data_dir, queue_dir, ready_event, messages_received):
    """Run Alice's messenger."""
    alice_data_dir = os.path.join(data_dir, "alice")
    os.makedirs(alice_data_dir, exist_ok=True)

    alice = SecureMessenger(
        "Alice",
        alice_data_dir,
        queue_dir,
        use_networking=False,
        auth_method="tofu"
    )

    alice_pubkey = alice.identity_manager.get_public_key_hex()
    alice_signing_key = alice.identity_manager.get_signing_public_key_hex()
    print(f"[ALICE] Public key: {alice_pubkey}")
    print(f"[ALICE] Signing key: {alice_signing_key}")

    ready_event.set()

    # Simulate receiving messages in a loop
    while True:
        messages = alice.receive_and_process_messages()
        for sender, text in messages:
            print(f"[ALICE] Received from {sender}: {text}")
            messages_received.append((sender, text))
        time.sleep(1)


def run_bob(data_dir, queue_dir, ready_event, messages_received, alice_info):
    """Run Bob's messenger."""
    bob_data_dir = os.path.join(data_dir, "bob")
    os.makedirs(bob_data_dir, exist_ok=True)

    bob = SecureMessenger(
        "Bob",
        bob_data_dir,
        queue_dir,
        use_networking=False,
        auth_method="tofu"
    )

    bob_pubkey = bob.identity_manager.get_public_key_hex()
    bob_signing_key = bob.identity_manager.get_signing_public_key_hex()
    print(f"[BOB] Public key: {bob_pubkey}")
    print(f"[BOB] Signing key: {bob_signing_key}")

    # Add Alice as contact
    alice_name, alice_pubkey, alice_signing_key = alice_info
    bob.add_contact(alice_name, alice_pubkey, alice_signing_key)
    print(f"[BOB] Added contact: {alice_name}")

    ready_event.set()

    # Simulate receiving messages in a loop
    while True:
        messages = bob.receive_and_process_messages()
        for sender, text in messages:
            print(f"[BOB] Received from {sender}: {text}")
            messages_received.append((sender, text))
        time.sleep(1)


def main():
    print("=" * 60)
    print("Encrypted Messaging - TUI Demo (File-based)")
    print("=" * 60)

    # Create temp directories
    temp_dir = tempfile.mkdtemp(prefix="encrypted_messaging_tui_demo_")
    data_dir = os.path.join(temp_dir, "data")
    queue_dir = os.path.join(temp_dir, "queue")

    print(f"Data dir: {data_dir}")
    print(f"Queue dir: {queue_dir}")

    # Create inbox directories for each user
    os.makedirs(os.path.join(queue_dir, "inbox_Alice"), exist_ok=True)
    os.makedirs(os.path.join(queue_dir, "inbox_Bob"), exist_ok=True)

    try:
        alice_ready = threading.Event()
        bob_ready = threading.Event()
        alice_messages = []
        bob_messages = []
        stop_delivery = threading.Event()

        # Start delivery simulator
        delivery_thread = threading.Thread(
            target=simulate_delivery,
            args=(queue_dir, stop_delivery),
            daemon=True
        )
        delivery_thread.start()

        # Start Alice in background thread
        alice_thread = threading.Thread(
            target=run_alice,
            args=(data_dir, queue_dir, alice_ready, alice_messages),
            daemon=True
        )
        alice_thread.start()

        # Wait for Alice to be ready
        print("Waiting for Alice to start...")
        alice_ready.wait(timeout=10)
        time.sleep(1)

        # Get Alice's keys for Bob
        alice_data_dir = os.path.join(data_dir, "alice")
        alice_messenger = SecureMessenger(
            "Alice", alice_data_dir, queue_dir, use_networking=False
        )
        alice_info = ("Alice", alice_messenger.identity_manager.get_public_key_hex(),
                      alice_messenger.identity_manager.get_signing_public_key_hex())

        # Start Bob in background thread
        bob_thread = threading.Thread(
            target=run_bob,
            args=(data_dir, queue_dir, bob_ready, bob_messages, alice_info),
            daemon=True
        )
        bob_thread.start()

        # Wait for Bob to be ready
        print("Waiting for Bob to start...")
        bob_ready.wait(timeout=10)
        time.sleep(1)

        # Now Alice adds Bob as contact
        bob_data_dir = os.path.join(data_dir, "bob")
        bob_messenger = SecureMessenger(
            "Bob", bob_data_dir, queue_dir, use_networking=False
        )
        bob_pubkey = bob_messenger.identity_manager.get_public_key_hex()
        bob_signing_key = bob_messenger.identity_manager.get_signing_public_key_hex()
        alice_messenger.add_contact("Bob", bob_pubkey, bob_signing_key)
        print("[ALICE] Added contact: Bob")

        print("\n--- Connection established! ---")
        print("Both clients running. Sending test messages...")

        # Alice sends a message to Bob
        print("\n[ALICE] Sending message to Bob...")
        success = alice_messenger.send_message("Bob", "Hello Bob from Alice via TUI demo!")
        print(f"[ALICE] Send result: {success}")

        # Wait for message to propagate
        time.sleep(3)

        # Bob replies
        print("\n[BOB] Sending reply to Alice...")
        success = bob_messenger.send_message("Alice", "Hi Alice! Got your message!")
        print(f"[BOB] Send result: {success}")

        time.sleep(3)

        # Check results
        print("\n--- Test Results ---")
        print(f"Alice received {len(alice_messages)} messages")
        for sender, text in alice_messages:
            print(f"  From {sender}: {text}")

        print(f"Bob received {len(bob_messages)} messages")
        for sender, text in bob_messages:
            print(f"  From {sender}: {text}")

        if alice_messages and bob_messages:
            print("\nSUCCESS: File-based messaging works!")
        else:
            print("\nFAILURE: Messages not received")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        stop_delivery.set()
        time.sleep(1)
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("\nDemo completed.")


if __name__ == "__main__":
    main()