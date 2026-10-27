"""
Storage layer for the encrypted messaging app.
Handles local persistence of messages and conversations using SQLite.
"""

import sqlite3
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from crypto import serialize_public_key, deserialize_public_key

# Setup logging
logger = logging.getLogger(__name__)


class MessageStore:
    """Manages local storage of messages and conversations."""

    def __init__(self, db_path: str = "./data/messaging.db"):
        """
        Initialize message store.

        Args:
            db_path: Path to SQLite database file
        """
        logger.debug(f"Initializing MessageStore with db_path: {db_path}")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        logger.info(f"MessageStore initialized with database: {self.db_path}")

    def _init_database(self):
        """Initialize database tables if they don't exist."""
        logger.debug("Initializing database tables")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contact_name TEXT NOT NULL,
                    contact_public_key TEXT,  -- NULL for groups
                    is_group BOOLEAN NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    UNIQUE(contact_name, is_group)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    sender_name TEXT NOT NULL,
                    recipient_name TEXT NOT NULL,
                    direction TEXT NOT NULL CHECK(direction IN ('sent', 'received')),
                    ciphertext BLOB NOT NULL,
                    nonce BLOB NOT NULL,
                    ephemeral_public_key BLOB NOT NULL,
                    salt BLOB NOT NULL,
                    timestamp INTEGER NOT NULL,
                    is_group BOOLEAN NOT NULL DEFAULT 0,
                    ttl INTEGER,  -- NULL for permanent, seconds for ephemeral
                    -- Signature for message authentication
                    signature BLOB,  -- Ed25519 signature of the message envelope
                    -- Edit tracking
                    edit_of_sender TEXT,
                    edit_of_recipient TEXT,
                    edit_of_timestamp INTEGER,
                    -- Delete tracking
                    delete_of_sender TEXT,
                    delete_of_recipient TEXT,
                    delete_of_timestamp INTEGER,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            """)
            conn.commit()
        logger.debug("Database tables initialized")

    def _get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_path)

    def get_or_create_conversation(self, contact_name: str, contact_public_key: Optional[bytes] = None, is_group: bool = False) -> int:
        """
        Get existing conversation or create new one.

        Args:
            contact_name: Name/identifier of contact or group
            contact_public_key: Contact's public key in bytes (None for groups)
            is_group: Whether this is a group conversation

        Returns:
            int: Conversation ID
        """
        logger.debug(f"Getting or creating conversation for {contact_name} (is_group={is_group})")
        contact_public_key_hex = contact_public_key.hex() if contact_public_key else None

        with self._get_connection() as conn:
            # Try to get existing conversation
            cursor = conn.execute(
                "SELECT id FROM conversations WHERE contact_name = ? AND is_group = ?",
                (contact_name, 1 if is_group else 0)
            )
            row = cursor.fetchone()
            if row:
                logger.debug(f"Found existing conversation with ID: {row[0]}")
                return row[0]

            # Create new conversation
            cursor = conn.execute(
                """
                INSERT INTO conversations (contact_name, contact_public_key, is_group, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (contact_name, contact_public_key_hex, 1 if is_group else 0, int(time.time()))
            )
            conn.commit()
            conversation_id = cursor.lastrowid
            logger.debug(f"Created new conversation with ID: {conversation_id}")
            return conversation_id

    def save_message(self, conversation_id: int, direction: str,
                     ciphertext: bytes, nonce: bytes, ephemeral_public_key: bytes, salt: bytes,
                     sender_name: str, recipient_name: str,
                     timestamp: Optional[int] = None, is_group: bool = False, ttl: Optional[int] = None,
                     edit_of_sender: Optional[str] = None, edit_of_recipient: Optional[str] = None, edit_of_timestamp: Optional[int] = None,
                     delete_of_sender: Optional[str] = None, delete_of_recipient: Optional[str] = None, delete_of_timestamp: Optional[int] = None,
                     signature: Optional[bytes] = None):
        """
        Save a sent or received message.

        Args:
            conversation_id: ID of the conversation
            direction: 'sent' or 'received'
            ciphertext: Encrypted message bytes
            nonce: Non used for encryption
            ephemeral_public_key: Ephemeral public key used for this message
            salt: Salt used for key derivation
            sender_name: Name of the sender
            recipient_name: Name of the recipient
            timestamp: Unix timestamp (defaults to current time)
            is_group: Whether this is a group message
            ttl: Time-to-live in seconds (None for permanent messages)
            edit_of_sender: Sender name of the message being edited
            edit_of_recipient: Recipient name of the message being edited
            edit_of_timestamp: Timestamp of the message being edited
            delete_of_sender: Sender name of the message being deleted
            delete_of_recipient: Recipient name of the message being deleted
            delete_of_timestamp: Timestamp of the message being deleted
            signature: Ed25519 signature of the message envelope (optional for backward compatibility)
        """
        logger.debug(f"Saving message: conversation_id={conversation_id}, direction={direction}, is_group={is_group}, sender={sender_name}, recipient={recipient_name}")
        if timestamp is None:
            timestamp = int(time.time())
            logger.debug(f"Timestamp set to current time: {timestamp}")

        with self._get_connection() as conn:
            try:
                conn.execute(
                    "INSERT INTO messages (conversation_id, direction, ciphertext, nonce, ephemeral_public_key, salt, sender_name, recipient_name, timestamp, is_group, ttl, signature, edit_of_sender, edit_of_recipient, edit_of_timestamp, delete_of_sender, delete_of_recipient, delete_of_timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (conversation_id, direction, ciphertext, nonce, ephemeral_public_key, salt, sender_name, recipient_name, timestamp, 1 if is_group else 0, ttl, signature, edit_of_sender, edit_of_recipient, edit_of_timestamp, delete_of_sender, delete_of_recipient, delete_of_timestamp)
                )
                conn.commit()
                logger.debug(f"Message saved successfully to conversation {conversation_id}")
            except Exception as e:
                logger.error(f"ERROR in save_message: {e}")
                logger.error(f"conversation_id: {conversation_id} (type: {type(conversation_id)})")
                logger.error(f"direction: {direction} (type: {type(direction)})")
                logger.error(f"ciphertext: {type(ciphertext)} (length: {len(ciphertext) if ciphertext else 0})")
                logger.error(f"nonce: {type(nonce)} (length: {len(nonce) if nonce else 0})")
                logger.error(f"ephemeral_public_key: {type(ephemeral_public_key)} (length: {len(ephemeral_public_key) if ephemeral_public_key else 0})")
                logger.error(f"salt: {type(salt)} (length: {len(salt) if salt else 0})")
                logger.error(f"timestamp: {timestamp} (type: {type(timestamp)})")
                logger.error(f"is_group: {is_group} (type: {type(is_group)}) -> {1 if is_group else 0}")
                logger.error(f"ttl: {ttl} (type: {type(ttl)})")
                logger.error(f"signature: {type(signature)} (length: {len(signature) if signature else 0})")
                logger.error(f"edit_of_sender: {edit_of_sender} (type: {type(edit_of_sender)})")
                logger.error(f"edit_of_recipient: {edit_of_recipient} (type: {type(edit_of_recipient)})")
                logger.error(f"edit_of_timestamp: {edit_of_timestamp} (type: {type(edit_of_timestamp)})")
                logger.error(f"delete_of_sender: {delete_of_sender} (type: {type(delete_of_sender)})")
                logger.error(f"delete_of_recipient: {delete_of_recipient} (type: {type(delete_of_recipient)})")
                logger.error(f"delete_of_timestamp: {delete_of_timestamp} (type: {type(delete_of_timestamp)})")
                raise

    def get_messages(self, conversation_id: int, limit: int = 50) -> List[Dict]:
        """
        Retrieve messages for a conversation.

        Args:
            conversation_id: ID of the conversation
            limit: Maximum number of messages to retrieve

        Returns:
            list: List of message dictionaries ordered by timestamp (oldest first)
        """
        logger.debug(f"Retrieving messages for conversation {conversation_id}, limit: {limit}")
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT sender_name, recipient_name, direction, ciphertext, nonce, ephemeral_public_key, salt, timestamp, is_group, ttl,
                       edit_of_sender, edit_of_recipient, edit_of_timestamp,
                       delete_of_sender, delete_of_recipient, delete_of_timestamp,
                       signature
                FROM messages
                WHERE conversation_id = ?
                  AND (ttl IS NULL OR timestamp + ttl > ?)
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (conversation_id, int(time.time()), limit)
            )
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'sender_name': row['sender_name'],
                    'recipient_name': row['recipient_name'],
                    'direction': row['direction'],
                    'ciphertext': row['ciphertext'],
                    'nonce': row['nonce'],
                    'ephemeral_public_key': row['ephemeral_public_key'],
                    'salt': row['salt'],
                    'timestamp': row['timestamp'],
                    'is_group': bool(row['is_group']),
                    'ttl': row['ttl'],
                    'edit_of_sender': row['edit_of_sender'],
                    'edit_of_recipient': row['edit_of_recipient'],
                    'edit_of_timestamp': row['edit_of_timestamp'],
                    'delete_of_sender': row['delete_of_sender'],
                    'delete_of_recipient': row['delete_of_recipient'],
                    'delete_of_timestamp': row['delete_of_timestamp'],
                    'signature': row['signature']
                })
            logger.debug(f"Retrieved {len(messages)} messages for conversation {conversation_id}")
            return messages

    def cleanup_expired_messages(self) -> int:
        """
        Remove expired messages from the database.

        Returns:
            int: Number of messages removed
        """
        logger.debug("Cleaning up expired messages")
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM messages
                WHERE ttl IS NOT NULL AND timestamp + ttl <= ?
                """,
                (int(time.time()),)
            )
            conn.commit()
            count = cursor.rowcount
            logger.info(f"Cleaned up {count} expired messages")
            return count

    def get_conversation_info(self, contact_name: str, is_group: bool = False) -> Optional[Dict]:
        """
        Get information about a conversation.

        Args:
            contact_name: Name/identifier of contact or group
            is_group: Whether this is a group conversation

        Returns:
            dict: Conversation info or None if not found
        """
        logger.debug(f"Getting conversation info for {contact_name} (is_group={is_group})")
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT c.id, c.contact_name, c.contact_public_key, c.is_group, c.created_at,
                       COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.contact_name = ? AND c.is_group = ?
                  AND (m.ttl IS NULL OR m.timestamp + m.ttl > ?)
                GROUP BY c.id
                """,
                (contact_name, 1 if is_group else 0, int(time.time()))
            )
            row = cursor.fetchone()
            if row:
                result = {
                    'id': row['id'],
                    'contact_name': row['contact_name'],
                    'contact_public_key': bytes.fromhex(row['contact_public_key']) if row['contact_public_key'] else None,
                    'is_group': bool(row['is_group']),
                    'created_at': row['created_at'],
                    'message_count': row['message_count']
                }
                logger.debug(f"Conversation info retrieved: {result}")
                return result
            logger.debug(f"No conversation found for {contact_name}")
            return None

    def list_conversations(self) -> List[Dict]:
        """
        List all conversations.

        Returns:
            list: List of conversation dictionaries
        """
        logger.debug("Listing all conversations")
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT c.id, c.contact_name, c.contact_public_key, c.is_group, c.created_at,
                       COUNT(m.id) as message_count,
                       MAX(CASE WHEN m.ttl IS NULL OR m.timestamp + m.ttl > ? THEN m.timestamp END) as last_message_time
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE m.ttl IS NULL OR m.timestamp + m.ttl > ?
                GROUP BY c.id
                ORDER BY c.created_at DESC
                """,
                (int(time.time()), int(time.time()))
            )
            conversations = []
            for row in cursor.fetchall():
                conversations.append({
                    'id': row['id'],
                    'contact_name': row['contact_name'],
                    'contact_public_key': bytes.fromhex(row['contact_public_key']) if row['contact_public_key'] else None,
                    'is_group': bool(row['is_group']),
                    'created_at': row['created_at'],
                    'message_count': row['message_count'],
                    'last_message_time': row['last_message_time']
                })
            logger.debug(f"Listed {len(conversations)} conversations")
            return conversations

    def delete_conversation(self, contact_name: str, is_group: bool = False) -> bool:
        """
        Delete a conversation and all its messages.

        Args:
            contact_name: Name/identifier of contact or group
            is_group: Whether this is a group conversation

        Returns:
            bool: True if deleted, False if not found
        """
        logger.info(f"Deleting conversation for {contact_name} (is_group={is_group})")
        with self._get_connection() as conn:
            # Delete messages first (due to foreign key constraint)
            conn.execute(
                """
                DELETE FROM messages
                WHERE conversation_id IN (
                    SELECT id FROM conversations WHERE contact_name = ? AND is_group = ?
                )
                """,
                (contact_name, 1 if is_group else 0)
            )
            # Delete conversation
            cursor = conn.execute(
                "DELETE FROM conversations WHERE contact_name = ? AND is_group = ?",
                (contact_name, 1 if is_group else 0)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Conversation deleted for {contact_name}")
            else:
                logger.warning(f"No conversation found to delete for {contact_name}")
            return deleted


# Global instance for easy access (for backward compatibility)
message_store = MessageStore()

# Log that the module has been initialized
logger.info("Storage module initialized")