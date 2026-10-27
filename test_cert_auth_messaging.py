#!/usr/bin/env python3
"""
Test certificate-based authentication in the messaging layer.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from identity import IdentityManager
from messaging import SecureMessenger, Message
from crypto import generate_ephemeral_keypair, serialize_public_key, perform_dh_key_exchange, derive_key, encrypt_message
from messaging import Message

def test_cert_auth_trust_logic():
    """Test that certificate-based authentication automatically trusts contacts."""
    print("Testing certificate-based authentication trust logic...")

    # Create temporary directories for testing
    temp_dir = tempfile.mkdtemp()
    print(f"Using temporary directory: {temp_dir}")

    try:
        # Set up alice with certificate-based auth
        alice_data_dir = os.path.join(temp_dir, "alice_data")
        alice_identity_manager = IdentityManager(alice_data_dir)

        # Generate identity with certificate for Alice
        print("Generating identity with certificate for Alice...")
        ec_priv, ec_pub, x25519_priv, x25519_pub, alice_username, cert = alice_identity_manager.generate_and_save_identity_with_cert("alice")
        print(f"Generated identity for {alice_username}")

        # Set up bob (we'll simulate his identity)
        bob_data_dir = os.path.join(temp_dir, "bob_data")
        bob_identity_manager = IdentityManager(bob_data_dir)

        # Generate identity with certificate for Bob
        print("Generating identity with certificate for Bob...")
        bob_ec_priv, bob_ec_pub, bob_x25519_priv, bob_x25519_pub, bob_username, bob_cert = bob_identity_manager.generate_and_save_identity_with_cert("bob")
        print(f"Generated identity for {bob_username}")

        # Get Bob's identity details for message creation
        bob_ec_priv, bob_ec_pub, bob_x25519_priv, bob_x25519_pub, bob_user, bob_cert = bob_identity_manager.load_identity_with_cert()
        from crypto import deserialize_private_key, deserialize_public_key
        bob_priv_key = deserialize_private_key(bob_x25519_priv)  # X25519 private key for encryption
        bob_pub_key = deserialize_public_key(bob_x25519_pub)

        # Create SecureMessenger for Alice with certificate auth
        alice_messenger = SecureMessenger(
            username="alice",
            data_dir=alice_data_dir,
            queue_dir=os.path.join(temp_dir, "alice_queue"),
            use_networking=False,  # Use file-based for simplicity
            auth_method="cert"
        )

        # Initially, Alice should not have Bob in her contacts
        print("Checking initial contacts for Alice...")
        initial_contacts = alice_messenger.list_contacts()
        print(f"Alice's initial contacts: {initial_contacts}")
        assert "bob" not in initial_contacts, "Bob should not be in Alice's contacts initially"

        # Give Alice Bob's public key (simulating out-of-band exchange) but mark as unknown
        # This simulates having exchanged certificates or public keys through some secure channel
        alice_messenger.add_contact("bob", bob_x25519_pub.hex())

        # Simulate receiving a message from Bob
        print("Simulating receipt of message from Bob...")

        # Create a test message from Bob to Alice (as Bob would send it)
        # We need to encrypt it using Alice's public key and Bob's private key

        # Get Alice's public key from her identity
        alice_ec_priv, alice_ec_pub, alice_x25519_priv, alice_x25519_pub, alice_username, alice_cert = alice_identity_manager.load_identity_with_cert()
        from crypto import deserialize_private_key, deserialize_public_key
        alice_x25519_pub_key = deserialize_public_key(alice_x25519_pub)

        # Generate ephemeral key for Bob
        bob_eph_priv, bob_eph_pub = generate_ephemeral_keypair()

        # Perform DH key exchange (as Bob would do it)
        # shared_secret_eph = Bob's ephemeral private + Alice's identity public
        shared_secret_eph = perform_dh_key_exchange(bob_eph_priv, alice_x25519_pub_key)
        # shared_secret_id = Bob's identity private + Alice's identity public
        shared_secret_id = perform_dh_key_exchange(bob_priv_key, alice_x25519_pub_key)

        # Combine secrets and derive key
        combined_secret = shared_secret_eph + shared_secret_id
        key, salt = derive_key(combined_secret)

        # Encrypt message
        plaintext = b"Hello Alice from Bob!"
        nonce, ciphertext = encrypt_message(key, plaintext)

        # Create the message as Bob would send it
        import time
        bob_message = Message(
            sender_name="bob",
            recipient_name="alice",
            ciphertext=ciphertext,
            nonce=nonce,
            ephemeral_public_key=serialize_public_key(bob_eph_pub),
            salt=salt,
            timestamp=int(time.time()),
            is_group=False
        )

        # Put the message in Alice's inbox (simulating receipt)
        print("Putting message in Alice's inbox...")
        import time
        timestamp_str = str(int(time.time() * 1000000))  # microseconds
        import secrets
        random_str = secrets.token_hex(8)
        filename = f"{timestamp_str}_{random_str}.msg"
        filepath = alice_messenger.message_queue.inbox_dir / filename

        with open(filepath, 'w') as f:
            f.write(bob_message.to_json())

        print(f"Message saved to {filepath}")

        # Process the message with Alice's messenger
        print("Processing message with Alice's messenger...")
        decrypted_messages = alice_messenger.receive_and_process_messages()

        # Check that we got the message
        assert len(decrypted_messages) == 1, f"Expected 1 message, got {len(decrypted_messages)}"
        sender, plaintext_received = decrypted_messages[0]
        assert sender == "bob", f"Expected sender 'bob', got '{sender}'"
        assert plaintext_received == plaintext.decode('utf-8'), f"Plaintext mismatch"
        print(f"Successfully decrypted message from {sender}: {plaintext_received}")

        # Most importantly, check that Bob is now in Alice's contacts and trusted
        print("Checking Alice's contacts after message processing...")
        contacts_after = alice_messenger.list_contacts()
        print(f"Alice's contacts after processing: {contacts_after}")

        assert "bob" in contacts_after, "Bob should now be in Alice's contacts"
        trust_level = alice_messenger.contact_manager.get_contact_trust_level("bob")
        assert trust_level == 1, f"Bob should be trusted (level 1), but is level {trust_level}"

        print("Certificate-based authentication trust logic test passed!")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    if test_cert_auth_trust_logic():
        print("\n[PASS] Certificate-based authentication trust logic test passed!")
        sys.exit(0)
    else:
        print("\n[FAIL] Certificate-based authentication trust logic test failed!")
        sys.exit(1)