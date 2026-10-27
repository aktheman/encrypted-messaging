#!/usr/bin/env python3

import sys
sys.path.insert(0, '.')

from messaging import SecureMessenger

def debug_send_message():
    """Debug version of send_message with extra prints."""
    print("Creating SecureMessenger for Alice...")
    alice = SecureMessenger('alice', './data/alice', './queue')
    print("SecureMessenger created")

    print("Getting identity...")
    our_private_key_bytes, our_public_key_bytes, _ = alice.get_identity()
    print(f"Identity retrieved: {our_private_key_bytes.hex()[:16]}...")

    from crypto import deserialize_private_key
    our_private_key = deserialize_private_key(our_private_key_bytes)
    print("Private key deserialized")

    print("Getting username...")
    our_username, _, _ = alice.get_identity()  # Get username too
    print(f"Username: {our_username}")

    print("Getting Bob's public key...")
    recipient_public_key_bytes = alice.get_contact_public_key('bob')
    if recipient_public_key_bytes is None:
        print("ERROR: Bob's public key not found!")
        return False
    print(f"Bob's public key retrieved: {recipient_public_key_bytes.hex()[:16]}...")

    from crypto import deserialize_public_key
    recipient_public_key = deserialize_public_key(recipient_public_key_bytes)
    print("Bob's public key deserialized")

    from crypto import generate_ephemeral_keypair, perform_dh_key_exchange, derive_key, encrypt_message, serialize_public_key
    print("Generating ephemeral key pair...")
    eph_private_key, eph_public_key = generate_ephemeral_keypair()
    print("Ephemeral key pair generated")

    print("Performing DH key exchange (ephemeral)...")
    shared_secret_eph = perform_dh_key_exchange(eph_private_key, recipient_public_key)
    print("DH key exchange (ephemeral) completed")

    print("Performing DH key exchange (identity)...")
    shared_secret_id = perform_dh_key_exchange(our_private_key, recipient_public_key)
    print("DH key exchange (identity) completed")

    print("Combining secrets...")
    combined_secret = shared_secret_eph + shared_secret_id
    print("Secrets combined")

    print("Deriving encryption key...")
    key, salt = derive_key(combined_secret)
    print("Encryption key derived")

    print("Encrypting message...")
    plaintext = "Hello Bob! This is an encrypted message from Alice."
    plaintext_bytes = plaintext.encode('utf-8')
    nonce, ciphertext = encrypt_message(key, plaintext_bytes)
    print("Message encrypted")

    from messaging import Message
    print("Creating message object...")
    message = Message(
        sender_name=our_username,
        recipient_name='bob',
        ciphertext=ciphertext,
        nonce=nonce,
        ephemeral_public_key=serialize_public_key(eph_public_key)
    )
    print("Message object created")

    from messaging import MessageQueue
    print("Creating MessageQueue...")
    message_queue = MessageQueue('./queue')
    print("MessageQueue created")

    print("Sending message via queue...")
    success = message_queue.send_message(message)
    print(f"Queue send result: {success}")

    if success:
        from storage import MessageStore
        print("Storing message locally...")
        conversation_id = alice.message_store.get_or_create_conversation('bob', recipient_public_key_bytes)
        print(f"Conversation ID: {conversation_id}")
        alice.message_store.save_message(
            conversation_id=conversation_id,
            direction='sent',
            ciphertext=ciphertext,
            nonce=nonce,
            ephemeral_public_key=serialize_public_key(eph_public_key)
        )
        print("Message stored locally")

    return success

if __name__ == "__main__":
    result = debug_send_message()
    print(f"Overall result: {result}")