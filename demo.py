"""
Demo script for the encrypted messaging app.
Shows how users can exchange encrypted messages individually and in groups.
"""

import os
import time
import shutil
import sys
import json
from pathlib import Path

# Import local modules
try:
    # When run as module
    from .main import main
except ImportError:
    # When run directly as script
    from main import main


def simulate_delivery(queue_dir: str, group_members: dict, delay: float = 0.1):
    """
    Simulate network delivery by moving messages from shared outbox to per-user inboxes.

    Args:
        queue_dir: Path to shared queue directory
        group_members: Dict mapping group names to lists of member usernames
        delay: Simulated network delay in seconds
    """
    print(f"Simulating network transport with {delay}s delay...")
    outbox_path = Path(queue_dir) / "outbox"
    if not outbox_path.exists():
        print("No outbox directory found.")
        return

    for msg_file in outbox_path.glob("*.msg"):
        try:
            with open(msg_file, 'r') as f:
                message_json = f.read()
            message = json.loads(message_json)

            # Simulate delay
            time.sleep(delay)

            # Determine recipients
            recipients = []
            if message.get('is_group', False):
                # Group message - deliver to all group members except sender
                group_name = message.get('recipient_name')
                sender = message.get('sender_name')
                if group_name in group_members:
                    for member in group_members[group_name]:
                        if member != sender:
                            recipients.append(member)
            else:
                # Individual message - deliver to recipient
                recipient = message.get('recipient_name')
                if recipient:
                    recipients.append(recipient)

            # Deliver to each recipient's inbox
            for recipient in recipients:
                inbox_dir = Path(queue_dir) / f"inbox_{recipient}"
                inbox_dir.mkdir(parents=True, exist_ok=True)
                inbox_path = inbox_dir / msg_file.name
                inbox_path.write_text(message_json)
                print(f"Delivered to {recipient}: {msg_file.name}")

            # Remove from outbox
            msg_file.unlink()

        except Exception as e:
            print(f"Error processing {msg_file.name}: {e}")


