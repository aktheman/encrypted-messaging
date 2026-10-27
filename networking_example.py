"""
Networking example for the encrypted messaging app.
Shows how to set up a WebSocket server and clients for encrypted messaging.
"""

import subprocess
import time
import threading
import signal
import sys
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command in a subprocess."""
    return subprocess.Popen(cmd, shell=True, cwd=cwd)

def main():
    print("=" * 60)
    print("ENCRYPTED MESSAGING APP - NETWORKING EXAMPLE")
    print("=" * 60)
    print()
    print("This example shows how to use WebSocket networking")
    print("for encrypted messaging between multiple clients.")
    print()
    print("Steps:")
    print("1. Start a WebSocket server")
    print("2. Initialize two clients (Alice and Bob)")
    print("3. Exchange public keys to add contacts")
    print("4. Send encrypted messages between clients")
    print()

    # Create data directories
    Path("./network_data").mkdir(exist_ok=True)
    Path("./network_data/server").mkdir(exist_ok=True)
    Path("./network_data/alice").mkdir(exist_ok=True)
    Path("./network_data/bob").mkdir(exist_ok=True)

    print("Starting WebSocket server...")
    server_proc = run_command(
        "python main.py server-info --username server "
        "--data-dir ./network_data/server "
        "--networking --server "
        "--host localhost --port 8765"
    )

    # Give server time to start
    time.sleep(2)

    print("\nInitializing Alice...")
    # Initialize Alice
    run_command(
        "python main.py init --username Alice "
        "--data-dir ./network_data/alice "
        "--networking --host localhost --port 8765"
    )

    # Get Alice's public key
    result = subprocess.run(
        "python main.py init --username Alice "
        "--data-dir ./network_data/alice "
        "--networking --host localhost --port 8765",
        capture_output=True, text=True, shell=True
    )
    # Extract public key from output (simplified)
    alice_pubkey = "alice_public_key_placeholder"  # In real use, extract from output

    print("Initializing Bob...")
    # Initialize Bob
    run_command(
        "python main.py init --username Bob "
        "--data-dir ./network_data/bob "
        "--networking --host localhost --port 8765"
    )

    print("\nAdding contacts...")
    # Alice adds Bob as contact (using placeholder - in real scenario, exchange actual keys)
    run_command(
        "python main.py add-contact --username Alice "
        "--data-dir ./network_data/alice "
        "--networking --host localhost --port 8765 "
        "Bob bob_public_key_placeholder"
    )

    # Bob adds Alice as contact
    run_command(
        "python main.py add-contact --username Bob "
        "--data-dir ./network_data/bob "
        "--networking --host localhost --port 8765 "
        "Alice alice_public_key_placeholder"
    )

    print("\nSending test message from Alice to Bob...")
    # Send message from Alice to Bob
    run_command(
        "python main.py send --username Alice "
        "--data-dir ./network_data/alice "
        "--message 'Hello Bob! This is a secure message via WebSocket.' "
        "--networking --host localhost --port 8765 Bob"
    )

    print("\nTo see the message, Bob would run:")
    print("python main.py receive --username Bob --data-dir ./network_data/bob --networking --host localhost --port 8765")

    print("\n" + "=" * 60)
    print("NETWORKING EXAMPLE SETUP COMPLETE")
    print("=" * 60)
    print()
    print("Notes:")
    print("- The WebSocket server is running in the background")
    print("- Clients are configured to connect to localhost:8765")
    print("- Actual public key exchange would be done manually or via secure channel")
    print("- To stop the server, press Ctrl+C in the server terminal")
    print()
    print("For a real conversation:")
    print("1. In terminal 1: Run the server command above")
    print("2. In terminal 2: Initialize and use Alice")
    print("3. In terminal 3: Initialize and use Bob")
    print("4. Exchange real public keys and add them as contacts")
    print("5. Send and receive messages in real-time!")
    print()

    try:
        # Keep the example running until user interrupts
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        server_proc.terminate()
        server_proc.wait()

if __name__ == "__main__":
    main()