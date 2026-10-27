"""
Messaging layer for the encrypted messaging app.
Handles message formatting, encryption/decryption, and transport (file-based queue or WebSocket).
"""

import os
import json
import time
import logging
import secrets
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, Callable, List
from crypto import (
    generate_ephemeral_keypair,
    serialize_public_key,
    deserialize_public_key,
    perform_dh_key_exchange,
    derive_key,
    encrypt_message,
    decrypt_message,
    create_message_keypair,
    deserialize_private_key,
    deserialize_signing_private_key,
    deserialize_signing_public_key,
    sign_message,
    verify_signature
)
from identity import IdentityManager, ContactManager
from storage import MessageStore
from config import config

# Try to import networking, fallback to file-based if not available
try:
    from networking import WebSocketMessageQueue
    NETWORKING_AVAILABLE = True
except ImportError:
    NETWORKING_AVAILABLE = False
    WebSocketMessageQueue = None

# Setup logging
logger = logging.getLogger(__name__)


class MessagingError(Exception):
    """Base exception for messaging errors."""
    pass


class Message:
    """Represents an encrypted message."""

    def __init__(self, sender_name: str, recipient_name: str, ciphertext: bytes, nonce: bytes,
                 ephemeral_public_key: bytes, salt: bytes, timestamp: Optional[float] = None,
                 is_group: bool = False, ttl: Optional[int] = None,
                 edit_of: Optional[Tuple[str, str, float]] = None,
                 delete_of: Optional[Tuple[str, str, float]] = None,
                 signature: Optional[bytes] = None,
                 sender_signing_key: Optional[bytes] = None):
        """
        Initialize a message.

        Args:
            sender_name: Name of the sender
            recipient_name: Name of the recipient (for individual) or group name (for group)
            ciphertext: Encrypted message content
            nonce: Nonce used for encryption
            ephemeral_public_key: Ephemeral public key used for this message
            salt: Salt used for encryption
            timestamp: Unix timestamp (defaults to current time)
            is_group: Whether this is a group message
            ttl: Time-to-live in seconds (None for permanent messages)
            edit_of: Tuple of (sender_name, recipient_name, timestamp) of the message being edited
            delete_of: Tuple of (sender_name, recipient_name, timestamp) of the message being deleted
            signature: Ed25519 signature of the message envelope (for authentication)
            sender_signing_key: Sender's Ed25519 signing public key (for key exchange and verification)
        """
        self.sender_name = sender_name
        self.recipient_name = recipient_name
        self.ciphertext = ciphertext
        self.nonce = nonce
        self.ephemeral_public_key = ephemeral_public_key
        self.salt = salt
        self.timestamp = timestamp or time.time()
        self.is_group = is_group
        self.ttl = ttl
        self.edit_of = edit_of
        self.delete_of = delete_of
        self.signature = signature
        self.sender_signing_key = sender_signing_key
        self.is_edit = edit_of is not None
        self.is_delete = delete_of is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization."""
        result = {
            'sender_name': self.sender_name,
            'recipient_name': self.recipient_name,
            'ciphertext': self.ciphertext.hex(),
            'nonce': self.nonce.hex(),
            'ephemeral_public_key': self.ephemeral_public_key.hex(),
            'salt': self.salt.hex(),
            'timestamp': self.timestamp,
            'is_group': self.is_group,
            'ttl': self.ttl
        }
        if self.signature is not None:
            result['signature'] = self.signature.hex()
        if self.sender_signing_key is not None:
            result['sender_signing_key'] = self.sender_signing_key.hex()
        if self.edit_of is not None:
            result['edit_of'] = {
                'sender_name': self.edit_of[0],
                'recipient_name': self.edit_of[1],
                'timestamp': self.edit_of[2]
            }
        if self.delete_of is not None:
            result['delete_of'] = {
                'sender_name': self.delete_of[0],
                'recipient_name': self.delete_of[1],
                'timestamp': self.delete_of[2]
            }
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary."""
        edit_of = None
        if 'edit_of' in data:
            edit_data = data['edit_of']
            edit_of = (edit_data['sender_name'], edit_data['recipient_name'], edit_data['timestamp'])

        delete_of = None
        if 'delete_of' in data:
            delete_data = data['delete_of']
            delete_of = (delete_data['sender_name'], delete_data['recipient_name'], delete_data['timestamp'])

        signature = None
        if 'signature' in data and data['signature'] is not None:
            signature = bytes.fromhex(data['signature'])

        sender_signing_key = None
        if 'sender_signing_key' in data and data['sender_signing_key'] is not None:
            sender_signing_key = bytes.fromhex(data['sender_signing_key'])

        return cls(
            sender_name=data['sender_name'],
            recipient_name=data['recipient_name'],
            ciphertext=bytes.fromhex(data['ciphertext']),
            nonce=bytes.fromhex(data['nonce']),
            ephemeral_public_key=bytes.fromhex(data['ephemeral_public_key']),
            salt=bytes.fromhex(data['salt']),
            timestamp=data['timestamp'],
            is_group=data.get('is_group', False),
            ttl=data.get('ttl'),
            edit_of=edit_of,
            delete_of=delete_of,
            signature=signature,
            sender_signing_key=sender_signing_key
        )

    def to_json(self) -> str:
        """Serialize message to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Deserialize message from JSON string."""
        return cls.from_dict(json.loads(json_str))


