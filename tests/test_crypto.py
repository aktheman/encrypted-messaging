"""
Unit tests for cryptographic primitives.
"""
import pytest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto import (
    generate_identity_keypair,
    serialize_public_key,
    deserialize_public_key,
    serialize_private_key,
    deserialize_private_key,
    perform_dh_key_exchange,
    derive_key,
    encrypt_message,
    decrypt_message,
    create_message_keypair,
    # Ed25519 signing
    generate_signing_keypair,
    serialize_signing_public_key,
    deserialize_signing_public_key,
    serialize_signing_private_key,
    deserialize_signing_private_key,
    sign_message,
    verify_signature,
)
from cryptography.exceptions import InvalidTag


class TestX25519KeyGeneration:
    """Tests for X25519 key generation and serialization."""

    def test_generate_identity_keypair(self):
        """Test that identity keypair generation works."""
        private_key, public_key = generate_identity_keypair()
        assert private_key is not None
        assert public_key is not None

    def test_serialize_deserialize_public_key(self):
        """Test public key serialization round-trip."""
        _, public_key = generate_identity_keypair()
        serialized = serialize_public_key(public_key)
        deserialized = deserialize_public_key(serialized)
        assert serialize_public_key(deserialized) == serialized

    def test_serialize_deserialize_private_key(self):
        """Test private key serialization round-trip."""
        private_key, _ = generate_identity_keypair()
        serialized = serialize_private_key(private_key)
        deserialized = deserialize_private_key(serialized)
        assert serialize_private_key(deserialized) == serialized

    def test_perform_dh_key_exchange(self):
        """Test Diffie-Hellman key exchange produces same shared secret."""
        alice_private, alice_public = generate_identity_keypair()
        bob_private, bob_public = generate_identity_keypair()

        # Alice computes shared secret with Bob's public key
        alice_shared = perform_dh_key_exchange(alice_private, bob_public)
        # Bob computes shared secret with Alice's public key
        bob_shared = perform_dh_key_exchange(bob_private, alice_public)

        assert alice_shared == bob_shared
        assert len(alice_shared) == 32  # X25519 shared secret is 32 bytes

    def test_derive_key(self):
        """Test HKDF key derivation."""
        shared_secret = os.urandom(32)
        key1, salt1 = derive_key(shared_secret)
        key2, salt2 = derive_key(shared_secret, salt=salt1)

        # Same salt should produce same key
        assert key1 == key2
        assert len(key1) == 32  # AES-256 key
        assert len(salt1) == 16

        # Different salt should produce different key
        key3, _ = derive_key(shared_secret)
        assert key1 != key3

    def test_encrypt_decrypt_message(self):
        """Test AES-GCM encryption and decryption."""
        key = os.urandom(32)
        plaintext = b"Hello, encrypted world!"
        associated_data = b"header"

        nonce, ciphertext = encrypt_message(key, plaintext, associated_data)
        assert len(nonce) == 12
        assert len(ciphertext) == len(plaintext) + 16  # AES-GCM adds 16-byte tag

        decrypted = decrypt_message(key, nonce, ciphertext, associated_data)
        assert decrypted == plaintext

    def test_decrypt_with_wrong_key_fails(self):
        """Test that decryption fails with wrong key."""
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        plaintext = b"Secret message"

        nonce, ciphertext = encrypt_message(key1, plaintext)

        with pytest.raises(InvalidTag):
            decrypt_message(key2, nonce, ciphertext)

    def test_decrypt_with_wrong_nonce_fails(self):
        """Test that decryption fails with wrong nonce."""
        key = os.urandom(32)
        plaintext = b"Secret message"

        nonce1, ciphertext = encrypt_message(key, plaintext)
        nonce2 = os.urandom(12)

        with pytest.raises(InvalidTag):
            decrypt_message(key, nonce2, ciphertext)

    def test_decrypt_with_tampered_ciphertext_fails(self):
        """Test that decryption fails with tampered ciphertext."""
        key = os.urandom(32)
        plaintext = b"Secret message"

        nonce, ciphertext = encrypt_message(key, plaintext)
        # Tamper with ciphertext
        tampered = bytearray(ciphertext)
        tampered[0] ^= 0xFF

        with pytest.raises(InvalidTag):
            decrypt_message(key, nonce, bytes(tampered))

    def test_create_message_keypair(self):
        """Test message keypair creation."""
        identity_private, identity_public = generate_identity_keypair()
        peer_private, peer_public = generate_identity_keypair()

        result = create_message_keypair(identity_private, peer_public)

        assert 'key' in result
        assert 'salt' in result
        assert 'ephemeral_private_key' in result
        assert 'ephemeral_public_key' in result
        assert len(result['key']) == 32
        assert len(result['salt']) == 16