def demo_group_chat():
    """Run a demo group chat between Alice, Bob, and Charlie."""

    # Clean up previous demo data
    if os.path.exists("./demo_data"):
        shutil.rmtree("./demo_data")
    if os.path.exists("./demo_queue"):
        shutil.rmtree("./demo_queue")

    os.makedirs("./demo_data", exist_ok=True)
    os.makedirs("./demo_queue/outbox", exist_ok=True)
    # Inboxes will be created automatically by MessageQueue

    print("=" * 60)
    print("ENCRYPTED MESSAGING APP DEMO - GROUP CHAT")
    print("=" * 60)
    print()
    print("This demo shows how Alice, Bob, and Charlie can")
    print("create a group and exchange encrypted messages.")
    print()

    # Step 1: Initialize Alice
    print("1. Setting up Alice...")
    sys.argv = [
        "main.py",
        "--username", "Alice",
        "--data-dir", "./demo_data/alice",
        "--queue-dir", "./demo_queue",
        "init"
    ]
    try:
        main()
    except SystemExit:
        pass  # main() calls sys.exit() which we need to catch

    # Get Alice's public key
    from messaging import SecureMessenger
    alice_messenger = SecureMessenger("Alice", "./demo_data/alice", "./demo_queue")
    _, alice_public_key_bytes, _ = alice_messenger.get_identity()
    alice_public_key = alice_public_key_bytes.hex()
    print(f"   Alice's public key: {alice_public_key[:32]}...")
    print()

    # Step 2: Initialize Bob
    print("2. Setting up Bob...")
    sys.argv = [
        "main.py",
        "--username", "Bob",
        "--data-dir", "./demo_data/bob",
        "--queue-dir", "./demo_queue",
        "init"
    ]
    try:
        main()
    except SystemExit:
        pass

    # Get Bob's public key
    bob_messenger = SecureMessenger("Bob", "./demo_data/bob", "./demo_queue")
    _, bob_public_key_bytes, _ = bob_messenger.get_identity()
    bob_public_key = bob_public_key_bytes.hex()
    print(f"   Bob's public key: {bob_public_key[:32]}...")
    print()

    # Step 3: Initialize Charlie
    print("3. Setting up Charlie...")
    sys.argv = [
        "main.py",
        "--username", "Charlie",
        "--data-dir", "./demo_data/charlie",
        "--queue-dir", "./demo_queue",
        "init"
    ]
    try:
        main()
    except SystemExit:
        pass

    # Get Charlie's public key
    charlie_messenger = SecureMessenger("Charlie", "./demo_data/charlie", "./demo_queue")
    _, charlie_public_key_bytes, _ = charlie_messenger.get_identity()
    charlie_public_key = charlie_public_key_bytes.hex()
    print(f"   Charlie's public key: {charlie_public_key[:32]}...")
    print()

    # Step 4: Alice adds Bob and Charlie as contacts
    print("4. Alice adds Bob and Charlie as contacts...")
    sys.argv = [
        "main.py",
        "--username", "Alice",
        "--data-dir", "./demo_data/alice",
        "--queue-dir", "./demo_queue",
        "add-contact", "Bob", bob_public_key
    ]
    try:
        main()
    except SystemExit:
        pass

    sys.argv = [
        "main.py",
        "--username", "Alice",
        "--data-dir", "./demo_data/alice",
        "--queue-dir", "./demo_queue",
        "add-contact", "Charlie", charlie_public_key
    ]
    try:
        main()
    except SystemExit:
        pass
    print("   Alice added Bob and Charlie as contacts.")
    print()

    # Step 5: Bob adds Alice and Charlie as contacts
    print("5. Bob adds Alice and Charlie as contacts...")
    sys.argv = [
        "main.py",
        "--username", "Bob",
        "--data-dir", "./demo_data/bob",
        "--queue-dir", "./demo_queue",
        "add-contact", "Alice", alice_public_key
    ]
    try:
        main()
    except SystemExit:
        pass

    sys.argv = [
        "main.py",
        "--username", "Bob",
        "--data-dir", "./demo_data/bob",
        "--queue-dir", "./demo_queue",
        "add-contact", "Charlie", charlie_public_key
    ]
    try:
        main()
    except SystemExit:
        pass
    print("   Bob added Alice and Charlie as contacts.")
    print()

    # Step 6: Charlie adds Alice and Bob as contacts
    print("6. Charlie adds Alice and Bob as contacts...")
    sys.argv = [
        "main.py",
        "--username", "Charlie",
        "--data-dir", "./demo_data/charlie",
        "--queue-dir", "./demo_queue",
        "add-contact", "Alice", alice_public_key
    ]
    try:
        main()
    except SystemExit:
        pass

    sys.argv = [
        "main.py",
        "--username", "Charlie",
        "--data-dir", "./demo_data/charlie",
        "--queue-dir", "./demo_queue",
        "add-contact", "Bob", bob_public_key
    ]
    try:
        main()
    except SystemExit:
        pass
    print("   Charlie added Alice and Bob as contacts.")
    print()

    # Step 7: Alice creates a group with Bob and Charlie
    print("7. Alice creates a group 'Team' with Bob and Charlie...")
    sys.argv = [
        "main.py",
        "--username", "Alice",
        "--data-dir", "./demo_data/alice",
        "--queue-dir", "./demo_queue",
        "create-group", "Team", "Bob", "Charlie"
    ]
    try:
        main()
    except SystemExit:
        pass
    print("   Group 'Team' created successfully.")
    print()

    # Also create the group for Bob and Charlie (groups are local in this prototype)
    print("   Creating group for Bob...")
    sys.argv = [
        "main.py",
        "--username", "Bob",
        "--data-dir", "./demo_data/bob",
        "--queue-dir", "./demo_queue",
        "create-group", "Team", "Alice", "Charlie"
    ]
    try:
        main()
    except SystemExit:
        pass

    print("   Creating group for Charlie...")
    sys.argv = [
        "main.py",
        "--username", "Charlie",
        "--data-dir", "./demo_data/charlie",
        "--queue-dir", "./demo_queue",
        "create-group", "Team", "Alice", "Bob"
    ]
    try:
        main()
    except SystemExit:
        pass
    print("   Group 'Team' created for all members.")
    print()

    # Step 8: Alice sends a group message
    print("8. Alice sends a message to the group 'Team'...")
    sys.argv = [
        "main.py",
        "--username", "Alice",
        "--data-dir", "./demo_data/alice",
        "--queue-dir", "./demo_queue",
        "send", "Team", "Hello Team! This is an encrypted group message from Alice."
    ]
    try:
        main()
    except SystemExit:
        pass
    print("   Group message queued for sending.")
    print()

    # Step 9: Simulate network transport
    print("9. Simulating network transport...")
    simulate_delivery("./demo_queue", {"Team": ["Alice", "Bob", "Charlie"]}, 0.1)
    print("   Messages delivered to recipients' inboxes.")
    print()

    # Step 10: Bob receives and decrypts the group message
    print("10. Bob receives and decrypts the group message...")
    sys.argv = [
        "main.py",
        "--username", "Bob",
        "--data-dir", "./demo_data/bob",
        "--queue-dir", "./demo_queue",
        "receive"
    ]
    try:
        main()
    except SystemExit:
        pass
    print()

    # Step 11: Charlie receives and decrypts the group message
    print("11. Charlie receives and decrypts the group message...")
    sys.argv = [
        "main.py",
        "--username", "Charlie",
        "--data-dir", "./demo_data/charlie",
        "--queue-dir", "./demo_queue",
        "receive"
    ]
    try:
        main()
    except SystemExit:
        pass
    print()

    # Step 12: Bob replies to the group
    print("12. Bob replies to the group...")
    sys.argv = [
        "main.py",
        "--username", "Bob",
        "--data-dir", "./demo_data/bob",
        "--queue-dir", "./demo_queue",
        "send", "Team", "Hi Alice and Charlie! I received Alice's message. This is Bob's reply."
    ]
    try:
        main()
    except SystemExit:
        pass
    print("   Reply queued for sending.")
    print()

    # Step 13: Simulate network transport for reply
    print("13. Simulating network transport for reply...")
    simulate_delivery("./demo_queue", {"Team": ["Alice", "Bob", "Charlie"]}, 0.1)
    print("   Reply delivered to recipients' inboxes.")
    print()

    # Step 14: Alice receives and decrypts Bob's reply
    print("14. Alice receives and decrypts Bob's reply...")
    sys.argv = [
        "main.py",
        "--username", "Alice",
        "--data-dir", "./demo_data/alice",
        "--queue-dir", "./demo_queue",
        "receive"
    ]
    try:
        main()
    except SystemExit:
        pass
    print()

    # Step 15: Charlie receives and decrypts Bob's reply
    print("15. Charlie receives and decrypts Bob's reply...")
    sys.argv = [
        "main.py",
        "--username", "Charlie",
        "--data-dir", "./demo_data/charlie",
        "--queue-dir", "./demo_queue",
        "receive"
    ]
    try:
        main()
    except SystemExit:
        pass
    print()

    # Step 16: Show conversation history for Alice
    print("16. Conversation history for Alice:")
    print("   Individual chat with Bob:")
    sys.argv = [
        "main.py",
        "--username", "Alice",
        "--data-dir", "./demo_data/alice",
        "--queue-dir", "./demo_queue",
        "history", "Bob"
    ]
    try:
        main()
    except SystemExit:
        pass
    print()

    print("   Group chat with Team:")
    sys.argv = [
        "main.py",
        "--username", "Alice",
        "--data-dir", "./demo_data/alice",
        "--queue-dir", "./demo_queue",
        "history", "Team"
    ]
    try:
        main()
    except SystemExit:
        pass
    print()

    # Step 17: List conversations
    print("17. Listing Alice's conversations...")
    sys.argv = [
        "main.py",
        "--username", "Alice",
        "--data-dir", "./demo_data/alice",
        "--queue-dir", "./demo_queue",
        "list-convos"
    ]
    try:
        main()
    except SystemExit:
        pass
    print()

    # Step 18: List groups
    print("18. Listing Alice's groups...")
    sys.argv = [
        "main.py",
        "--username", "Alice",
        "--data-dir", "./demo_data/alice",
        "--queue-dir", "./demo_queue",
        "list-groups"
    ]
    try:
        main()
    except SystemExit:
        pass
    print()

    print("=" * 60)
    print("GROUP CHAT DEMO COMPLETE")
    print("=" * 60)
    print()
    print("Notice how:")
    print("- Group messages are encrypted end-to-end using pairwise encryption")
    print("- Each member receives and can decrypt the group messages")
    print("- Forward secrecy is maintained through ephemeral keys")
    print("- Identity keys are long-term and used for authentication")
    print("- The same group name is used as recipient for all members")
    print()
    print("Demo data stored in:")
    print("  - ./demo_data/alice/ (Alice's data)")
    print("  - ./demo_data/bob/ (Bob's data)")
    print("  - ./demo_data/charlie/ (Charlie's data)")
    print("  - ./demo_queue/ (shared message queue with per-user inboxes)")


