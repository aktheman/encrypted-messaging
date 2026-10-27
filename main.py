"""
Main entry point for the encrypted messaging app.
Provides a command-line interface for sending and receiving encrypted messages.
"""

import argparse
import sys
import time
from pathlib import Path

# Import local modules
try:
    # When run as module
    from .messaging import SecureMessenger, MessageQueue
except ImportError:
    # When run directly as script
    from messaging import SecureMessenger, MessageQueue


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Encrypted Messaging App - A CLI-based prototype for end-to-end encrypted messaging"
    )
    parser.add_argument(
        "--username", "-u",
        required=True,
        help="Your username for this messaging instance"
    )
    parser.add_argument(
        "--data-dir",
        default="./data",
        help="Directory to store identity and data (default: ./data)"
    )
    parser.add_argument(
        "--queue-dir",
        default="./queue",
        help="Directory for message queue simulation (default: ./queue)"
    )
    # Networking options
    parser.add_argument(
        "--networking", "-n",
        action="store_true",
        help="Use WebSocket networking instead of file-based queue"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="WebSocket host (default: localhost)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8765,
        help="WebSocket port (default: 8765)"
    )
    parser.add_argument(
        "--server", "-s",
        action="store_true",
        help="Run as WebSocket server (required for one instance in a network)"
    )
    parser.add_argument(
        "--secure",
        action="store_true",
        help="Use secure WebSocket connections (wss://) with TLS encryption"
    )

    # Authentication options
    parser.add_argument(
        "--auth-method",
        choices=["tofu", "cert"],
        default="tofu",
        help="Authentication method to use (default: tofu)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Init command (generate identity)
    init_parser = subparsers.add_parser("init", help="Generate and save identity key pair")

    # Add contact command
    add_contact_parser = subparsers.add_parser("add-contact", help="Add a contact")
    add_contact_parser.add_argument("name", help="Contact name/identifier")
    add_contact_parser.add_argument("public_key", help="Contact's X25519 public key in hex format")
    add_contact_parser.add_argument("--signing-key", help="Contact's Ed25519 signing public key in hex format (optional)")

    # List contacts command
    subparsers.add_parser("list-contacts", help="List all stored contacts")

    # List pending contacts command (TOFU)
    pending_parser = subparsers.add_parser("pending-contacts", help="List pending contact requests")

    # Trust contact command (TOFU)
    trust_parser = subparsers.add_parser("trust-contact", help="Trust a pending contact")
    trust_parser.add_argument("name", help="Contact name to trust")

    # Block contact command (TOFU)
    block_parser = subparsers.add_parser("block-contact", help="Block a contact")
    block_parser.add_argument("name", help="Contact name to block")

    # Remove contact command
    remove_parser = subparsers.add_parser("remove-contact", help="Remove a contact")
    remove_parser.add_argument("name", help="Contact name to remove")

    # Group management commands
    # Create group
    create_group_parser = subparsers.add_parser("create-group", help="Create a new group")
    create_group_parser.add_argument("group_name", help="Name of the group")
    create_group_parser.add_argument("members", nargs="+", help="List of member usernames")

    # Add group member
    add_group_member_parser = subparsers.add_parser("add-group-member", help="Add a member to a group")
    add_group_member_parser.add_argument("group_name", help="Name of the group")
    add_group_member_parser.add_argument("member_name", help="Username to add")

    # Remove group member
    remove_group_member_parser = subparsers.add_parser("remove-group-member", help="Remove a member from a group")
    remove_group_member_parser.add_argument("group_name", help="Name of the group")
    remove_group_member_parser.add_argument("member_name", help="Username to remove")

    # List group members
    list_group_members_parser = subparsers.add_parser("list-group-members", help="List members of a group")
    list_group_members_parser.add_argument("group_name", help="Name of the group")

    # List groups
    subparsers.add_parser("list-groups", help="List all groups")

    # Delete group
    delete_group_parser = subparsers.add_parser("delete-group", help="Delete a group")
    delete_group_parser.add_argument("group_name", help="Name of the group")

    # Send message command
    send_parser = subparsers.add_parser("send", help="Send an encrypted message")
    send_parser.add_argument("recipient", help="Recipient name (can be individual or group)")
    send_parser.add_argument("message", help="Message to send")
    send_parser.add_argument(
        "--ttl",
        type=int,
        help="Time-to-live in seconds for ephemeral messages (default: permanent)"
    )

    # Edit message command
    edit_parser = subparsers.add_parser("edit-message", help="Edit a previously sent message")
    edit_parser.add_argument("recipient", help="Recipient name (can be individual or group)")
    edit_parser.add_argument("message", help="New message content")
    edit_parser.add_argument(
        "--ttl",
        type=int,
        help="Time-to-live in seconds for ephemeral messages (default: permanent)"
    )
    edit_parser.add_argument(
        "--edit-of",
        required=True,
        help="Timestamp of the message to edit (from history output)"
    )

    # Delete message command
    delete_parser = subparsers.add_parser("delete-message", help="Delete a previously sent message")
    delete_parser.add_argument("recipient", help="Recipient name (can be individual or group)")
    delete_parser.add_argument(
        "--delete-of",
        required=True,
        help="Timestamp of the message to delete (from history output)"
    )

    # Receive messages command
    subparsers.add_parser("receive", help="Receive and decrypt waiting messages")

    # Conversation history command
    history_parser = subparsers.add_parser("history", help="Show conversation history")
    history_parser.add_argument("contact", help="Contact name or group name")
    history_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=50,
        help="Maximum number of messages to show (default: 50)"
    )

    # List conversations command
    subparsers.add_parser("list-convos", help="List all conversations")

    # Simulate network command (for testing)
    simulate_parser = subparsers.add_parser("simulate", help="Simulate network transport")
    simulate_parser.add_argument(
        "--delay", "-d",
        type=float,
        default=0.5,
        help="Network delay in seconds (default: 0.5)"
    )

    args = parser.parse_args()

    # If no command provided, show help
    if not args.command:
        parser.print_help()
        return

    try:
        # Initialize messenger
        messenger = SecureMessenger(
            username=args.username,
            data_dir=args.data_dir,
            queue_dir=args.queue_dir,
            use_networking=args.networking,
            host=args.host,
            port=args.port,
            is_server=args.server,
            auth_method=args.auth_method,
            secure=args.secure
        )

        # Handle commands
        if args.command == "init":
            # Identity is generated automatically in __init__
            private_key_bytes, public_key_bytes, username = messenger.get_identity()
            print(f"Identity for {username} is ready.")
            print(f"Your public key (share this with contacts): {public_key_bytes.hex()}")

        elif args.command == "add-contact":
            messenger.add_contact(args.name, args.public_key, args.signing_key)
            if args.signing_key:
                print(f"Contact '{args.name}' added successfully with signing key.")
            else:
                print(f"Contact '{args.name}' added successfully (no signing key provided).")

        elif args.command == "list-contacts":
            contacts = messenger.list_contacts()
            if contacts:
                print("Stored contacts:")
                for name, pubkey_hex in contacts.items():
                    trust_level = messenger.contact_manager.get_contact_trust_level(name)
                    trust_symbol = "[BLOCKED]" if trust_level == 2 else "[TRUSTED]" if trust_level == 1 else "[UNKNOWN]"
                    print(f"  {trust_symbol} {name}: {pubkey_hex}")
            else:
                print("No contacts stored.")

        elif args.command == "pending-contacts":
            pending = messenger.get_pending_contacts()
            if pending:
                print("Pending contact requests:")
                for name, info in pending.items():
                    print(f"  {name}: {info['public_key']} (first seen: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info.get('first_seen', 0)))}")
            else:
                print("No pending contact requests.")

        elif args.command == "trust-contact":
            success = messenger.trust_contact(args.name)
            if success:
                print(f"Contact '{args.name}' is now trusted.")
            else:
                print(f"Failed to trust contact '{args.name}'. Contact may not exist.")

        elif args.command == "block-contact":
            success = messenger.block_contact(args.name)
            if success:
                print(f"Contact '{args.name}' is now blocked.")
            else:
                print(f"Failed to block contact '{args.name}'. Contact may not exist.")

        elif args.command == "remove-contact":
            success = messenger.remove_contact(args.name)
            if success:
                print(f"Contact '{args.name}' removed successfully.")
            else:
                print(f"Failed to remove contact '{args.name}'. Contact may not exist.")

        # Group management commands
        elif args.command == "create-group":
            success = messenger.create_group(args.group_name, args.members)
            if success:
                print(f"Group '{args.group_name}' created successfully with members: {', '.join(args.members)}")
            else:
                print(f"Failed to create group '{args.group_name}'. Group may already exist or some members not found.")

        elif args.command == "add-group-member":
            success = messenger.add_group_member(args.group_name, args.member_name)
            if success:
                print(f"Member '{args.member_name}' added to group '{args.group_name}'.")
            else:
                print(f"Failed to add member '{args.member_name}' to group '{args.group_name}'. Group or member may not exist.")

        elif args.command == "remove-group-member":
            success = messenger.remove_group_member(args.group_name, args.member_name)
            if success:
                print(f"Member '{args.member_name}' removed from group '{args.group_name}'.")
            else:
                print(f"Failed to remove member '{args.member_name}' from group '{args.group_name}'. Group or member may not exist.")

        elif args.command == "list-group-members":
            members = messenger.get_group_members(args.group_name)
            if members:
                print(f"Members of group '{args.group_name}': {', '.join(members)}")
            else:
                print(f"Group '{args.group_name}' not found or has no members.")

        elif args.command == "list-groups":
            groups = messenger.list_groups()
            if groups:
                print("Stored groups:")
                for group_name, info in groups.items():
                    members = ", ".join(info["members"])
                    print(f"  {group_name}: [{members}] (created: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info['created_at']))})")
            else:
                print("No groups stored.")

        elif args.command == "delete-group":
            success = messenger.delete_group(args.group_name)
            if success:
                print(f"Group '{args.group_name}' deleted successfully.")
            else:
                print(f"Failed to delete group '{args.group_name}'. Group may not exist.")

        elif args.command == "send":
            success = messenger.send_message(args.recipient, args.message, ttl=args.ttl)
            if success:
                if args.ttl is not None:
                    print(f"Message sent to {args.recipient} (will expire in {args.ttl} seconds).")
                else:
                    print(f"Message sent to {args.recipient}.")
            else:
                print(f"Failed to send message to {args.recipient}.")
                sys.exit(1)

        elif args.command == "edit-message":
            # Parse the timestamp of the message to edit
            try:
                edit_timestamp = float(args.edit_of)
            except ValueError:
                print("Error: --edit-of must be a valid timestamp (number)")
                sys.exit(1)

            # Get conversation info to find the message
            is_group = args.recipient in messenger.contact_manager.load_groups()
            conversation = messenger.message_store.get_conversation_info(args.recipient, is_group=is_group)
            if conversation is None:
                print(f"Error: No conversation found with {args.recipient}")
                sys.exit(1)

            # Get messages to find the one with the specified timestamp
            messages = messenger.message_store.get_messages(conversation['id'], limit=1000)  # Get a reasonable number
            target_message = None
            for msg in messages:
                if abs(msg['timestamp'] - edit_timestamp) < 1:  # Allow small difference due to integer conversion
                    target_message = msg
                    break

            if target_message is None:
                print(f"Error: Could not find message with timestamp {edit_timestamp} in conversation with {args.recipient}")
                sys.exit(1)

            # Create the edit-of tuple
            edit_of_tuple = (target_message['sender_name'], target_message['recipient_name'], target_message['timestamp'])

            # Send the edit message
            success = messenger.send_message(args.recipient, args.message, ttl=args.ttl, edit_of=edit_of_tuple)
            if success:
                if args.ttl is not None:
                    print(f"Edit sent to {args.recipient} (will expire in {args.ttl} seconds).")
                else:
                    print(f"Edit sent to {args.recipient}.")
            else:
                print(f"Failed to send edit to {args.recipient}.")
                sys.exit(1)

        elif args.command == "delete-message":
            # Parse the timestamp of the message to delete
            try:
                delete_timestamp = float(args.delete_of)
            except ValueError:
                print("Error: --delete-of must be a valid timestamp (number)")
                sys.exit(1)

            # Get conversation info to find the message
            is_group = args.recipient in messenger.contact_manager.load_groups()
            conversation = messenger.message_store.get_conversation_info(args.recipient, is_group=is_group)
            if conversation is None:
                print(f"Error: No conversation found with {args.recipient}")
                sys.exit(1)

            # Get messages to find the one with the specified timestamp
            messages = messenger.message_store.get_messages(conversation['id'], limit=1000)  # Get a reasonable number
            target_message = None
            for msg in messages:
                if abs(msg['timestamp'] - delete_timestamp) < 1:  # Allow small difference due to integer conversion
                    target_message = msg
                    break

            if target_message is None:
                print(f"Error: Could not find message with timestamp {delete_timestamp} in conversation with {args.recipient}")
                sys.exit(1)

            # Create the delete-of tuple
            delete_of_tuple = (target_message['sender_name'], target_message['recipient_name'], target_message['timestamp'])

            # Send the delete message
            success = messenger.send_message(args.recipient, "", ttl=args.ttl, delete_of=delete_of_tuple)  # Empty message content
            if success:
                if args.ttl is not None:
                    print(f"Delete sent to {args.recipient} (will expire in {args.ttl} seconds).")
                else:
                    print(f"Delete sent to {args.recipient}.")
            else:
                print(f"Failed to send delete to {args.recipient}.")
                sys.exit(1)

        elif args.command == "receive":
            messages = messenger.receive_and_process_messages()
            if messages:
                print("Received messages:")
                for sender, text in messages:
                    print(f"  From {sender}: {text}")
            else:
                print("No new messages.")

        elif args.command == "history":
            history = messenger.get_conversation_history(args.contact, args.limit)
            if history:
                print(f"Conversation history with {args.contact}:")
                for msg in history:
                    direction_arrow = ">>" if msg['direction'] == 'sent' else "<<"
                    timestamp = time.strftime("%H:%M:%S", time.localtime(msg['timestamp']))
                    group_indicator = " [GROUP]" if msg['is_group'] else ""
                    print(f"  [{timestamp}] {direction_arrow} {msg['text']}{group_indicator}")
            else:
                print(f"No conversation history with {args.contact}.")

        elif args.command == "list-convos":
            conversations = messenger.message_store.list_conversations()
            if conversations:
                print("Conversations:")
                for conv in conversations:
                    conv_type = "Group" if conv['is_group'] else "Contact"
                    if conv['last_message_time']:
                        last_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(conv['last_message_time']))
                    else:
                        last_time = "Never"
                    print(f"  {conv['contact_name']} ({conv_type}, {conv['message_count']} messages, last: {last_time})")
            else:
                print("No conversations found.")

        elif args.command == "simulate":
            # Only applicable in file-based mode
            if args.networking:
                print("Warning: --simulate is only available in file-based mode.")
                print("Networking mode handles delays automatically.")
            else:
                print(f"Simulating network transport with {args.delay}s delay...")
                queue = MessageQueue(args.queue_dir)
                # Move messages from outbox to inbox with delay
                outbox_path = Path(args.queue_dir) / "outbox"
                if outbox_path.exists():
                    for msg_file in outbox_path.glob("*.msg"):
                        try:
                            with open(msg_file, 'r') as f:
                                message_json = f.read()
                            # Simulate delay
                            time.sleep(args.delay)
                            # Move to inbox
                            inbox_path = Path(args.queue_dir) / "inbox" / msg_file.name
                            inbox_path.write_text(message_json)
                            msg_file.unlink()
                            print(f"Delivered: {msg_file.name}")
                        except Exception as e:
                            print(f"Error processing {msg_file.name}: {e}")
                else:
                    print("No outbox directory found.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()