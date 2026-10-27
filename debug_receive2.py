#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, '.')

from messaging import SecureMessenger, MessageQueue
from crypto import decrypt_message

def debug_receive_messages():
    """Debug version of receive_and_process_messages with extra prints."""
    print("Creating SecureMessenger for Bob...")
    bob = SecureMessenger('bob', './data/bob', './queue')
    print("SecureMessenger created")

    # Check inbox directly first
    inbox_path = './queue/inbox'
    print(f"Checking inbox directory: {os.path.abspath(inbox_path)}")
    if os.path.exists(inbox_path):
        files = os.listdir(inbox_path)
        print(f"Files in inbox: {files}")
        if files:
            print("Contents of first message file:")
            with open(os.path.join(inbox_path, files[0]), 'r') as f:
                print(f.read())
    else:
        print("Inbox directory does not exist")

    print("\nChecking for messages in queue via MessageQueue...")
    received_messages = bob.message_queue.receive_messages()
    print(f"Found {len(received_messages)} messages in queue")

    if len(received_messages) == 0:
        print("No messages to process")
        return []

    print("Processing messages...")
    decrypted_messages = []

    for i, message in enumerate(received_messages):
        print(f"\nProcessing message {i+1}:")
        print(f"  Sender: {message.sender_name}")
        print(f"  Recipient: {message.recipient_name}")
        print(f"  Timestamp: {message.timestamp}")

        try:
            # Check if message is intended for us
            print(f"  Checking if message is for {bob.username}...")
            if message.recipient_name != bob.username:
                print(f"  Message not for us (expected {bob.username}, got {message.recipient_name}), skipping")
                continue
            print("  Message is for us")

            # Get our identity for decryption
            print("  Getting our identity...")
            our_private_key_bytes, _, _ = bob.get_identity()
            print(f"  Our private key bytes: {our_private_key_bytes.hex()[:32]}...")

            from crypto import deserialize_private_key
            our_private_key = deserialize_private_key(our_private_key_bytes)
            print("  Our private key deserialized")

            # Get sender's public key from contacts
            print(f"  Looking up contact '{message.sender_name}'...")
            sender_public_key_bytes = bob.get_contact_public_key(message.sender_name)
            if sender_public_key_bytes is None:
                # If we don't have the sender in contacts, we can't decrypt (security feature)
                print(f"  Warning: Received message from unknown contact '{message.sender_name}'. Skipping.")
                continue
            print(f"  Sender public key bytes: {sender_public_key_bytes.hex()[:32]}...")

            from crypto import deserialize_public_key
            sender_public_key = deserialize_public_key(sender_public_key_bytes)
            print("  Sender public key deserialized")

            # Get ephemeral public key from message
            print("  Getting ephemeral public key from message...")
            sender_eph_public_key = deserialize_public_key(message.ephemeral_public_key)
            print("  Ephemeral public key deserialized")

            # Perform DH key exchange: our identity private + sender's ephemeral public
            print("  Performing DH key exchange (our private + sender ephemeral)...")
            from crypto import perform_dh_key_exchange
            shared_secret_eph = perform_dh_key_exchange(our_private_key, sender_eph_public_key)
            print("  DH key exchange (our private + sender ephemeral) completed")

            # Perform DH key exchange: our identity private + sender's identity public
            print("  Performing DH key exchange (our private + sender identity)...")
            shared_secret_id = perform_dh_key_exchange(our_private_key, sender_public_key)
            print("  DH key exchange (our private + sender identity) completed")

            # Combine secrets for key derivation (must match sender's process)
            print("  Combining secrets...")
            combined_secret = shared_secret_eph + shared_secret_id
            print("  Secrets combined")

            # Derive encryption key
            print("  Deriving encryption key...")
            from crypto import derive_key
            key, salt = derive_key(combined_secret)
            print("  Encryption key derived")

            # Decrypt message
            print("  Decrypting message...")
            plaintext_bytes = decrypt_message(
                key, message.nonce, message.ciphertext
            )
            plaintext = plaintext_bytes.decode('utf-8')
            print(f"  Decrypted message: '{plaintext}'")

            # Store received message locally
            print("  Storing received message locally...")
            conversation_id = bob.message_store.get_or_create_conversation(
                message.sender_name, sender_public_key_bytes
            )
            print(f"  Conversation ID: {conversation_id}")
            bob.message_store.save_message(
                conversation_id=conversation_id,
                direction='received',
                ciphertext=message.ciphertext,
                nonce=message.nonce,
                ephemeral_public_key=message.ephemeral_public_key,
                salt=message.salt,
                timestamp=int(message.timestamp),
                is_group=message.is_group,
                ttl=message.ttl,
                signature=message.signature
            )
            print("  Message stored locally")

            decrypted_messages.append((message.sender_name, plaintext))
            print(f"  Message {i+1} processed successfully")

        except Exception as e:
            print(f"  Error processing message from {message.sender_name}: {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"\nTotal decrypted messages: {len(decrypted_messages)}")
    return decrypted_messages

if __name__ == "__main__":
    result = debug_receive_messages()
    print(f"Final result: {result}")