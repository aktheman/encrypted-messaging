#!/usr/bin/env python3
"""
Demo script for WebSocket networking with offline message delivery.
This demonstrates the offline message delivery feature.
Fixed: Uses single connection per user to avoid multiple connection issues.
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


def run_server(data_dir, queue_dir, ready_event):
    """Run WebSocket server."""
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
    print(f"[SERVER] Public key: {server_pubkey}")

    ready_event.set()

    # Keep server running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def run_client(username, data_dir, queue_dir, ready_event, messages_received, contacts_to_add=None, stop_event=None, messenger_ref=None):
    """Run a client messenger."""
    user_data_dir = os.path.join(data_dir, username.lower())
    os.makedirs(user_data_dir, exist_ok=True)

    messenger = SecureMessenger(
        username,
        user_data_dir,
        queue_dir,
        use_networking=True,
        host="localhost",
        port=8765,
        is_server=False,
        secure=False,
        auth_method="tofu"
    )

    # Store messenger reference for external access
    if messenger_ref is not None:
        messenger_ref.append(messenger)

    pubkey = messenger.identity_manager.get_public_key_hex()
    signing_key = messenger.identity_manager.get_signing_public_key_hex()
    print(f"[{username.upper()}] Public key: {pubkey}")
    print(f"[{username.upper()}] Signing key: {signing_key}")

    # Add contacts if provided
    if contacts_to_add:
        for contact_name, contact_pubkey, contact_signkey in contacts_to_add:
            messenger.add_contact(contact_name, contact_pubkey, contact_signkey)
            print(f"[{username.upper()}] Added contact: {contact_name}")

    ready_event.set()

    # Simulate receiving messages in a loop
    while stop_event is None or not stop_event.is_set():
        messages = messenger.receive_and_process_messages()
        for sender, text in messages:
            print(f"[{username.upper()}] Received from {sender}: {text}")
            messages_received.append((sender, text))
        time.sleep(1)

    # Cleanup
    try:
        messenger.message_queue.stop()
    except Exception:
        pass


def main():
    print("=" * 60)
    print("Encrypted Messaging - Offline Delivery Demo (WebSocket)")
    print("=" * 60)

    # Create temp directories
    temp_dir = tempfile.mkdtemp(prefix="encrypted_messaging_offline_demo_")
    data_dir = os.path.join(temp_dir, "data")
    queue_dir = os.path.join(temp_dir, "queue")

    print(f"Data dir: {data_dir}")
    print(f"Queue dir: {queue_dir}")

    try:
        server_ready = threading.Event()
        alice_ready = threading.Event()
        bob_ready = threading.Event()
        alice_messages = []
        bob_messages = []
        stop_event = threading.Event()

        # Store messenger references for sending
        alice_messenger = []
        bob_messenger = []

        # Start server in background thread
        server_thread = threading.Thread(
            target=run_server,
            args=(data_dir, queue_dir, server_ready),
            daemon=True
        )
        server_thread.start()

        # Wait for server to be ready
        print("Waiting for server to start...")
        server_ready.wait(timeout=10)
        time.sleep(1)

        # Create Alice and get her keys FIRST (before Bob connects)
        alice_data_dir = os.path.join(data_dir, "alice")
        os.makedirs(alice_data_dir, exist_ok=True)
        alice_temp = SecureMessenger(
            "Alice", alice_data_dir, queue_dir, use_networking=True,
            host="localhost", port=8765, is_server=False, auth_method="tofu"
        )
        alice_info = ("Alice", alice_temp.identity_manager.get_public_key_hex(),
                      alice_temp.identity_manager.get_signing_public_key_hex())
        alice_temp.message_queue.stop()

        # Create Bob and get his keys (while Bob is still "offline")
        bob_data_dir = os.path.join(data_dir, "bob")
        os.makedirs(bob_data_dir, exist_ok=True)
        bob_temp = SecureMessenger(
            "Bob", bob_data_dir, queue_dir, use_networking=True,
            host="localhost", port=8765, is_server=False, auth_method="tofu"
        )
        bob_info = ("Bob", bob_temp.identity_manager.get_public_key_hex(),
                    bob_temp.identity_manager.get_signing_public_key_hex())
        bob_temp.message_queue.stop()

        print(f"\n--- Keys generated ---")
        print(f"Alice: {alice_info[1][:16]}... (signing: {alice_info[2][:16]}...)")
        print(f"Bob:   {bob_info[1][:16]}... (signing: {bob_info[2][:16]}...)")

        # Start Alice (she comes online first)
        print("\n--- Alice comes ONLINE ---")
        alice_thread = threading.Thread(
            target=run_client,
            args=("Alice", data_dir, queue_dir, alice_ready, alice_messages, [bob_info], stop_event, alice_messenger),
            daemon=True
        )
        alice_thread.start()

        # Wait for Alice to connect
        print("Waiting for Alice to connect...")
        alice_ready.wait(timeout=10)
        time.sleep(2)

        # Alice sends a message to Bob while Bob is OFFLINE
        print("\n--- Alice sends message while Bob is OFFLINE ---")
        # Use Alice's messenger from the thread
        while not alice_messenger:
            time.sleep(0.1)
        success = alice_messenger[0].send_message("Bob", "Hello Bob! You are offline right now.")
        print(f"[ALICE] Send result (Bob offline): {success}")

        time.sleep(2)

        # Now Bob comes online
        print("\n--- Bob comes ONLINE ---")
        bob_thread = threading.Thread(
            target=run_client,
            args=("Bob", data_dir, queue_dir, bob_ready, bob_messages, [alice_info], stop_event, bob_messenger),
            daemon=True
        )
        bob_thread.start()

        # Wait for Bob to connect and receive offline messages
        print("Waiting for Bob to connect...")
        bob_ready.wait(timeout=10)
        time.sleep(3)  # Wait for offline message delivery

        # Bob replies to Alice using his connected messenger
        print("\n--- Bob replies to Alice ---")
        while not bob_messenger:
            time.sleep(0.1)
        success = bob_messenger[0].send_message("Alice", "Hi Alice! I got your offline message!")
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

        # Verify offline delivery worked
        offline_delivered = any("offline" in text.lower() for _, text in bob_messages)
        if bob_messages and offline_delivered:
            print("\n[SUCCESS] Offline message delivery works!")
        elif bob_messages:
            print("\n[PARTIAL] Bob received messages but not the offline one")
        else:
            print("\n[FAILURE] No messages received by Bob")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        stop_event.set()
        time.sleep(1)
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("\nDemo completed.")


if __name__ == "__main__":
    main()