class MessageQueue:
    """Message queue for transport (file-based for prototype, WebSocket for networking)."""

    def __init__(self, queue_dir: str = None, use_networking: bool = None,
                 host: str = None, port: int = None, is_server: bool = False, secure: bool = None,
                 auth_method: str = None, cert_data: Optional[bytes] = None, key_data: Optional[bytes] = None,
                 inbox_dir: str = None, username: Optional[str] = None):
        """
        Initialize message queue.

        Args:
            queue_dir: Directory to store message files (for file-based mode). Used for outbox.
            use_networking: Whether to use WebSocket networking
            host: WebSocket host
            port: WebSocket port
            is_server: Whether this instance is a server (for WebSocket mode)
            secure: Whether to use secure WebSocket connections (wss://) with TLS encryption
            auth_method: Authentication method to use ("tofu" or "cert")
            cert_data: Certificate data in PEM format (for client authentication)
            key_data: Private key data in PEM format (for client authentication)
            inbox_dir: Optional separate directory for inbox (for shared outbox, per-user inbox pattern)
            username: Username for WebSocket client registration (for TOFU auth)
        """
        # Use configuration values as defaults
        storage_config = config.get_storage_config()
        networking_config = config.get_networking_config()

        self.queue_dir = queue_dir if queue_dir is not None else storage_config.get("queue_dir", "./queue")
        self.use_networking = use_networking if use_networking is not None else networking_config.get("use_networking", False)
        self.auth_method = auth_method if auth_method is not None else networking_config.get("auth_method", "tofu")
        self.cert_data = cert_data
        self.key_data = key_data

        logger.debug(f"MessageQueue initialized: queue_dir={self.queue_dir}, use_networking={self.use_networking}, auth_method={self.auth_method}, username={username}")

        if self.use_networking:
            self.queue = WebSocketMessageQueue(host, port, is_server, secure, auth_method, cert_data, key_data, username=username)
        else:
            # File-based queue (original implementation)
            self.queue_dir = Path(self.queue_dir)
            self.queue_dir.mkdir(parents=True, exist_ok=True)
            self.outbox_dir = self.queue_dir / "outbox"
            self.outbox_dir.mkdir(parents=True, exist_ok=True)

            # Support separate inbox directory for shared outbox / per-user inbox pattern
            if inbox_dir is not None:
                self.inbox_dir = Path(inbox_dir)
            else:
                self.inbox_dir = self.queue_dir / "inbox"
            self.inbox_dir.mkdir(parents=True, exist_ok=True)

    def start(self):
        """Start the queue (for networking mode)."""
        if self.use_networking:
            logger.debug("Starting message queue in networking mode")
            self.queue.start()
        else:
            logger.debug("Message queue started in file-based mode (no action needed)")

    def stop(self):
        """Stop the queue (for networking mode)."""
        if self.use_networking:
            logger.debug("Stopping message queue in networking mode")
            self.queue.stop()
        else:
            logger.debug("Message queue stopped in file-based mode (no action needed)")

    def send_message(self, message: Message) -> bool:
        """
        Place a message in the outbox (simulates sending) or send via network.

        Args:
            message: Message to send

        Returns:
            bool: True if successful
        """
        if self.use_networking:
            logger.debug(f"Sending message via network: {message.to_json()[:50]}...")
            return self.queue.send_message(message)
        else:
            # File-based implementation
            try:
                # Create unique filename based on timestamp and random component
                timestamp_str = str(int(message.timestamp * 1000000))  # microseconds
                random_str = secrets.token_hex(8)
                filename = f"{timestamp_str}_{random_str}.msg"
                filepath = self.outbox_dir / filename

                with open(filepath, 'w') as f:
                    f.write(message.to_json())

                logger.debug(f"Message saved to outbox: {filepath}")
                return True
            except Exception as e:
                logger.error(f"Failed to send message (file-based): {e}")
                return False

    def receive_messages(self) -> list[Message]:
        """
        Get all messages from inbox and clear the inbox (file-based) or
        get received messages (networking).

        Returns:
            list: List of received Message objects
        """
        if self.use_networking:
            logger.debug("Receiving messages via network")
            return self.queue.receive_messages()
        else:
            # File-based implementation
            messages = []
            try:
                # Get all .msg files in inbox
                for filepath in self.inbox_dir.glob("*.msg"):
                    try:
                        with open(filepath, 'r') as f:
                            message_json = f.read()
                        message = Message.from_json(message_json)
                        messages.append(message)
                        # Remove file after reading
                        filepath.unlink()
                    except Exception:
                        # Skip corrupted files but continue
                        try:
                            filepath.unlink()
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Error receiving messages (file-based): {e}")
            return messages

    def simulate_network_delay(self, message: Message, delay_seconds: float = 0.1):
        """
        Simulate network delay by moving message from outbox to inbox after delay
        (file-based only) or apply delay (networking).

        Args:
            message: Message to simulate
            delay_seconds: Delay in seconds
        """
        logger.debug(f"Simulating network delay of {delay_seconds} seconds")
        if self.use_networking:
            self.queue.simulate_network_delay(message, delay_seconds)
        else:
            # File-based implementation
            # In a real implementation, this would be actual network transport
            # For prototype, we'll just move it immediately with a small delay
            time.sleep(delay_seconds)
            self._deliver_message(message)

    def _deliver_message(self, message: Message):
        """Deliver a message to the inbox (called by simulate_network_delay)."""
        try:
            timestamp_str = str(int(message.timestamp * 1000000))
            random_str = secrets.token_hex(8)
            filename = f"{timestamp_str}_{random_str}.msg"
            filepath = self.inbox_dir / filename

            with open(filepath, 'w') as f:
                f.write(message.to_json())

            logger.debug(f"Message delivered to inbox: {filepath}")
        except Exception as e:
            logger.error(f"Error delivering message to inbox: {e}")
            pass  # Ignore delivery errors in prototype