class TestEd25519Signing:
    """Tests for Ed25519 signing and verification."""

    def test_generate_signing_keypair(self):
        """Test Ed25519 keypair generation."""
        private_key, public_key = generate_signing_keypair()
        assert private_key is not None
        assert public_key is not None

    def test_serialize_deserialize_signing_public_key(self):
        """Test Ed25519 public key serialization round-trip."""
        _, public_key = generate_signing_keypair()
        serialized = serialize_signing_public_key(public_key)
        assert len(serialized) == 32  # Ed25519 public key is 32 bytes
        deserialized = deserialize_signing_public_key(serialized)
        assert serialize_signing_public_key(deserialized) == serialized

    def test_serialize_deserialize_signing_private_key(self):
        """Test Ed25519 private key serialization round-trip."""
        private_key, _ = generate_signing_keypair()
        serialized = serialize_signing_private_key(private_key)
        assert len(serialized) == 32  # Ed25519 private key is 32 bytes
        deserialized = deserialize_signing_private_key(serialized)
        assert serialize_signing_private_key(deserialized) == serialized

    def test_sign_verify_message(self):
        """Test message signing and verification."""
        private_key, public_key = generate_signing_keypair()
        message = b"Test message to sign"

        signature = sign_message(private_key, message)
        assert len(signature) == 64  # Ed25519 signature is 64 bytes

        # Verify with correct public key
        assert verify_signature(public_key, message, signature) is True

    def test_verify_with_wrong_key_fails(self):
        """Test that verification fails with wrong public key."""
        private_key1, _ = generate_signing_keypair()
        _, public_key2 = generate_signing_keypair()
        message = b"Test message"

        signature = sign_message(private_key1, message)

        # Verify with different public key should fail
        assert verify_signature(public_key2, message, signature) is False

    def test_verify_with_wrong_message_fails(self):
        """Test that verification fails with different message."""
        private_key, public_key = generate_signing_keypair()
        message1 = b"Original message"
        message2 = b"Different message"

        signature = sign_message(private_key, message1)

        # Verify with different message should fail
        assert verify_signature(public_key, message2, signature) is False

    def test_verify_with_tampered_signature_fails(self):
        """Test that verification fails with tampered signature."""
        private_key, public_key = generate_signing_keypair()
        message = b"Test message"

        signature = bytearray(sign_message(private_key, message))
        # Tamper with signature
        signature[0] ^= 0xFF

        assert verify_signature(public_key, message, bytes(signature)) is False


class TestCombinedOperations:
    """Tests for combined cryptographic operations."""

    def test_full_encryption_signing_workflow(self):
        """Test complete workflow: DH key exchange -> encrypt -> sign -> verify -> decrypt."""
        # Generate identities
        alice_identity_private, alice_identity_public = generate_identity_keypair()
        bob_identity_private, bob_identity_public = generate_identity_keypair()

        # Generate signing keys
        alice_signing_private, alice_signing_public = generate_signing_keypair()
        bob_signing_private, bob_signing_public = generate_signing_keypair()

        # Alice wants to send message to Bob
        # Generate ephemeral key
        alice_eph_private, alice_eph_public = generate_identity_keypair()

        # DH exchanges
        shared_eph = perform_dh_key_exchange(alice_eph_private, bob_identity_public)
        shared_id = perform_dh_key_exchange(alice_identity_private, bob_identity_public)
        combined = shared_eph + shared_id

        # Derive key
        key, salt = derive_key(combined)

        # Encrypt
        plaintext = b"Hello Bob, this is Alice!"
        nonce, ciphertext = encrypt_message(key, plaintext)

        # Create message envelope for signing
        timestamp = 1234567890
        recipient = b"Bob"
        is_group = b'\x00'
        message_data = (ciphertext + nonce + serialize_public_key(alice_eph_public) +
                       salt + timestamp.to_bytes(8, 'big') + recipient + is_group)

        # Sign
        signature = sign_message(alice_signing_private, message_data)

        # Bob receives and verifies
        # Recreate message data
        message_data_verify = (ciphertext + nonce + serialize_public_key(alice_eph_public) +
                              salt + timestamp.to_bytes(8, 'big') + recipient + is_group)
        assert verify_signature(alice_signing_public, message_data_verify, signature)

        # Bob derives same key
        bob_shared_eph = perform_dh_key_exchange(bob_identity_private, alice_eph_public)
        bob_shared_id = perform_dh_key_exchange(bob_identity_private, alice_identity_public)
        bob_combined = bob_shared_eph + bob_shared_id
        bob_key, _ = derive_key(bob_combined, salt)

        # Decrypt
        decrypted = decrypt_message(bob_key, nonce, ciphertext)
        assert decrypted == plaintext


if __name__ == "__main__":
    pytest.main([__file__, "-v"])