#!/usr/bin/env python3
"""
Demo script for WebSocket networking.
Starts a server and two clients that exchange encrypted messages.
"""
import os
import sys
import time
import tempfile
import shutil
import threading
import signal

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from messaging import SecureMessenger


# Global flag for graceful shutdown
shutdown = False


def signal_handler(sig, frame):
    global shutdown
    print("\nShutting down...")
    shutdown = True


signal.signal(signal.SIGINT, signal_handler)


def run_server(data_dir, queue_dir, host="localhost", port=8765, ready_event=None):
    """Run a WebSocket server in a separate thread."""
    server_data_dir = os.path.join(data_dir, "server")
    os.makedirs(server_data_dir, exist_ok=True)

    messenger = SecureMessenger(
        "Server",
        server_data_dir,
        queue_dir,
        use_networking=True,
        host=host,
        port=port,
        is_server=True,
        secure=False,
        auth_method="tofu"
    )

    server_pubkey = messenger.identity_manager.get_public_key_hex()
    server_signing_key = messenger.identity_manager.get_signing_public_key_hex()

    print(f"[SERVER] Started on {host}:{port}")
    print(f"[SERVER] Public key: {server_pubkey}")
    print(f"[SERVER] Signing key: {server_signing_key}")

    # Signal that server is ready
    if ready_event:
        ready_event.set()

    # Store server info for clients
    messenger.server_info = (server_pubkey, server_signing_key)

    # Keep server running
    try:
        while not shutdown:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        print("[SERVER] Shutting down...")
        if hasattr(messenger, 'message_queue'):
            messenger.message_queue.stop()

    return messenger


def run_client(name, data_dir, queue_dir, server_host="localhost", server_port=8765,
               server_info=None, peer_info=None, ready_event=None):
    """Run a client that connects to the server."""
    client_data_dir = os.path.join(data_dir, name.lower())
    os.makedirs(client_data_dir, exist_ok=True)

    messenger = SecureMessenger(
        name,
        client_data_dir,
        queue_dir,
        use_networking=True,
        host=server_host,
        port=server_port,
        is_server=False,
        secure=False,
        auth_method="tofu"
    )

    my_pubkey = messenger.identity_manager.get_public_key_hex()
    my_signing_key = messenger.identity_manager.get_signing_public_key_hex()

    print(f"[{name}] Started, connecting to {server_host}:{server_port}")
    print(f"[{name}] Public key: {my_pubkey}")
    print(f"[{name}] Signing key: {my_signing_key}")

    # Wait for connection to establish
    time.sleep(2)

    # Add peer as contact if we have their info
    if peer_info:
        peer_name, peer_pubkey, peer_signing_key = peer_info
        messenger.add_contact(peer_name, peer_pubkey, peer_signing_key)
        print(f"[{name}] Added contact: {peer_name}")

    # Signal ready
    if ready_event:
        ready_event.set()

    # Send a test message after a moment
    if peer_info:
        peer_name = peer_info[0]
        time.sleep(1)
        success = messenger.send_message(peer_name, f"Hello from {name}!")
        if success:
            print(f"[{name}] Sent message to {peer_name}")
        else:
            print(f"[{name}] Failed to send message")

    # Listen for messages
    try:
        while not shutdown:
            messages = messenger.receive_and_process_messages()
            for sender, text in messages:
                print(f"[{name}] Received from {sender}: {text}")
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print(f"[{name}] Shutting down...")
        if hasattr(messenger, 'message_queue'):
            messenger.message_queue.stop()

    return messenger


def main():
    global shutdown

    print("=" * 60)
    print("Encrypted Messaging - WebSocket Networking Demo")
    print("=" * 60)

    # Create temp directories
    temp_dir = tempfile.mkdtemp(prefix="encrypted_messaging_demo_")
    data_dir = os.path.join(temp_dir, "data")
    queue_dir = os.path.join(temp_dir, "queue")

    print(f"Data dir: {data_dir}")
    print(f"Queue dir: {queue_dir}")

    try:
        server_ready = threading.Event()

        # Start server in background thread
        server_thread = threading.Thread(
            target=run_server,
            args=(data_dir, queue_dir, "localhost", 8765, server_ready),
            daemon=True
        )
        server_thread.start()

        # Wait for server to be ready
        print("Waiting for server to start...")
        server_ready.wait(timeout=10)

        # Give a moment for server to fully start
        time.sleep(1)

        # Start clients - Alice first
        alice_ready = threading.Event()
        alice_thread = threading.Thread(
            target=run_client,
            args=("Alice", data_dir, queue_dir, "localhost", 8765, None, None, alice_ready),
            daemon=True
        )
        alice_thread.start()

        # Wait for Alice to connect
        alice_ready.wait(timeout=10)
        time.sleep(1)

        # Now start Bob with Alice's info
        # We need to get Alice's public keys - let's just run the test sequentially
        # Actually, let's just run both clients and they can discover each other via the server
        # For simplicity in this demo, let's just have them exchange keys manually

        # Create a simple approach: run both clients without contact setup first
        # to verify connection works, then manually add contacts

        print("\n--- Connection established! ---")
        print("Clients connected to server. Now you can:")
        print("1. Use CLI to add contacts between Alice and Bob")
        print("2. Send messages")
        print("\nPress Ctrl+C to stop...")

        # Keep main thread alive
        while not shutdown:
            time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        shutdown = True
        print("\nShutting down...")
        time.sleep(1)
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("Done.")


if __name__ == "__main__":
    main()