class SecureMessenger:
    """Main secure messaging interface."""

    def __init__(self, username: str, data_dir: str = None, queue_dir: str = None,
                 use_networking: bool = None, host: str = None, port: int = None,
                 is_server: bool = False, auth_method: str = None, secure: bool = None,
                 new_contact_callback: Optional[Callable[[str, bytes], None]] = None):
        """
        Initialize secure messenger.

        Args:
            username: Username for this instance
            data_dir: Directory for identity and storage data
            queue_dir: Directory for message queue simulation (file-based) or ignored (networking)
            use_networking: Whether to use WebSocket networking
            host: WebSocket host
            port: WebSocket port
            is_server: Whether this instance is a server (for WebSocket mode)
            auth_method: Authentication method to use ("tofu" or "cert")
            secure: Whether to use secure WebSocket connections (wss://) with TLS encryption
            new_contact_callback: Callback function for new contact requests (name, public_key_bytes)
        """
        # Use configuration values as defaults
        storage_config = config.get_storage_config()
        networking_config = config.get_networking_config()

        self.username = username
        self.data_dir = data_dir if data_dir is not None else storage_config.get("data_dir", "./data")
        self.queue_dir = queue_dir if queue_dir is not None else storage_config.get("queue_dir", "./queue")
        self.use_networking = use_networking if use_networking is not None else networking_config.get("use_networking", False)
        self.host = host if host is not None else networking_config.get("default_host", "localhost")
        self.port = port if port is not None else networking_config.get("default_port", 8765)
        self.is_server = is_server
        self.auth_method = auth_method if auth_method is not None else networking_config.get("auth_method", "tofu")
        self.secure = secure if secure is not None else networking_config.get("secure", False)
        self.new_contact_callback = new_contact_callback

        logger.info(f"Initializing SecureMessenger for user: {self.username}")
        logger.debug(f"Parameters: data_dir={self.data_dir}, queue_dir={self.queue_dir}, use_networking={self.use_networking}, "
                    f"host={self.host}, port={self.port}, is_server={self.is_server}, auth_method={self.auth_method}, secure={self.secure}")

        self.identity_manager = IdentityManager(self.data_dir)
        self.contact_manager = ContactManager(self.data_dir)
        self.message_store = MessageStore(str(Path(self.data_dir) / "messaging.db"))
        # Get certificate data for certificate-based authentication
        cert_data = None
        key_data = None
        if self.auth_method == "cert":
            identity = self.identity_manager.load_identity_with_cert()
            if identity:
                # identity tuple: (ec_private_key_bytes, ec_public_key_bytes, x25519_private_key_bytes, x25519_public_key_bytes, username, cert_bytes)
                cert_data = identity[5]  # cert_bytes
                # Get the private key that corresponds to the certificate
                # For our implementation, the certificate is signed with the EC key
                # but contains the X25519 public key
                # For TLS client authentication, we need the EC private key
                ec_private_key_bytes = identity[0]  # ec_private_key_bytes
                from cryptography.hazmat.primitives import serialization
                key_data = ec_private_key_bytes  # This is already in PEM format from identity.py

        # Ensure identity exists FIRST (generates cert if needed)
        self._ensure_identity()

        # Reload cert/key after identity generation for cert auth
        if self.auth_method == "cert":
            identity = self.identity_manager.load_identity_with_cert()
            if identity:
                cert_data = identity[5]
                ec_private_key_bytes = identity[0]
                from cryptography.hazmat.primitives import serialization
                key_data = ec_private_key_bytes

        # Use per-user inbox directory for shared outbox / per-user inbox pattern
        inbox_dir = str(Path(self.queue_dir) / f"inbox_{self.username}")

        self.message_queue = MessageQueue(self.queue_dir, self.use_networking, self.host, self.port,
                                        self.is_server, self.secure, self.auth_method, cert_data, key_data,
                                        inbox_dir=inbox_dir, username=self.username if not self.is_server else None)
        self.use_networking = self.use_networking and NETWORKING_AVAILABLE

        # Start networking if enabled
        if self.use_networking:
            self.message_queue.start()

    def __del__(self):
        """Cleanup when object is destroyed."""
        if hasattr(self, 'message_queue') and self.use_networking:
            logger.debug("Cleaning up SecureMessenger (stopping message queue)")
            self.message_queue.stop()

    def _ensure_identity(self):
        """Ensure we have an identity; generate if not present."""
        logger.debug(f"Ensuring identity exists for user: {self.username}")
        if self.auth_method == "cert":
            # Try to load identity with certificate for certificate-based auth
            identity = self.identity_manager.load_identity_with_cert()
            if identity is None:
                logger.info(f"No existing identity found for {self.username}. Generating new identity with certificate...")
                ec_private_key_bytes, ec_public_key_bytes, x25519_private_key_bytes, x25519_public_key_bytes, username, cert_bytes = self.identity_manager.generate_and_save_identity_with_cert(self.username)
                logger.info(f"Identity generated and saved. Your public key: {x25519_public_key_bytes.hex()}")
            else:
                logger.debug(f"Existing identity loaded for user: {self.username}")
        else:
            # Default TOFU authentication
            identity = self.identity_manager.load_identity()
            if identity is None:
                logger.info(f"No existing identity found for {self.username}. Generating new identity...")
                self.identity_manager.generate_and_save_identity(self.username)
                logger.info(f"Identity generated and saved. Your public key: {self.identity_manager.get_public_key_hex()}")
            else:
                logger.debug(f"Existing identity loaded for user: {self.username}")

    def get_identity(self) -> Tuple[bytes, bytes, str]:
        """
        Get the current user's identity.

        Returns:
            tuple: (private_key_bytes, public_key_bytes, username)
        """
        logger.debug(f"Getting identity for user: {self.username}")
        if self.auth_method == "cert":
            identity = self.identity_manager.load_identity_with_cert()
            if identity is None:
                raise MessagingError("No identity found")
            # For certificate-based auth, return X25519 keys for message encryption
            # identity tuple: (ec_private_key_bytes, ec_public_key_bytes, x25519_private_key_bytes, x25519_public_key_bytes, username, cert_bytes)
            x25519_private_key_bytes = identity[2]
            x25519_public_key_bytes = identity[3]
            username = identity[4]
            return x25519_private_key_bytes, x25519_public_key_bytes, username
        else:
            # Default TOFU authentication
            identity = self.identity_manager.load_identity()
            if identity is None:
                raise MessagingError("No identity found")
            return identity

    def add_contact(self, name: str, public_key_hex: str, signing_key_hex: Optional[str] = None):
        """
        Add a contact with their public key and optional signing key.

        Args:
            name: Contact name/identifier
            public_key_hex: X25519 public key in hex format
            signing_key_hex: Optional Ed25519 signing public key in hex format
        """
        logger.debug(f"Adding contact: {name} with signing key: {'yes' if signing_key_hex else 'no'}")
        self.contact_manager.add_contact(name, public_key_hex, signing_key_hex=signing_key_hex)

    def get_contact_public_key(self, name: str) -> Optional[bytes]:
        """
        Get a contact's public key.

        Args:
            name: Contact name/identifier

        Returns:
            bytes: Public key in raw format or None if not found
        """
        logger.debug(f"Getting public key for contact: {name}")
        return self.contact_manager.get_contact_public_key(name)

    def list_contacts(self) -> dict:
        """
        List all stored contacts.

        Returns:
            dict: Mapping of contact names to public key hex strings
        """
        logger.debug("Listing all contacts")
        return self.contact_manager.list_contacts()

    # Group management methods
    def create_group(self, group_name: str, member_names: List[str]) -> bool:
        """
        Create a new group with the specified members.
        The creator (self.username) is automatically added as a member.

        Args:
            group_name: Name of the group
            member_names: List of member usernames

        Returns:
            bool: True if successful
        """
        logger.info(f"Creating group: {group_name} with members: {member_names}")
        # Add creator to member list if not already present
        all_members = member_names.copy()
        if self.username not in all_members:
            all_members.append(self.username)
        return self.contact_manager.create_group(group_name, all_members, creator=self.username)

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
        return self.contact_manager.add_group_member(group_name, member_name)

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
        return self.contact_manager.remove_group_member(group_name, member_name)

    def get_group_members(self, group_name: str) -> List[str]:
        """
        Get the list of members in a group.

        Args:
            group_name: Name of the group

        Returns:
            list: List of member usernames, or empty list if group doesn't exist
        """
        logger.debug(f"Getting members for group: {group_name}")
        return self.contact_manager.get_group_members(group_name)

    def list_groups(self) -> dict:
        """
        List all stored groups.

        Returns:
            dict: Mapping of group names to group info dictionaries
        """
        logger.debug("Listing all groups")
        return self.contact_manager.load_groups()

    def delete_group(self, group_name: str) -> bool:
        """
        Delete a group.

        Args:
            group_name: Name of the group

        Returns:
            bool: True if successful
        """
        logger.info(f"Deleting group: {group_name}")
        return self.contact_manager.delete_group(group_name)

    def send_message(self, recipient_name: str, plaintext: str, ttl: Optional[int] = None,
                     edit_of: Optional[Tuple[str, str, float]] = None,
                     delete_of: Optional[Tuple[str, str, float]] = None) -> bool:
        """
        Send an encrypted message to a recipient (individual or group).

        Args:
            recipient_name: Name of the recipient or group
            plaintext: Message to send
            ttl: Time-to-live in seconds (None for permanent messages)
            edit_of: Tuple of (sender_name, recipient_name, timestamp) of the message being edited
            delete_of: Tuple of (sender_name, recipient_name, timestamp) of the message being deleted

        Returns:
            bool: True if message was queued for sending
        """
        logger.info(f"Sending message to {recipient_name} (ttl={ttl})")
        try:
            # Get our identity
            our_private_key_bytes, our_public_key_bytes, our_username = self.get_identity()
            our_private_key = deserialize_private_key(our_private_key_bytes)

            # Get our signing private key
            signing_private_key_bytes = self.identity_manager.get_signing_private_key_bytes()
            if signing_private_key_bytes is not None:
                signing_private_key = deserialize_signing_private_key(signing_private_key_bytes)
            else:
                signing_private_key = None

            # Check if recipient is a group
            is_group = self.contact_manager.is_contact_in_group(recipient_name, our_username) or \
                       (recipient_name in self.contact_manager.load_groups() and
                        our_username in self.contact_manager.get_group_members(recipient_name))

            # For groups, we send to each member individually
            if is_group:
                group_members = self.contact_manager.get_group_members(recipient_name)
                # Remove ourselves from the list to avoid sending to ourselves
                if our_username in group_members:
                    group_members.remove(our_username)

                # Send individual message to each group member
                all_success = True
                for member in group_members:
                    # Get member's public key
                    member_public_key_bytes = self.get_contact_public_key(member)
                    if member_public_key_bytes is None:
                        logger.warning(f"Could not get public key for group member {member}")
                        all_success = False
                        continue

                    member_public_key = deserialize_public_key(member_public_key_bytes)

                    # Generate ephemeral key pair for forward secrecy
                    eph_private_key, eph_public_key = generate_ephemeral_keypair()

                    # Perform DH key exchange: our ephemeral private + member's identity public
                    shared_secret_eph = perform_dh_key_exchange(eph_private_key, member_public_key)

                    # Perform DH key exchange: our identity private + member's identity public
                    shared_secret_id = perform_dh_key_exchange(our_private_key, member_public_key)

                    # Combine secrets for key derivation
                    combined_secret = shared_secret_eph + shared_secret_id

                    # Derive encryption key
                    key, salt = derive_key(combined_secret)

                    # Encrypt the message
                    plaintext_bytes = plaintext.encode('utf-8')
                    nonce, ciphertext = encrypt_message(key, plaintext_bytes)

                    # Create message envelope for signing
                    timestamp = int(time.time())
                    message_data_to_sign = (ciphertext + nonce + serialize_public_key(eph_public_key) + salt +
                                          timestamp.to_bytes(8, 'big') + recipient_name.encode('utf-8') + b'\x01')

                    # Sign the message if we have a signing key
                    signature = None
                    if signing_private_key is not None:
                        signature = sign_message(signing_private_key, message_data_to_sign)
                        logger.debug(f"Message signed for group member {member}")

                    # Get our signing public key to include in message (for key exchange)
                    sender_signing_key = self.identity_manager.get_signing_public_key_bytes()

                    # Create message object (marked as group message)
                    message = Message(
                        sender_name=our_username,
                        recipient_name=recipient_name,  # Keep group name as recipient
                        ciphertext=ciphertext,
                        nonce=nonce,
                        ephemeral_public_key=serialize_public_key(eph_public_key),
                        salt=salt,
                        is_group=True,
                        ttl=ttl,
                        edit_of=edit_of,
                        delete_of=delete_of,
                        signature=signature,
                        sender_signing_key=sender_signing_key
                    )

                    # Send message (place in outbox or send via network)
                    success = self.message_queue.send_message(message)

                    if success:
                        # Store sent message locally (as sent to the group)
                        conversation_id = self.message_store.get_or_create_conversation(
                            recipient_name, self._get_group_identifier(recipient_name), is_group=True
                        )
                        self.message_store.save_message(
                            conversation_id=conversation_id,
                            direction='sent',
                            ciphertext=ciphertext,
                            nonce=nonce,
                            ephemeral_public_key=serialize_public_key(eph_public_key),
                            salt=salt,
                            sender_name=our_username,
                            recipient_name=recipient_name,
                            timestamp=timestamp,
                            is_group=True,
                            ttl=ttl,
                            signature=signature,
                            edit_of_sender=edit_of[0] if edit_of else None,
                            edit_of_recipient=edit_of[1] if edit_of else None,
                            edit_of_timestamp=int(edit_of[2]) if edit_of else None,
                            delete_of_sender=delete_of[0] if delete_of else None,
                            delete_of_recipient=delete_of[1] if delete_of else None,
                            delete_of_timestamp=int(delete_of[2]) if delete_of else None
                        )
                    else:
                        all_success = False

                return all_success
            else:
                # Individual message (original logic)
                # Get recipient's public key
                recipient_public_key_bytes = self.get_contact_public_key(recipient_name)
                if recipient_public_key_bytes is None:
                    raise MessagingError(f"Contact '{recipient_name}' not found. Please add contact first.")
                recipient_public_key = deserialize_public_key(recipient_public_key_bytes)

                # Generate ephemeral key pair for forward secrecy
                eph_private_key, eph_public_key = generate_ephemeral_keypair()

                # Perform DH key exchange: our ephemeral private + recipient's identity public
                shared_secret_eph = perform_dh_key_exchange(eph_private_key, recipient_public_key)

                # Perform DH key exchange: our identity private + recipient's identity public
                shared_secret_id = perform_dh_key_exchange(our_private_key, recipient_public_key)

                # Combine secrets for key derivation
                combined_secret = shared_secret_eph + shared_secret_id

                # Derive encryption key
                key, salt = derive_key(combined_secret)

                # Encrypt the message
                plaintext_bytes = plaintext.encode('utf-8')
                nonce, ciphertext = encrypt_message(key, plaintext_bytes)

                # Create message envelope for signing
                timestamp = int(time.time())
                message_data_to_sign = (ciphertext + nonce + serialize_public_key(eph_public_key) + salt +
                                      timestamp.to_bytes(8, 'big') + recipient_name.encode('utf-8') + b'\x00')

                # Sign the message if we have a signing key
                signature = None
                if signing_private_key is not None:
                    signature = sign_message(signing_private_key, message_data_to_sign)
                    logger.debug(f"Message signed for {recipient_name}")

                # Get our signing public key to include in message (for key exchange)
                sender_signing_key = self.identity_manager.get_signing_public_key_bytes()

                # Create message object
                message = Message(
                    sender_name=our_username,
                    recipient_name=recipient_name,
                    ciphertext=ciphertext,
                    nonce=nonce,
                    ephemeral_public_key=serialize_public_key(eph_public_key),
                    salt=salt,
                    is_group=False,
                    ttl=ttl,
                    edit_of=edit_of,
                    delete_of=delete_of,
                    signature=signature,
                    sender_signing_key=sender_signing_key
                )

                # Send message (place in outbox or send via network)
                success = self.message_queue.send_message(message)

                if success:
                    # Store sent message locally
                    conversation_id = self.message_store.get_or_create_conversation(
                        recipient_name, recipient_public_key_bytes, is_group=False
                    )
                    self.message_store.save_message(
                        conversation_id=conversation_id,
                        direction='sent',
                        ciphertext=ciphertext,
                        nonce=nonce,
                        ephemeral_public_key=serialize_public_key(eph_public_key),
                        salt=salt,
                        sender_name=our_username,
                        recipient_name=recipient_name,
                        timestamp=timestamp,
                        is_group=False,
                        ttl=ttl,
                        signature=signature,
                        edit_of_sender=edit_of[0] if edit_of else None,
                        edit_of_recipient=edit_of[1] if edit_of else None,
                        edit_of_timestamp=int(edit_of[2]) if edit_of else None,
                        delete_of_sender=delete_of[0] if delete_of else None,
                        delete_of_recipient=delete_of[1] if delete_of else None,
                        delete_of_timestamp=int(delete_of[2]) if delete_of else None
                    )

                logger.info(f"Message sent successfully to {recipient_name}: {success}")
                return success

        except Exception as e:
            logger.error(f"Error sending message to {recipient_name}: {e}")
            return False

    def receive_and_process_messages(self) -> list[Tuple[str, str]]:
        """
        Receive and decrypt all waiting messages.

        Returns:
            list: List of (sender_name, decrypted_text) tuples
        """
        logger.debug("Receiving and processing messages")
        decrypted_messages = []

        # Get messages from queue
        received_messages = self.message_queue.receive_messages()
        logger.debug(f"Received {len(received_messages)} messages from queue")

        for message in received_messages:
            try:
                # Check if message is intended for us
                # For individual messages: recipient_name should be our username
                # For group messages: recipient_name is the group name, and we must be a member
                is_for_us = False
                if message.is_group:
                    # Check if we're a member of this group
                    group_members = self.contact_manager.get_group_members(message.recipient_name)
                    if self.username in group_members:
                        is_for_us = True
                else:
                    # Individual message - check if recipient is us
                    if message.recipient_name == self.username:
                        is_for_us = True

                if not is_for_us:
                    # Not for us, skip
                    logger.debug(f"Message not intended for us (recipient: {message.recipient_name}, is_group: {message.is_group}), skipping")
                    continue

                # Get our identity for decryption
                our_private_key_bytes, _, our_username = self.get_identity()
                our_private_key = deserialize_private_key(our_private_key_bytes)

                # Get sender's public key from contacts
                sender_public_key_bytes = self.get_contact_public_key(message.sender_name)

                # If we don't have the sender in contacts, this might be a new contact (TOFU)
                is_new_contact = sender_public_key_bytes is None

                # If we don't have the key, try to get it anyway (our updated ContactManager
                # will return keys for unknown contacts, only None for blocked)
                if sender_public_key_bytes is None:
                    # Try to get the public key anyway - our ContactManager might have it as unknown
                    # We need to check if the contact exists but is unknown
                    contacts = self.contact_manager.load_contacts()
                    if message.sender_name in contacts:
                        # Contact exists but might be unknown/trusted/blocked
                        contact_info = contacts[message.sender_name]
                        trust_level = contact_info.get("trust_level", 0)

                        # If blocked, skip
                        if trust_level == 2:
                            logger.warning(f"Received message from blocked contact '{message.sender_name}'. Skipping.")
                            continue

                        # Get the public key (should exist for trust_level 0 or 1)
                        try:
                            sender_public_key_bytes = bytes.fromhex(contact_info["public_key"])
                        except (ValueError, KeyError):
                            # If we can't get the key, skip
                            logger.warning(f"Could not retrieve public key for '{message.sender_name}'. Skipping.")
                            continue
                    else:
                        # Contact doesn't exist at all - try to get public key from message history?
                        # For now, we can't decrypt without the key
                        logger.warning(f"Received message from unknown contact '{message.sender_name}'. Skipping.")
                        continue
                else:
                    # We have the public key from get_contact_public_key
                    # Check if it's blocked
                    trust_level = self.contact_manager.get_contact_trust_level(message.sender_name)
                    if trust_level == 2:
                        logger.warning(f"Received message from blocked contact '{message.sender_name}'. Skipping.")
                        continue

                sender_public_key = deserialize_public_key(sender_public_key_bytes)

                # Get ephemeral public key from message
                sender_eph_public_key = deserialize_public_key(message.ephemeral_public_key)

                # Get salt from message
                salt = message.salt

                # Perform DH key exchange: our identity private + sender's ephemeral public
                shared_secret_eph = perform_dh_key_exchange(our_private_key, sender_eph_public_key)

                # Perform DH key exchange: our identity private + sender's identity public
                shared_secret_id = perform_dh_key_exchange(our_private_key, sender_public_key)

                # Combine secrets for key derivation (must match sender's process)
                combined_secret = shared_secret_eph + shared_secret_id

                # Derive encryption key
                key, _ = derive_key(combined_secret, salt)  # Use the salt from the message

                # Decrypt message
                plaintext_bytes = decrypt_message(
                    key, message.nonce, message.ciphertext
                )
                plaintext = plaintext_bytes.decode('utf-8')

                # Extract and store sender's signing key if present in message (automatic key exchange)
                if message.sender_signing_key is not None:
                    existing_signing_key = self.contact_manager.get_contact_signing_key(message.sender_name)
                    if existing_signing_key is None:
                        # We don't have the signing key yet - store it from the message
                        self.contact_manager.add_contact(
                            message.sender_name,
                            sender_public_key_bytes.hex(),
                            trust_level=self.contact_manager.get_contact_trust_level(message.sender_name),
                            signing_key_hex=message.sender_signing_key.hex()
                        )
                        logger.info(f"Exchanged signing key with {message.sender_name} via message")
                    elif existing_signing_key != message.sender_signing_key:
                        # Signing key changed - could be a key rotation or MITM attempt
                        logger.warning(f"Signing key for {message.sender_name} differs from stored key!")
                        # For now, we keep the old key but log the discrepancy

                # Verify message signature if present
                signature_verified = False
                if message.signature is not None:
                    # Get sender's signing public key
                    sender_signing_key_bytes = self.contact_manager.get_contact_signing_key(message.sender_name)
                    if sender_signing_key_bytes is not None:
                        sender_signing_key = deserialize_signing_public_key(sender_signing_key_bytes)
                        # Reconstruct the message data that was signed
                        is_group_byte = b'\x01' if message.is_group else b'\x00'
                        message_data_to_verify = (message.ciphertext + message.nonce + message.ephemeral_public_key +
                                                 message.salt + int(message.timestamp).to_bytes(8, 'big') +
                                                 message.recipient_name.encode('utf-8') + is_group_byte)
                        signature_verified = verify_signature(sender_signing_key, message_data_to_verify, message.signature)
                        if signature_verified:
                            logger.debug(f"Signature verified for message from {message.sender_name}")
                        else:
                            logger.warning(f"Signature verification FAILED for message from {message.sender_name}")
                    else:
                        logger.warning(f"Message from {message.sender_name} has signature but no signing key available for verification")
                else:
                    logger.debug(f"Message from {message.sender_name} has no signature (backward compatibility)")

                # For certificate-based authentication, trust senders that successfully decrypt
                if self.auth_method == "cert":
                    # Add sender as trusted contact if not already present
                    sender_public_key_bytes = self.get_contact_public_key(message.sender_name)
                    if sender_public_key_bytes is None:
                        # Contact doesn't exist, add as trusted
                        self.add_contact(message.sender_name, sender_public_key.hex())
                        logger.info(f"Added new trusted contact via certificate validation: {message.sender_name}")
                    else:
                        # Contact exists, check if trusted or unknown
                        trust_level = self.contact_manager.get_contact_trust_level(message.sender_name)
                        if trust_level == 0:  # Unknown, upgrade to trusted
                            self.trust_contact(message.sender_name)
                            logger.info(f"Upgraded contact to trusted via certificate validation: {message.sender_name}")
                        # If already trusted (1) or blocked (2), leave as is

                # Store received message locally
                # For group messages, use the group name (recipient_name) as conversation key
                # For individual messages, use the sender's name
                conversation_contact = message.recipient_name if message.is_group else message.sender_name
                conversation_id = self.message_store.get_or_create_conversation(
                    conversation_contact, sender_public_key_bytes, message.is_group
                )
                self.message_store.save_message(
                    conversation_id=conversation_id,
                    direction='received',
                    ciphertext=message.ciphertext,
                    nonce=message.nonce,
                    ephemeral_public_key=message.ephemeral_public_key,
                    salt=message.salt,
                    sender_name=message.sender_name,
                    recipient_name=message.recipient_name,
                    timestamp=int(message.timestamp),
                    is_group=message.is_group,
                    ttl=message.ttl,
                    signature=message.signature,
                    edit_of_sender=message.edit_of[0] if message.edit_of else None,
                    edit_of_recipient=message.edit_of[1] if message.edit_of else None,
                    edit_of_timestamp=int(message.edit_of[2]) if message.edit_of else None,
                    delete_of_sender=message.delete_of[0] if message.delete_of else None,
                    delete_of_recipient=message.delete_of[1] if message.delete_of else None,
                    delete_of_timestamp=int(message.delete_of[2]) if message.delete_of else None
                )

                decrypted_messages.append((message.sender_name, plaintext))
                logger.debug(f"Successfully decrypted message from {message.sender_name}: {plaintext[:50]}...")

                # Handle TOFU: if this was a new/unknown contact, notify about verification request
                if is_new_contact:
                    # Mark as pending contact if not already stored
                    current_trust = self.contact_manager.get_contact_trust_level(message.sender_name)
                    if current_trust == 0:  # Still unknown
                        self.contact_manager.add_pending_contact(message.sender_name, sender_public_key_bytes.hex())
                        logger.debug(f"Added pending contact for TOFU: {message.sender_name}")

                    # Notify about new contact request
                    if self.new_contact_callback:
                        try:
                            self.new_contact_callback(message.sender_name, sender_public_key_bytes)
                            logger.debug(f"New contact callback executed for {message.sender_name}")
                        except Exception as e:
                            logger.error(f"Error in new contact callback: {e}")

            except Exception as e:
                logger.error(f"Error processing message from {message.sender_name}: {e}")
                continue

        logger.info(f"Finished processing messages. Decrypted {len(decrypted_messages)} messages.")
        return decrypted_messages

    def get_conversation_history(self, contact_name: str, limit: int = 50) -> list[Dict]:
        """
        Get conversation history with a contact or group.

        Args:
            contact_name: Name of contact or group
            limit: Maximum number of messages to retrieve

        Returns:
            list: List of message dictionaries with decrypted content
        """
        logger.debug(f"Getting conversation history for {contact_name}, limit: {limit}")
        # Check if this is a group conversation
        is_group = contact_name in self.contact_manager.load_groups()
        conversation = self.message_store.get_conversation_info(contact_name, is_group=is_group)
        if conversation is None:
            logger.debug(f"No conversation found for {contact_name}")
            return []

        # Get all messages first (we'll filter and limit later)
        messages = self.message_store.get_messages(conversation['id'], limit * 3)  # Get extra to account for filtering

        # Identify deleted messages: messages that are referenced by delete_of fields
        deleted_message_keys = set()
        # Map original messages to their edits: (sender, recipient, timestamp) -> list of edit messages
        edits_map = {}

        for msg in messages:
            # Check if this message is a deletion
            if msg['delete_of_sender'] is not None and msg['delete_of_recipient'] is not None and msg['delete_of_timestamp'] is not None:
                deleted_key = (msg['delete_of_sender'], msg['delete_of_recipient'], msg['delete_of_timestamp'])
                deleted_message_keys.add(deleted_key)

            # Check if this message is an edit
            if msg['edit_of_sender'] is not None and msg['edit_of_recipient'] is not None and msg['edit_of_timestamp'] is not None:
                original_key = (msg['edit_of_sender'], msg['edit_of_recipient'], msg['edit_of_timestamp'])
                if original_key not in edits_map:
                    edits_map[original_key] = []
                edits_map[original_key].append(msg)

        # Group messages by their "base" key (original message or standalone message)
        message_groups = {}
        standalone_messages = []

        for msg in messages:
            # Determine if this message is an edit of another message
            is_edit = (msg['edit_of_sender'] is not None and
                      msg['edit_of_recipient'] is not None and
                      msg['edit_of_timestamp'] is not None)

            if is_edit:
                # This is an edit, it belongs to the group of its original message
                original_key = (msg['edit_of_sender'], msg['edit_of_recipient'], msg['edit_of_timestamp'])
                if original_key not in message_groups:
                    message_groups[original_key] = []
                message_groups[original_key].append(msg)
            else:
                # This is not an edit, so it's either an original message or a standalone message
                # Create a key based on its own identity
                msg_key = (msg['sender_name'], msg['recipient_name'], msg['timestamp'])
                if msg_key not in message_groups:
                    message_groups[msg_key] = []
                message_groups[msg_key].append(msg)

        # Process each group: keep only the most recent non-deleted message
        final_messages = []

        for key, msgs in message_groups.items():
            # Check if this group represents a deleted message
            if key in deleted_message_keys:
                # Skip this entire group as it's been deleted
                continue

            # Sort messages by timestamp (newest first) and take the most recent one
            msgs_sorted = sorted(msgs, key=lambda x: x['timestamp'], reverse=True)
            final_messages.append(msgs_sorted[0])

        # Sort all final messages by timestamp (oldest first) for chronological display
        final_messages.sort(key=lambda x: x['timestamp'])

        # Apply limit (take the most recent messages)
        if len(final_messages) > limit:
            final_messages = final_messages[-limit:]

        # Decrypt the messages
        history = []

        # Get our identity for decryption
        our_private_key_bytes, _, _ = self.get_identity()
        our_private_key = deserialize_private_key(our_private_key_bytes)

        for msg in final_messages:
            try:
                # Determine whose public key to use based on direction
                if msg['direction'] == 'sent':
                    # We sent it, so we need recipient's public key to re-derive key
                    if msg['is_group']:
                        # For group messages, we need the group identifier
                        group_id = self._get_group_identifier(msg['recipient_name'])
                        contact_public_key_bytes = self._get_group_key_bytes(group_id)
                        if contact_public_key_bytes is None:
                            continue
                        contact_public_key = deserialize_public_key(contact_public_key_bytes)
                        our_private_key_for_exchange = our_private_key
                    else:
                        # Individual message
                        contact_public_key_bytes = self.get_contact_public_key(contact_name)
                        if contact_public_key_bytes is None:
                            continue
                        contact_public_key = deserialize_public_key(contact_public_key_bytes)
                        our_private_key_for_exchange = our_private_key
                else:  # received
                    # They sent it, so we need their public key
                    if msg['is_group']:
                        # For group messages received, we need to identify the actual sender
                        # But for simplicity in this implementation, we'll treat it as coming from the group
                        # In a more sophisticated implementation, we'd track the actual sender within the group
                        group_id = self._get_group_identifier(msg['recipient_name'])
                        contact_public_key_bytes = self._get_group_key_bytes(group_id)
                        if contact_public_key_bytes is None:
                            continue
                        contact_public_key = deserialize_public_key(contact_public_key_bytes)
                        our_private_key_for_exchange = our_private_key
                    else:
                        # Individual message
                        contact_public_key_bytes = self.get_contact_public_key(contact_name)
                        if contact_public_key_bytes is None:
                            continue
                        contact_public_key = deserialize_public_key(contact_public_key_bytes)
                        our_private_key_for_exchange = our_private_key

                # Get ephemeral public key from message
                sender_eph_public_key = deserialize_public_key(msg['ephemeral_public_key'])

                # Get salt from message
                salt = msg['salt']

                # Perform DH key exchange (same as in send/receive)
                shared_secret_eph = perform_dh_key_exchange(our_private_key_for_exchange, sender_eph_public_key)
                shared_secret_id = perform_dh_key_exchange(our_private_key_for_exchange, contact_public_key)
                combined_secret = shared_secret_eph + shared_secret_id

                # Derive key and decrypt
                key, _ = derive_key(combined_secret, salt)  # Use the salt from the message
                plaintext_bytes = decrypt_message(
                    key, msg['nonce'], msg['ciphertext']
                )
                plaintext = plaintext_bytes.decode('utf-8')

                history.append({
                    'direction': msg['direction'],
                    'text': plaintext,
                    'timestamp': msg['timestamp'],
                    'is_group': msg['is_group']
                })
            except Exception:
                # For sent messages, we can't decrypt due to forward secrecy (ephemeral key discarded)
                # Show a placeholder instead
                if msg['direction'] == 'sent':
                    history.append({
                        'direction': msg['direction'],
                        'text': '[Message encrypted - cannot decrypt due to forward secrecy]',
                        'timestamp': msg['timestamp'],
                        'is_group': msg['is_group']
                    })
                # For received messages, if we can't decrypt, there's a real issue
                # Skip received messages we can't decrypt (shouldn't happen with valid keys)
                continue

        logger.debug(f"Returning {len(history)} messages in conversation history")
        return history

    # Helper methods for key serialization/deserialization
    def serialize_public_key(self, public_key):
        """Serialize public key to bytes."""
        return serialize_public_key(public_key)

    def deserialize_public_key(self, public_key_bytes):
        """Deserialize public key from bytes."""
        return deserialize_public_key(public_key_bytes)

    def deserialize_private_key(self, private_key_bytes):
        """Deserialize private key from bytes."""
        return deserialize_private_key(private_key_bytes)

    # Contact management methods for TOFU
    def trust_contact(self, name: str) -> bool:
        """
        Mark a contact as trusted.

        Args:
            name: Contact name/identifier

        Returns:
            bool: True if successful
        """
        logger.debug(f"Trusting contact: {name}")
        return self.contact_manager.trust_contact(name)

    def block_contact(self, name: str) -> bool:
        """
        Block a contact.

        Args:
            name: Contact name/identifier

        Returns:
            bool: True if successful
        """
        logger.debug(f"Blocking contact: {name}")
        return self.contact_manager.block_contact(name)

    def get_pending_contacts(self) -> dict:
        """
        Get all pending contact requests (unknown/unverified contacts).

        Returns:
            dict: Mapping of contact names to contact info for pending contacts
        """
        logger.debug("Getting pending contacts")
        return self.contact_manager.get_pending_contacts()

    def get_trusted_contacts(self) -> dict:
        """
        Get all trusted contacts.

        Returns:
            dict: Mapping of contact names to contact info for trusted contacts
        """
        logger.debug("Getting trusted contacts")
        return self.contact_manager.get_trusted_contacts()

    def get_blocked_contacts(self) -> dict:
        """
        Get all blocked contacts.

        Returns:
            dict: Mapping of contact names to contact info for blocked contacts
        """
        logger.debug("Getting blocked contacts")
        return self.contact_manager.get_blocked_contacts()

    # Group management helper methods
    def _get_group_identifier(self, group_name: str) -> Optional[bytes]:
        """
        Get a unique identifier for a group (used for storage).
        In this simple implementation, we use a hash of the group name.
        """
        logger.debug(f"Getting group identifier for: {group_name}")
        import hashlib
        result = hashlib.sha256(group_name.encode('utf-8')).digest()
        logger.debug(f"Group identifier: {result.hex()}")
        return result

    def _get_group_key_bytes(self, group_id: bytes) -> Optional[bytes]:
        """
        Get the public key associated with a group identifier.
        For our pairwise encryption approach, we don't actually use a group key.
        This method exists for compatibility with the storage layer.
        """
        logger.debug(f"Getting group key bytes for group identifier: {group_id.hex()}")
        # In our pairwise encryption approach, we don't store or use group keys
        # This is just a placeholder to satisfy the interface
        result = b'\x00' * 32  # Return dummy bytes
        logger.debug(f"Group key bytes: {result.hex()}")
        return result


# Global instance for easy access (for backward compatibility)
secure_messenger = SecureMessenger("default_user")

# Log that the module has been initialized
logger.info("Messaging module initialized")