def demo_individual_chat():
    """Run the original demo conversation between Alice and Bob."""

    # Clean up previous demo data
    if os.path.exists("./demo_data_individual"):
        shutil.rmtree("./demo_data_individual")
    if os.path.exists("./demo_queue_individual"):
        shutil.rmtree("./demo_queue_individual")

    os.makedirs("./demo_data_individual", exist_ok=True)
    os.makedirs("./demo_queue_individual", exist_ok=True)

    print("=" * 60)
    print("ENCRYPTED MESSAGING APP DEMO - INDIVIDUAL CHAT")
    print("=" * 60)
    print()
    print("This demo shows how Alice and Bob can exchange")
    print("encrypted messages using the prototype.")
    print()

    # Step 1: Initialize Alice
    print("1. Setting up Alice...")
    sys.argv = [
        "main.py",
        "--username", "Alice",
        "--data-dir", "./demo_data_individual/alice",
        "--queue-dir", "./demo_queue_individual",
        "init"
    ]
    try:
        main()
    except SystemExit:
        pass  # main() calls sys.exit() which we need to catch

    # Get Alice's public key
    from messaging import SecureMessenger
    alice_messenger = SecureMessenger("Alice", "./demo_data_individual/alice", "./demo_queue_individual")
    _, alice_public_key_bytes, _ = alice_messenger.get_identity()
    alice_public_key = alice_public_key_bytes.hex()
    print(f"   Alice's public key: {alice_public_key[:32]}...")
    print()

    # Step 2: Initialize Bob
    print("2. Setting up Bob...")
    sys.argv = [
        "main.py",
        "--username", "Bob",
        "--data-dir", "./demo_data_individual/bob",
        "--queue-dir", "./demo_queue_individual",
        "init"
    ]
    try:
        main()
    except SystemExit:
        pass

    # Get Bob's public key
    bob_messenger = SecureMessenger("Bob", "./demo_data_individual/bob", "./demo_queue_individual")
    _, bob_public_key_bytes, _ = bob_messenger.get_identity()
    bob_public_key = bob_public_key_bytes.hex()
    print(f"   Bob's public key: {bob_public_key[:32]}...")
    print()

    # Step 3: Alice adds Bob as contact
    print("3. Alice adds Bob as contact...")
    sys.argv = [
        "main.py",
        "--username", "Alice",
        "--data-dir", "./demo_data_individual/alice",
        "--queue-dir", "./demo_queue_individual",
        "add-contact", "Bob", bob_public_key
    ]
    try:
        main()
    except SystemExit:
        pass
    print("   Alice added Bob's public key.")
    print()

    # Step 4: Bob adds Alice as contact
    print("4. Bob adds Alice as contact...")
    sys.argv = [
        "main.py",
        "--username", "Bob",
        "--data-dir", "./demo_data_individual/bob",
        "--queue-dir", "./demo_queue_individual",
        "add-contact", "Alice", alice_public_key
    ]
    try:
        main()
    except SystemExit:
        pass
    print("   Bob added Alice's public key.")
    print()

    # Step 5: Alice sends a message to Bob
    print("5. Alice sends a message to Bob...")
    sys.argv = [
        "main.py",
        "--username", "Alice",
        "--data-dir", "./demo_data_individual/alice",
        "--queue-dir", "./demo_queue_individual",
        "send", "Bob", "Hello Bob! This is an encrypted message from Alice."
    ]
    try:
        main()
    except SystemExit:
        pass
    print("   Message queued for sending.")
    print()

    # Step 6: Simulate network transport
    print("6. Simulating network transport...")
    simulate_delivery("./demo_queue_individual", {}, 0.1)
    print("   Message delivered to Bob's inbox.")
    print()

    # Step 7: Bob receives and decrypts the message
    print("7. Bob receives and decrypts the message...")
    sys.argv = [
        "main.py",
        "--username", "Bob",
        "--data-dir", "./demo_data_individual/bob",
        "--queue-dir", "./demo_queue_individual",
        "receive"
    ]
    try:
        main()
    except SystemExit:
        pass
    print()

    # Step 8: Bob replies to Alice
    print("8. Bob replies to Alice...")
    sys.argv = [
        "main.py",
        "--username", "Bob",
        "--data-dir", "./demo_data_individual/bob",
        "--queue-dir", "./demo_queue_individual",
        "send", "Alice", "Hi Alice! I received your message securely. This is my reply."
    ]
    try:
        main()
    except SystemExit:
        pass
    print("   Reply queued for sending.")
    print()

    # Step 9: Simulate network transport again
    print("9. Simulating network transport for reply...")
    simulate_delivery("./demo_queue_individual", {}, 0.1)
    print("   Reply delivered to Alice's inbox.")
    print()

    # Step 10: Alice receives and decrypts Bob's reply
    print("10. Alice receives and decrypts Bob's reply...")
    sys.argv = [
        "main.py",
        "--username", "Alice",
        "--data-dir", "./demo_data_individual/alice",
        "--queue-dir", "./demo_queue_individual",
        "receive"
    ]
    try:
        main()
    except SystemExit:
        pass
    print()

    # Step 11: Show conversation history
    print("11. Conversation history for Alice:")
    sys.argv = [
        "main.py",
        "--username", "Alice",
        "--data-dir", "./demo_data_individual/alice",
        "--queue-dir", "./demo_queue_individual",
        "history", "Bob"
    ]
    try:
        main()
    except SystemExit:
        pass
    print()

    print("12. Conversation history for Bob:")
    sys.argv = [
        "main.py",
        "--username", "Bob",
        "--data-dir", "./demo_data_individual/bob",
        "--queue-dir", "./demo_queue_individual",
        "history", "Alice"
    ]
    try:
        main()
    except SystemExit:
        pass
    print()

    print("=" * 60)
    print("INDIVIDUAL CHAT DEMO COMPLETE")
    print("=" * 60)
    print()
    print("Notice how:")
    print("- Messages are encrypted end-to-end")
    print("- Only Alice and Bob can read each other's messages")
    print("- Each message uses ephemeral keys for forward secrecy")
    print("- Identity keys are long-term and used for authentication")
    print()
    print("Demo data stored in:")
    print("  - ./demo_data_individual/alice/ (Alice's data)")
    print("  - ./demo_data_individual/bob/ (Bob's data)")
    print("  - ./demo_queue_individual/ (message queue simulation)")


if __name__ == "__main__":
    print("Select demo mode:")
    print("1. Individual chat (Alice & Bob)")
    print("2. Group chat (Alice, Bob, & Charlie)")
    print()

    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "2":
        demo_group_chat()
    else:
        demo_individual_chat()