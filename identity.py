"""
Identity management for the encrypted messaging app.
Handles generation, storage, and retrieval of identity key pairs.
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from crypto import (
    generate_identity_keypair,
    serialize_private_key,
    deserialize_private_key,
    serialize_public_key,
    deserialize_public_key,
    generate_signing_keypair,
    serialize_signing_public_key,
    deserialize_signing_public_key,
    serialize_signing_private_key,
    deserialize_signing_private_key
)
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
import datetime
from config import config

# Setup logging
logger = logging.getLogger(__name__)

# Custom OID for X25519 public key extension
# Using a private enterprise OID (1.3.6.1.4.1) + arbitrary identifier
# In practice, you should register a proper OID, but for demo we'll use:
# 1.3.6.1.4.1.99999.1.1 (where 99999 is a private enterprise number)
X25519_PUBLIC_KEY_OID = x509.ObjectIdentifier("1.3.6.1.4.1.99999.1.1")

# Custom OID for Ed25519 signing public key extension
ED25519_SIGNING_KEY_OID = x509.ObjectIdentifier("1.3.6.1.4.1.99999.1.2")

from cryptography.x509 import ExtensionNotFound


class IdentityManager:
    """Manages user identity key pairs."""

    def __init__(self, data_dir: str = None):
        """
        Initialize identity manager.

        Args:
            data_dir: Directory to store identity files
        """
        # Use configuration value as default
        if data_dir is None:
            storage_config = config.get_storage_config()
            data_dir = storage_config.get("data_dir", "./data")

        logger.debug(f"Initializing IdentityManager with data_dir: {data_dir}")
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.identity_file = self.data_dir / "identity.json"
        logger.info(f"IdentityManager initialized, identity file: {self.identity_file}")

    def generate_and_save_identity(self, username: str) -> Tuple[bytes, bytes]:
        """
        Generate a new identity key pair and save it.

        Args:
            username: Username for this identity

        Returns:
            tuple: (private_key_bytes, public_key_bytes)
        """
        logger.info(f"Generating and saving identity for user: {username}")
        private_key, public_key = generate_identity_keypair()

        private_key_bytes = serialize_private_key(private_key)
        public_key_bytes = serialize_public_key(public_key)

        # Generate Ed25519 signing key pair
        signing_private_key, signing_public_key = generate_signing_keypair()
        signing_private_key_bytes = serialize_signing_private_key(signing_private_key)
        signing_public_key_bytes = serialize_signing_public_key(signing_public_key)

        # Save to file
        identity_data = {
            "username": username,
            "private_key": private_key_bytes.hex(),
            "public_key": public_key_bytes.hex(),
            "signing_private_key": signing_private_key_bytes.hex(),
            "signing_public_key": signing_public_key_bytes.hex()
        }

        with open(self.identity_file, 'w') as f:
            json.dump(identity_data, f, indent=2)

        logger.info(f"Identity saved for user: {username}")
        return private_key_bytes, public_key_bytes

    def load_identity(self) -> Optional[Tuple[bytes, bytes, str]]:
        """
        Load existing identity from file.

        Returns:
            tuple: (private_key_bytes, public_key_bytes, username) or None if not found
        """
        logger.debug(f"Loading identity from file: {self.identity_file}")
        if not self.identity_file.exists():
            logger.debug("Identity file does not exist")
            return None

        try:
            with open(self.identity_file, 'r') as f:
                data = json.load(f)

            private_key_bytes = bytes.fromhex(data["private_key"])
            public_key_bytes = bytes.fromhex(data["public_key"])
            username = data["username"]

            logger.info(f"Identity loaded for user: {username}")
            return private_key_bytes, public_key_bytes, username
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load identity: {e}")
            return None

    def load_identity_with_signing_keys(self) -> Optional[Tuple[bytes, bytes, bytes, bytes, str]]:
        """
        Load existing identity from file including Ed25519 signing keys.

        Returns:
            tuple: (private_key_bytes, public_key_bytes, signing_private_key_bytes, signing_public_key_bytes, username) or None if not found
        """
        logger.debug(f"Loading identity with signing keys from file: {self.identity_file}")
        if not self.identity_file.exists():
            logger.debug("Identity file does not exist")
            return None

        try:
            with open(self.identity_file, 'r') as f:
                data = json.load(f)

            private_key_bytes = bytes.fromhex(data["private_key"])
            public_key_bytes = bytes.fromhex(data["public_key"])
            username = data["username"]

            # Load signing keys if present (backward compatibility)
            signing_private_key_bytes = None
            signing_public_key_bytes = None
            if "signing_private_key" in data and "signing_public_key" in data:
                signing_private_key_bytes = bytes.fromhex(data["signing_private_key"])
                signing_public_key_bytes = bytes.fromhex(data["signing_public_key"])

            logger.info(f"Identity with signing keys loaded for user: {username}")
            return private_key_bytes, public_key_bytes, signing_private_key_bytes, signing_public_key_bytes, username
        except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to load identity with signing keys: {e}")
            return None

    def get_signing_public_key_bytes(self) -> Optional[bytes]:
        """
        Get just the Ed25519 signing public key bytes.

        Returns:
            bytes: Signing public key in raw format or None if no identity
        """
        logger.debug("Getting signing public key bytes")
        # First try loading from identity file (for non-cert identities)
        identity = self.load_identity_with_signing_keys()
        if identity and identity[3] is not None:
            logger.debug("Signing public key bytes retrieved from identity file")
            return identity[3]  # signing_public_key_bytes

        # For cert-based identities, try loading from certificate
        cert_identity = self.load_identity_with_cert()
        if cert_identity:
            # cert_identity: (ec_private_key_bytes, ec_public_key_bytes, x25519_private_key_bytes, x25519_public_key_bytes, username, cert_bytes)
            cert_bytes = cert_identity[5]
            if cert_bytes:
                try:
                    from cryptography import x509
                    from cryptography.hazmat.backends import default_backend
                    from identity import ED25519_SIGNING_KEY_OID
                    from cryptography.x509 import UnrecognizedExtension

                    cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())
                    for extension in cert.extensions:
                        if extension.oid == ED25519_SIGNING_KEY_OID:
                            if isinstance(extension.value, UnrecognizedExtension):
                                signing_pubkey = extension.value._value
                                logger.debug("Signing public key bytes retrieved from certificate")
                                return signing_pubkey
                except Exception as e:
                    logger.debug(f"Could not extract signing key from certificate: {e}")

        logger.debug("No signing key found")
        return None

    def get_signing_public_key_hex(self) -> Optional[str]:
        """
        Get the Ed25519 signing public key as hex string.

        Returns:
            str: Signing public key in hex format or None if no identity
        """
        logger.debug("Getting signing public key as hex")
        signing_public_key_bytes = self.get_signing_public_key_bytes()
        if signing_public_key_bytes:
            hex_str = signing_public_key_bytes.hex()
            logger.debug("Signing public key hex retrieved")
            return hex_str
        logger.debug("No signing key found")
        return None

    def get_signing_private_key_bytes(self) -> Optional[bytes]:
        """
        Get the Ed25519 signing private key bytes (for signing messages).

        Returns:
            bytes: Signing private key in raw format or None if no identity
        """
        logger.debug("Getting signing private key bytes")
        identity = self.load_identity_with_signing_keys()
        if identity and identity[2] is not None:
            logger.debug("Signing private key bytes retrieved")
            return identity[2]  # signing_private_key_bytes
        logger.debug("No signing private key found")
        return None

    def get_public_key_bytes(self) -> Optional[bytes]:
        """
        Get just the public key bytes (for backward compatibility - returns X25519 public key).

        Returns:
            bytes: Public key in raw format or None if no identity
        """
        logger.debug("Getting public key bytes")
        # Try cert identity first (has x25519_public_key)
        cert_identity = self.load_identity_with_cert()
        if cert_identity:
            logger.debug("Public key bytes retrieved from cert identity")
            return cert_identity[3]  # x25519_public_key_bytes

        # Fallback to TOFU identity
        identity = self.load_identity()
        if identity:
            logger.debug("Public key bytes retrieved from TOFU identity")
            return identity[1]  # public_key_bytes
        logger.debug("No identity found, returning None for public key")
        return None

    def get_x25519_public_key_bytes(self) -> Optional[bytes]:
        """
        Get the X25519 public key bytes for message encryption.
        Works for both TOFU and cert-based identities.

        Returns:
            bytes: X25519 public key in raw format or None if no identity
        """
        return self.get_public_key_bytes()

    def get_public_key_hex(self) -> Optional[str]:
        """
        Get the public key as hex string.

        Returns:
            str: Public key in hex format or None if no identity
        """
        logger.debug("Getting public key as hex")
        public_key_bytes = self.get_public_key_bytes()
        if public_key_bytes:
            hex_str = public_key_bytes.hex()
            logger.debug("Public key hex retrieved")
            return hex_str
        logger.debug("No identity found, returning None for public key hex")
        return None

    def delete_identity(self) -> bool:
        """
        Delete the stored identity.

        Returns:
            bool: True if deleted, False if no identity existed
        """
        logger.info("Deleting identity")
        if self.identity_file.exists():
            self.identity_file.unlink()
            logger.info("Identity deleted successfully")
            return True
        logger.debug("No identity file found to delete")
        return False

    def generate_and_save_identity_with_cert(self, username: str, validity_days: int = None) -> Tuple[bytes, bytes, bytes, bytes, str, bytes]:
        """
        Generate a new identity key pair and self-signed X.509 certificate, then save them.

        Args:
            username: Username for this identity
            validity_days: Number of days the certificate should be valid for

        Returns:
            tuple: (ec_private_key_bytes, ec_public_key_bytes, x25519_private_key_bytes, x25519_public_key_bytes, username, cert_bytes)
        """
        # Use configuration value as default
        if validity_days is None:
            identity_config = config.get_identity_config()
            validity_days = identity_config.get("certificate_validity_days", 365)

        logger.info(f"Generating identity with certificate for user: {username}, validity: {validity_days} days")
        # Generate EC key pair for certificate signing (SSL/TLS compatible)
        from cryptography.hazmat.primitives.asymmetric import ec
        ec_private_key = ec.generate_private_key(ec.SECP256R1())
        ec_public_key = ec_private_key.public_key()

        ec_private_key_bytes = ec_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        ec_public_key_bytes = ec_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        # Generate X25519 key pair for message encryption
        x25519_private_key, x25519_public_key = generate_identity_keypair()
        x25519_private_key_bytes = serialize_private_key(x25519_private_key)
        x25519_public_key_bytes = serialize_public_key(x25519_public_key)

        # Generate Ed25519 signing key pair
        signing_private_key, signing_public_key = generate_signing_keypair()
        signing_private_key_bytes = serialize_signing_private_key(signing_private_key)
        signing_public_key_bytes = serialize_signing_public_key(signing_public_key)

        # Generate self-signed certificate binding identity to X25519 public key and Ed25519 signing key
        # The certificate uses EC key for SSL/TLS compatibility, but carries X25519 and Ed25519 keys in extensions
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, username),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Encrypted Messaging App"),
        ])

        # Create the X25519 public key extension
        x25519_extension = x509.UnrecognizedExtension(
            X25519_PUBLIC_KEY_OID,
            x25519_public_key_bytes  # Raw X25519 public key bytes
        )

        # Create the Ed25519 signing public key extension
        ed25519_extension = x509.UnrecognizedExtension(
            ED25519_SIGNING_KEY_OID,
            signing_public_key_bytes  # Raw Ed25519 public key bytes
        )

        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            ec_public_key  # Certificate uses EC key for SSL/TLS compatibility
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=validity_days)
        ).add_extension(
            x509.SubjectAlternativeName([x509.DNSName(username)]),
            critical=False,
        ).add_extension(
            x25519_extension,
            critical=False,  # Non-critical extension so SSL/TLS implementations that don't understand it will still work
        ).add_extension(
            ed25519_extension,
            critical=False,
        ).sign(ec_private_key, hashes.SHA256())  # Sign with EC key

        cert_bytes = cert.public_bytes(serialization.Encoding.PEM)

        # Save to file (including certificate and all key pairs)
        identity_data = {
            "username": username,
            "ec_private_key": ec_private_key_bytes.hex(),
            "ec_public_key": ec_public_key_bytes.hex(),
            "x25519_private_key": x25519_private_key_bytes.hex(),
            "x25519_public_key": x25519_public_key_bytes.hex(),
            "signing_private_key": signing_private_key_bytes.hex(),
            "signing_public_key": signing_public_key_bytes.hex(),
            "certificate": cert_bytes.hex()
        }

        with open(self.identity_file, 'w') as f:
            json.dump(identity_data, f, indent=2)

        logger.info(f"Identity with certificate saved for user: {username}")
        return ec_private_key_bytes, ec_public_key_bytes, x25519_private_key_bytes, x25519_public_key_bytes, username, cert_bytes

    def load_identity_with_cert(self) -> Optional[Tuple[bytes, bytes, bytes, bytes, str, bytes]]:
        """
        Load existing identity and certificate from file.

        Returns:
            tuple: (ec_private_key_bytes, ec_public_key_bytes, x25519_private_key_bytes, x25519_public_key_bytes, username, cert_bytes) or None if not found
        """
        logger.debug(f"Loading identity with certificate from file: {self.identity_file}")
        if not self.identity_file.exists():
            logger.debug("Identity file does not exist")
            return None

        try:
            with open(self.identity_file, 'r') as f:
                data = json.load(f)

            ec_private_key_bytes = bytes.fromhex(data["ec_private_key"])
            ec_public_key_bytes = bytes.fromhex(data["ec_public_key"])
            x25519_private_key_bytes = bytes.fromhex(data["x25519_private_key"])
            x25519_public_key_bytes = bytes.fromhex(data["x25519_public_key"])
            username = data["username"]
            cert_bytes = bytes.fromhex(data["certificate"]) if "certificate" in data else None

            logger.info(f"Identity with certificate loaded for user: {username}")
            return ec_private_key_bytes, ec_public_key_bytes, x25519_private_key_bytes, x25519_public_key_bytes, username, cert_bytes
        except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to load identity with certificate: {e}")
            return None

    def load_identity_with_cert_and_signing(self) -> Optional[Tuple[bytes, bytes, bytes, bytes, bytes, bytes, str, bytes]]:
        """
        Load existing identity and certificate from file including Ed25519 signing keys.

        Returns:
            tuple: (ec_private_key_bytes, ec_public_key_bytes, x25519_private_key_bytes, x25519_public_key_bytes,
                   signing_private_key_bytes, signing_public_key_bytes, username, cert_bytes) or None if not found
        """
        logger.debug(f"Loading identity with certificate and signing keys from file: {self.identity_file}")
        if not self.identity_file.exists():
            logger.debug("Identity file does not exist")
            return None

        try:
            with open(self.identity_file, 'r') as f:
                data = json.load(f)

            ec_private_key_bytes = bytes.fromhex(data["ec_private_key"])
            ec_public_key_bytes = bytes.fromhex(data["ec_public_key"])
            x25519_private_key_bytes = bytes.fromhex(data["x25519_private_key"])
            x25519_public_key_bytes = bytes.fromhex(data["x25519_public_key"])
            username = data["username"]
            cert_bytes = bytes.fromhex(data["certificate"]) if "certificate" in data else None

            # Load signing keys if present (backward compatibility)
            signing_private_key_bytes = None
            signing_public_key_bytes = None
            if "signing_private_key" in data and "signing_public_key" in data:
                signing_private_key_bytes = bytes.fromhex(data["signing_private_key"])
                signing_public_key_bytes = bytes.fromhex(data["signing_public_key"])

            logger.info(f"Identity with certificate and signing keys loaded for user: {username}")
            return ec_private_key_bytes, ec_public_key_bytes, x25519_private_key_bytes, x25519_public_key_bytes, signing_private_key_bytes, signing_public_key_bytes, username, cert_bytes
        except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to load identity with certificate and signing keys: {e}")
            return None

    def extract_ed25519_signing_key_from_cert(self, cert_bytes: bytes) -> Optional[bytes]:
        """
        Extract the Ed25519 signing public key from a certificate's extension.

        Args:
            cert_bytes: Certificate bytes in PEM format

        Returns:
            bytes: Ed25519 public key in raw format (32 bytes), or None if not found/invalid
        """
        logger.debug("Extracting Ed25519 signing public key from certificate")
        try:
            from cryptography.x509 import UnrecognizedExtension
            cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())

            # Iterate through extensions to find our custom one
            for extension in cert.extensions:
                if extension.oid == ED25519_SIGNING_KEY_OID:
                    # The value is an UnrecognizedExtension wrapper, need to access _value
                    if isinstance(extension.value, UnrecognizedExtension):
                        result = extension.value._value
                        logger.debug("Ed25519 signing public key extracted from certificate")
                        return result

            # Extension not found
            logger.debug("Ed25519 signing key extension not found in certificate")
            return None

        except Exception as e:
            # Failed to parse certificate
            logger.error(f"Failed to extract Ed25519 signing key from certificate: {e}")
            return None

    def get_certificate_bytes(self) -> Optional[bytes]:
        """
        Get the certificate bytes.

        Returns:
            bytes: Certificate in PEM format or None if no identity/certificate
        """
        logger.debug("Getting certificate bytes")
        identity = self.load_identity_with_cert()
        if identity:
            logger.debug("Certificate bytes retrieved")
            return identity[5]  # cert_bytes
        logger.debug("No identity/certificate found, returning None")
        return None

    def extract_x25519_public_key_from_cert(self, cert_bytes: bytes) -> Optional[bytes]:
        """
        Extract the X25519 public key from a certificate's extension.

        Args:
            cert_bytes: Certificate bytes in PEM format

        Returns:
            bytes: X25519 public key in raw format, or None if not found/invalid
        """
        logger.debug("Extracting X25519 public key from certificate")
        try:
            from cryptography.x509 import UnrecognizedExtension
            cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())

            # Iterate through extensions to find our custom one
            for extension in cert.extensions:
                if extension.oid == X25519_PUBLIC_KEY_OID:
                    # The value is an UnrecognizedExtension wrapper, need to access _value
                    if isinstance(extension.value, UnrecognizedExtension):
                        result = extension.value._value
                        logger.debug("X25519 public key extracted from certificate")
                        return result

            # Extension not found
            logger.debug("X25519 public key extension not found in certificate")
            return None

        except Exception as e:
            # Failed to parse certificate
            logger.error(f"Failed to extract X25519 public key from certificate: {e}")
            return None

    def validate_certificate(self, cert_bytes: bytes) -> Tuple[bool, Optional[str]]:
        """
        Validate a certificate (check if it's properly signed and not expired).

        Args:
            cert_bytes: Certificate bytes in PEM format

        Returns:
            tuple: (is_valid, error_message)
        """
        logger.debug("Validating certificate")
        try:
            cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())

            # Check if certificate is expired (use UTC properties to avoid deprecation warning)
            now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
            # Use _utc properties if available (cryptography >= 41.0.0), fallback to naive
            not_valid_before = getattr(cert, 'not_valid_before_utc', cert.not_valid_before)
            not_valid_after = getattr(cert, 'not_valid_after_utc', cert.not_valid_after)
            # Ensure both are offset-aware for comparison
            if not_valid_before.tzinfo is None:
                not_valid_before = not_valid_before.replace(tzinfo=datetime.timezone.utc)
            if not_valid_after.tzinfo is None:
                not_valid_after = not_valid_after.replace(tzinfo=datetime.timezone.utc)
            if now < not_valid_before or now > not_valid_after:
                logger.warning(f"Certificate is expired or not yet valid: {not_valid_before} to {not_valid_after}")
                return False, "Certificate is expired or not yet valid"

            # Basic validation passed
            logger.debug("Certificate validation passed")
            return True, None
        except Exception as e:
            logger.error(f"Certificate validation failed: {str(e)}")
            return False, f"Certificate validation failed: {str(e)}"


class ContactManager:
    """Manages stored contact public keys with trust levels (TOFU support) and groups."""

    def __init__(self, data_dir: str = None):
        """
        Initialize contact manager.

        Args:
            data_dir: Directory to store contact files
        """
        # Use configuration value as default
        if data_dir is None:
            storage_config = config.get_storage_config()
            data_dir = storage_config.get("data_dir", "./data")

        logger.debug(f"Initializing ContactManager with data_dir: {data_dir}")
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.contacts_file = self.data_dir / "contacts.json"
        self.groups_file = self.data_dir / "groups.json"
        logger.info(f"ContactManager initialized, contacts file: {self.contacts_file}, groups file: {self.groups_file}")

    # Individual contact methods (TOFU support)
    def add_contact(self, name: str, public_key_hex: str, trust_level: int = 0, signing_key_hex: str = None) -> bool:
        """
        Add or update a contact's public key with trust level.

        Args:
            name: Contact name/identifier
            public_key_hex: Public key in hex format (X25519 encryption key)
            trust_level: Trust level (0 = unknown/unverified, 1 = trusted, 2 = blocked)
            signing_key_hex: Optional Ed25519 signing public key in hex format

        Returns:
            bool: True if successful
        """
        logger.debug(f"Adding/updating contact: {name} with trust level: {trust_level}")
        contacts = self.load_contacts()

        # If contact exists, preserve existing trust level if not overriding
        if name in contacts and trust_level == 0:
            # Keep existing trust level if not explicitly setting to unknown
            existing_trust = contacts[name].get("trust_level", 0)
            trust_level = existing_trust
            logger.debug(f"Preserving existing trust level for {name}: {existing_trust}")

        contact_info = {
            "public_key": public_key_hex,
            "trust_level": trust_level,
            "first_seen": contacts.get(name, {}).get("first_seen", int(time.time())),
            "verified_at": contacts.get(name, {}).get("verified_at")
        }

        # Add signing key if provided
        if signing_key_hex is not None:
            contact_info["signing_key"] = signing_key_hex

        # Set verified_at if we're marking as trusted
        if trust_level == 1 and not contact_info["verified_at"]:
            contact_info["verified_at"] = int(time.time())
            logger.debug(f"Setting verified_at for trusted contact: {name}")

        contacts[name] = contact_info
        result = self._save_contacts(contacts)
        if result:
            logger.info(f"Contact added/updated: {name} (trust level: {trust_level})")
        else:
            logger.error(f"Failed to save contact: {name}")
        return result

    def get_contact_public_key(self, name: str) -> Optional[bytes]:
        """
        Get a contact's public key if contact exists and is trusted or unknown.
        Returns None for blocked contacts or if contact doesn't exist.

        Args:
            name: Contact name/identifier

        Returns:
            bytes: Public key in raw format or None if not found/blocked
        """
        logger.debug(f"Getting public key for contact: {name}")
        contacts = self.load_contacts()
        if name in contacts:
            contact_info = contacts[name]
            trust_level = contact_info.get("trust_level", 0)

            # Return None for blocked contacts
            if trust_level == 2:
                logger.debug(f"Contact {name} is blocked (trust level: 2), returning None")
                return None

            # For unknown/unverified contacts (trust_level=0), we still return the key
            # but the messaging layer should handle verification
            try:
                result = bytes.fromhex(contact_info["public_key"])
                logger.debug(f"Public key retrieved for contact: {name}")
                return result
            except ValueError:
                logger.error(f"Invalid public key format for contact: {name}")
                return None
        logger.debug(f"Contact not found: {name}")
        return None

    def get_contact_signing_key(self, name: str) -> Optional[bytes]:
        """
        Get a contact's Ed25519 signing public key for message verification.

        Args:
            name: Contact name/identifier

        Returns:
            bytes: Signing public key in raw format (32 bytes) or None if not found/blocked
        """
        logger.debug(f"Getting signing key for contact: {name}")
        contacts = self.load_contacts()
        if name in contacts:
            contact_info = contacts[name]
            trust_level = contact_info.get("trust_level", 0)

            # Return None for blocked contacts
            if trust_level == 2:
                logger.debug(f"Contact {name} is blocked (trust level: 2), returning None for signing key")
                return None

            if "signing_key" not in contact_info:
                logger.debug(f"Contact {name} has no signing key")
                return None

            try:
                result = bytes.fromhex(contact_info["signing_key"])
                logger.debug(f"Signing key retrieved for contact: {name}")
                return result
            except ValueError:
                logger.error(f"Invalid signing key format for contact: {name}")
                return None
        logger.debug(f"Contact not found: {name}")
        return None

    def list_contacts(self) -> dict:
        """
        List all stored contacts with their trust levels.

        Returns:
            dict: Mapping of contact names to contact info dictionaries
        """
        logger.debug("Listing all contacts")
        contacts = self.load_contacts()
        logger.debug(f"Found {len(contacts)} contacts")
        return contacts

    def get_contact_trust_level(self, name: str) -> int:
        """
        Get the trust level for a contact.

        Args:
            name: Contact name/identifier

        Returns:
            int: Trust level (0 = unknown/unverified, 1 = trusted, 2 = blocked)
                 Returns 0 if contact doesn't exist (treated as unknown)
        """
        logger.debug(f"Getting trust level for contact: {name}")
        contacts = self.load_contacts()
        if name in contacts:
            trust_level = contacts[name].get("trust_level", 0)
            logger.debug(f"Trust level for {name}: {trust_level}")
            return trust_level
        logger.debug(f"Contact not found: {name}, returning default trust level 0")
        return 0  # Unknown if not found

    def set_contact_trust_level(self, name: str, trust_level: int) -> bool:
        """
        Set the trust level for a contact.

        Args:
            name: Contact name/identifier
            trust_level: Trust level to set (0 = unknown, 1 = trusted, 2 = blocked)

        Returns:
            bool: True if successful
        """
        logger.debug(f"Setting trust level for contact {name} to: {trust_level}")
        contacts = self.load_contacts()
        if name not in contacts:
            # Create new contact entry if it doesn't exist
            # We need a public key - this should ideally be called after we have the key
            # For now, we'll require the contact to exist first
            logger.warning(f"Attempt to set trust level for non-existent contact: {name}")
            return False

        contact_info = contacts[name]
        contact_info["trust_level"] = trust_level

        # Set verified_at timestamp when marking as trusted
        if trust_level == 1 and not contact_info.get("verified_at"):
            contact_info["verified_at"] = int(time.time())
            logger.debug(f"Setting verified_at for newly trusted contact: {name}")
        elif trust_level != 1:
            # Clear verified_at when not trusted
            contact_info["verified_at"] = None
            logger.debug(f"Clearing verified_at for contact: {name} (trust level: {trust_level})")

        contacts[name] = contact_info
        result = self._save_contacts(contacts)
        if result:
            logger.info(f"Trust level set for contact {name}: {trust_level}")
        else:
            logger.error(f"Failed to save contact trust level for: {name}")
        return result

    def add_pending_contact(self, name: str, public_key_hex: str) -> bool:
        """
        Add a new contact in unknown/unverified state (for TOFU).

        Args:
            name: Contact name/identifier
            public_key_hex: Public key in hex format

        Returns:
            bool: True if successful
        """
        logger.debug(f"Adding pending contact: {name}")
        return self.add_contact(name, public_key_hex, trust_level=0)

    def trust_contact(self, name: str) -> bool:
        """
        Mark a contact as trusted.

        Args:
            name: Contact name/identifier

        Returns:
            bool: True if successful
        """
        logger.debug(f"Trusting contact: {name}")
        return self.set_contact_trust_level(name, 1)

    def block_contact(self, name: str) -> bool:
        """
        Block a contact.

        Args:
            name: Contact name/identifier

        Returns:
            bool: True if successful
        """
        logger.debug(f"Blocking contact: {name}")
        return self.set_contact_trust_level(name, 2)

    def remove_contact(self, name: str) -> bool:
        """
        Remove a contact.

        Args:
            name: Contact name/identifier

        Returns:
            bool: True if removed, False if not found
        """
        logger.debug(f"Removing contact: {name}")
        contacts = self.load_contacts()
        if name in contacts:
            del contacts[name]
            result = self._save_contacts(contacts)
            if result:
                logger.info(f"Contact removed: {name}")
            else:
                logger.error(f"Failed to save contacts after removing: {name}")
            return result
        logger.warning(f"Attempt to remove non-existent contact: {name}")
        return False

    def load_contacts(self) -> dict:
        """
        Load all contacts from file.

        Returns:
            dict: Mapping of contact names to contact info dictionaries
        """
        logger.debug(f"Loading contacts from file: {self.contacts_file}")
        if not self.contacts_file.exists():
            logger.debug("Contacts file does not exist")
            return {}

        try:
            with open(self.contacts_file, 'r') as f:
                data = json.load(f)
            logger.debug(f"Loaded {len(data)} contacts from file")
            return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load contacts: {e}")
            return {}

    def _save_contacts(self, contacts: dict) -> bool:
        """
        Save contacts to file.

        Args:
            contacts: Dictionary of contacts to save

        Returns:
            bool: True if successful
        """
        logger.debug(f"Saving {len(contacts)} contacts to file: {self.contacts_file}")
        try:
            with open(self.contacts_file, 'w') as f:
                json.dump(contacts, f, indent=2)
            logger.debug("Contacts saved successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to save contacts: {e}")
            return False

    def get_pending_contacts(self) -> dict:
        """
        Get all contacts in unknown/unverified state (trust_level = 0).

        Returns:
            dict: Mapping of contact names to contact info for pending contacts
        """
        logger.debug("Getting pending contacts (trust level = 0)")
        contacts = self.load_contacts()
        pending = {}
        for name, info in contacts.items():
            if info.get("trust_level", 0) == 0:
                pending[name] = info
        logger.debug(f"Found {len(pending)} pending contacts")
        return pending

    def get_trusted_contacts(self) -> dict:
        """
        Get all trusted contacts (trust_level = 1).

        Returns:
            dict: Mapping of contact names to contact info for trusted contacts
        """
        logger.debug("Getting trusted contacts (trust level = 1)")
        contacts = self.load_contacts()
        trusted = {}
        for name, info in contacts.items():
            if info.get("trust_level", 0) == 1:
                trusted[name] = info
        logger.debug(f"Found {len(trusted)} trusted contacts")
        return trusted

    def get_blocked_contacts(self) -> dict:
        """
        Get all blocked contacts (trust_level = 2).

        Returns:
            dict: Mapping of contact names to contact info for blocked contacts
        """
        logger.debug("Getting blocked contacts (trust level = 2)")
        contacts = self.load_contacts()
        blocked = {}
        for name, info in contacts.items():
            if info.get("trust_level", 0) == 2:
                blocked[name] = info
        logger.debug(f"Found {len(blocked)} blocked contacts")
        return blocked

    # Group management methods
    def create_group(self, group_name: str, member_names: List[str], creator: str = None) -> bool:
        """
        Create a new group with the specified members.

        Args:
            group_name: Name of the group
            member_names: List of member usernames
            creator: Optional username of the group creator (added to members, excluded from contact validation)

        Returns:
            bool: True if successful
        """
        logger.info(f"Creating group: {group_name} with members: {member_names}, creator: {creator}")
        groups = self.load_groups()

        # Check if group already exists
        if group_name in groups:
            logger.warning(f"Group already exists: {group_name}")
            return False

        # Validate that all members exist as contacts (except the creator)
        contacts = self.load_contacts()
        for member in member_names:
            if member == creator:
                # Creator doesn't need to be in their own contacts
                continue
            if member not in contacts:
                logger.warning(f"Member not found in contacts: {member}")
                return False

        # Create group info - include creator in members list
        all_members = member_names.copy()
        if creator and creator not in all_members:
            all_members.append(creator)

        group_info = {
            "members": all_members,
            "created_at": int(time.time()),
            "modified_at": int(time.time())
        }

        groups[group_name] = group_info
        result = self._save_groups(groups)
        if result:
            logger.info(f"Group created successfully: {group_name} with members: {all_members}")
        else:
            logger.error(f"Failed to save group: {group_name}")
        return result

    def add_group_member(self, group_name: str, member_name: str) -> bool:
        """
        Add a member to an existing group.

        Args:
            group_name: Name of the group
            member_name: Username to add

        Returns:
            bool: True if successful
        """
        logger.debug(f"Adding member {member_name} to group: {group_name}")
        groups = self.load_groups()
        if group_name not in groups:
            logger.warning(f"Group not found: {group_name}")
            return False

        contacts = self.load_contacts()
        if member_name not in contacts:
            logger.warning(f"Member not found in contacts: {member_name}")
            return False

        if member_name in groups[group_name]["members"]:
            logger.debug(f"Member {member_name} already in group: {group_name}")
            return True  # Already a member

        groups[group_name]["members"].append(member_name)
        groups[group_name]["modified_at"] = int(time.time())
        result = self._save_groups(groups)
        if result:
            logger.info(f"Member {member_name} added to group: {group_name}")
        else:
            logger.error(f"Failed to save group after adding member: {group_name}")
        return result

    def remove_group_member(self, group_name: str, member_name: str) -> bool:
        """
        Remove a member from a group.

        Args:
            group_name: Name of the group
            member_name: Username to remove

        Returns:
            bool: True if successful
        """
        logger.debug(f"Removing member {member_name} from group: {group_name}")
        groups = self.load_groups()
        if group_name not in groups:
            logger.warning(f"Group not found: {group_name}")
            return False

        if member_name not in groups[group_name]["members"]:
            logger.debug(f"Member {member_name} not in group: {group_name} (nothing to remove)")
            return True  # Not a member, nothing to do

        groups[group_name]["members"].remove(member_name)
        groups[group_name]["modified_at"] = int(time.time())
        result = self._save_groups(groups)
        if result:
            logger.info(f"Member {member_name} removed from group: {group_name}")
        else:
            logger.error(f"Failed to save group after removing member: {group_name}")
        return result

    def get_group_members(self, group_name: str) -> List[str]:
        """
        Get the list of members in a group.

        Args:
            group_name: Name of the group

        Returns:
            list: List of member usernames, or empty list if group doesn't exist
        """
        logger.debug(f"Getting members for group: {group_name}")
        groups = self.load_groups()
        if group_name in groups:
            members = groups[group_name]["members"].copy()
            logger.debug(f"Group {group_name} has {len(members)} members: {members}")
            return members
        logger.debug(f"Group not found: {group_name}")
        return []

    def list_groups(self) -> dict:
        """
        List all stored groups.

        Returns:
            dict: Mapping of group names to group info dictionaries
        """
        logger.debug("Listing all groups")
        return self.load_groups()

    def delete_group(self, group_name: str) -> bool:
        """
        Delete a group.

        Args:
            group_name: Name of the group

        Returns:
            bool: True if successful
        """
        logger.info(f"Deleting group: {group_name}")
        groups = self.load_groups()

        if group_name in groups:
            del groups[group_name]
            return self._save_groups(groups)
        else:
            logger.warning(f"Attempt to delete non-existent group: {group_name}")
            return False

    def load_groups(self) -> dict:
        """
        Load all groups from file.

        Returns:
            dict: Mapping of group names to group info dictionaries
        """
        logger.debug(f"Loading groups from file: {self.groups_file}")
        if not self.groups_file.exists():
            logger.debug("Groups file does not exist")
            return {}

        try:
            with open(self.groups_file, 'r') as f:
                data = json.load(f)
            logger.debug(f"Loaded {len(data)} groups from file")
            return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load groups: {e}")
            return {}

    def _save_groups(self, groups: dict) -> bool:
        """
        Save groups to file.

        Args:
            groups: Dictionary of groups to save

        Returns:
            bool: True if successful
        """
        logger.debug(f"Saving {len(groups)} groups to file: {self.groups_file}")
        try:
            with open(self.groups_file, 'w') as f:
                json.dump(groups, f, indent=2)
            logger.debug("Groups saved successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to save groups: {e}")
            return False

    def is_contact_in_group(self, group_name: str, contact_name: str) -> bool:
        """
        Check if a contact is a member of a group.

        Args:
            group_name: Name of the group
            contact_name: Name of the contact to check

        Returns:
            bool: True if contact is in group, False otherwise
        """
        logger.debug(f"Checking if contact {contact_name} is in group: {group_name}")
        groups = self.load_groups()
        if group_name in groups:
            result = contact_name in groups[group_name]["members"]
            logger.debug(f"Contact {contact_name} is in group {group_name}: {result}")
            return result
        logger.debug(f"Group not found: {group_name}")
        return False


# Global instances for easy access (for backward compatibility)
identity_manager = IdentityManager()
contact_manager = ContactManager()

# Log that the module has been initialized
logger.info("Identity module initialized")