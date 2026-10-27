"""
Cryptographic primitives for the encrypted messaging app.
Handles key generation, Diffie-Hellman key exchange, encryption, decryption, and signing.
"""

import os
import secrets
from cryptography.hazmat.primitives.asymmetric import x25519, ed25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag


def generate_identity_keypair():
    """
    Generate a long-term identity key pair (X25519).

    Returns:
        tuple: (private_key, public_key) as X25519PrivateKey and X25519PublicKey objects
    """
    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def generate_ephemeral_keypair():
    """
    Generate an ephemeral key pair for forward secrecy.

    Returns:
        tuple: (private_key, public_key) as X25519PrivateKey and X25519PublicKey objects
    """
    return generate_identity_keypair()  # Same algorithm for ephemeral keys


def serialize_public_key(public_key):
    """
    Serialize a public key to bytes for storage/transmission.

    Args:
        public_key: X25519PublicKey object

    Returns:
        bytes: Serialized public key in raw format
    """
    return public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )


def deserialize_public_key(public_key_bytes):
    """
    Deserialize bytes to a public key object.

    Args:
        public_key_bytes (bytes): Serialized public key in raw format

    Returns:
        X25519PublicKey: Deserialized public key object
    """
    return x25519.X25519PublicKey.from_public_bytes(public_key_bytes)


def serialize_private_key(private_key):
    """
    Serialize a private key to bytes for storage.

    Args:
        private_key: X25519PrivateKey object

    Returns:
        bytes: Serialized private key in raw format
    """
    return private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )


def deserialize_private_key(private_key_bytes):
    """
    Deserialize bytes to a private key object.

    Args:
        private_key_bytes (bytes): Serialized private key in raw format

    Returns:
        X25519PrivateKey: Deserialized private key object
    """
    return x25519.X25519PrivateKey.from_private_bytes(private_key_bytes)


def perform_dh_key_exchange(private_key, peer_public_key):
    """
    Perform Diffie-Hellman key exchange.

    Args:
        private_key: X25519PrivateKey (our private key)
        peer_public_key: X25519PublicKey (peer's public key)

    Returns:
        bytes: Shared secret
    """
    shared_secret = private_key.exchange(peer_public_key)
    return shared_secret


def derive_key(shared_secret, salt=None, length=32):
    """
    Derive a encryption key from shared secret using HKDF.

    Args:
        shared_secret (bytes): Shared secret from DH exchange
        salt (bytes): Salt for HKDF (if None, generates random salt)
        length (int): Length of derived key in bytes (default 32 for AES-256)

    Returns:
        tuple: (derived_key, salt) where derived_key is bytes and salt is bytes
    """
    if salt is None:
        salt = secrets.token_bytes(16)  # 128-bit salt

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=b'encrypted messaging app'
    )
    derived_key = hkdf.derive(shared_secret)
    return derived_key, salt


def encrypt_message(key, plaintext, associated_data=b""):
    """
    Encrypt a message using AES-GCM.

    Args:
        key (bytes): Encryption key (32 bytes for AES-256)
        plaintext (bytes): Message to encrypt
        associated_data (bytes): Additional authenticated data (optional)

    Returns:
        tuple: (nonce, ciphertext) where nonce is 12 bytes and ciphertext is bytes
    """
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)  # 96-bit nonce for AES-GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
    return nonce, ciphertext


def decrypt_message(key, nonce, ciphertext, associated_data=b""):
    """
    Decrypt a message using AES-GCM.

    Args:
        key (bytes): Encryption key (32 bytes for AES-256)
        nonce (bytes): 12-byte nonce used during encryption
        ciphertext (bytes): Encrypted message
        associated_data (bytes): Additional authenticated data (optional)

    Returns:
        bytes: Decrypted plaintext

    Raises:
        InvalidTag: If authentication fails (message tampered with or wrong key)
    """
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data)
    return plaintext


def create_message_keypair(identity_private_key, peer_public_key):
    """
    Create a message encryption key using double ratchet concept (simplified).
    Uses our identity private key and peer's identity public key to establish
    a shared secret, then combines with ephemeral keys for forward secrecy.

    Args:
        identity_private_key: Our long-term identity private key
        peer_public_key: Peer's long-term identity public key

    Returns:
        dict: Contains keys and nonces needed for encryption/decryption
    """
    # Perform DH with identity keys
    shared_secret_identity = perform_dh_key_exchange(
        identity_private_key,
        peer_public_key
    )

    # Generate ephemeral key pair for this message
    eph_private, eph_public = generate_ephemeral_keypair()

    # Perform DH with ephemeral private and identity public (for forward secrecy)
    shared_secret_ephemeral = perform_dh_key_exchange(
        eph_private,
        peer_public_key
    )

    # Combine both secrets (in practice, you'd use a proper key derivation chain)
    combined_secret = shared_secret_identity + shared_secret_ephemeral

    # Derive encryption key
    key, salt = derive_key(combined_secret)

    return {
        'key': key,
        'salt': salt,
        'ephemeral_private_key': eph_private,
        'ephemeral_public_key': eph_public,
        'identity_private_key': identity_private_key,
        'peer_public_key': peer_public_key
    }


# ============================================================================
# Ed25519 Signing Primitives
# ============================================================================

def generate_signing_keypair():
    """
    Generate an Ed25519 signing key pair.

    Returns:
        tuple: (private_key, public_key) as Ed25519PrivateKey and Ed25519PublicKey objects
    """
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def serialize_signing_public_key(public_key):
    """
    Serialize an Ed25519 public key to raw bytes (32 bytes).

    Args:
        public_key: Ed25519PublicKey object

    Returns:
        bytes: Serialized public key in raw format
    """
    return public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )


def deserialize_signing_public_key(public_key_bytes):
    """
    Deserialize bytes to an Ed25519 public key object.

    Args:
        public_key_bytes (bytes): Serialized public key in raw format (32 bytes)

    Returns:
        Ed25519PublicKey: Deserialized public key object
    """
    return ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)


def serialize_signing_private_key(private_key):
    """
    Serialize an Ed25519 private key to raw bytes (32 bytes).

    Args:
        private_key: Ed25519PrivateKey object

    Returns:
        bytes: Serialized private key in raw format
    """
    return private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )


def deserialize_signing_private_key(private_key_bytes):
    """
    Deserialize bytes to an Ed25519 private key object.

    Args:
        private_key_bytes (bytes): Serialized private key in raw format (32 bytes)

    Returns:
        Ed25519PrivateKey: Deserialized private key object
    """
    return ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)


def sign_message(private_key, message):
    """
    Sign a message with Ed25519 private key.

    Args:
        private_key: Ed25519PrivateKey object
        message (bytes): Message to sign

    Returns:
        bytes: 64-byte signature
    """
    return private_key.sign(message)


def verify_signature(public_key, message, signature):
    """
    Verify an Ed25519 signature.

    Args:
        public_key: Ed25519PublicKey object
        message (bytes): Original message that was signed
        signature (bytes): 64-byte signature to verify

    Returns:
        bool: True if signature is valid, False otherwise
    """
    try:
        public_key.verify(signature, message)
        return True
    except Exception:
        return False