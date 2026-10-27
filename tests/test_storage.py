"""
Unit tests for storage layer (MessageStore).
"""
import pytest
import os
import sys
import tempfile
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage import MessageStore


class TestMessageStore:
    """Tests for MessageStore class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def message_store(self, temp_db):
        """Create a MessageStore instance with temporary database."""
        return MessageStore(temp_db)

    def test_init_database(self, message_store):
        """Test that database tables are created."""
        # Tables should be created on init
        with message_store._get_connection() as conn:
            # Check conversations table
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'")
            assert cursor.fetchone() is not None

            # Check messages table
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
            assert cursor.fetchone() is not None

    def test_get_or_create_conversation_individual(self, message_store):
        """Test creating individual conversation."""
        contact_name = "Alice"
        public_key = bytes.fromhex("01" * 32)

        conv_id = message_store.get_or_create_conversation(contact_name, public_key, is_group=False)

        assert isinstance(conv_id, int)
        assert conv_id > 0

        # Getting again should return same ID
        conv_id2 = message_store.get_or_create_conversation(contact_name, public_key, is_group=False)
        assert conv_id == conv_id2

    def test_get_or_create_conversation_group(self, message_store):
        """Test creating group conversation."""
        group_name = "Team"
        conv_id = message_store.get_or_create_conversation(group_name, None, is_group=True)

        assert isinstance(conv_id, int)
        assert conv_id > 0

        # Getting again should return same ID
        conv_id2 = message_store.get_or_create_conversation(group_name, None, is_group=True)
        assert conv_id == conv_id2

    def test_save_and_get_message_individual(self, message_store):
        """Test saving and retrieving individual message."""
        contact_name = "Bob"
        public_key = bytes.fromhex("02" * 32)

        conv_id = message_store.get_or_create_conversation(contact_name, public_key, is_group=False)

        # Save a sent message
        ciphertext = b"encrypted_content"
        nonce = bytes(12)
        ephemeral_key = bytes.fromhex("03" * 32)
        salt = bytes(16)
        timestamp = int(time.time())

        message_store.save_message(
            conversation_id=conv_id,
            direction='sent',
            ciphertext=ciphertext,
            nonce=nonce,
            ephemeral_public_key=ephemeral_key,
            salt=salt,
            sender_name="Alice",
            recipient_name="Bob",
            timestamp=timestamp,
            is_group=False
        )

        # Retrieve messages
        messages = message_store.get_messages(conv_id)
        assert len(messages) == 1
        msg = messages[0]
        assert msg['sender_name'] == "Alice"
        assert msg['recipient_name'] == "Bob"
        assert msg['direction'] == 'sent'
        assert msg['ciphertext'] == ciphertext
        assert msg['nonce'] == nonce
        assert msg['ephemeral_public_key'] == ephemeral_key
        assert msg['salt'] == salt
        assert msg['timestamp'] == timestamp
        assert msg['is_group'] == False

    def test_save_and_get_message_group(self, message_store):
        """Test saving and retrieving group message."""
        group_name = "Team"
        group_key = bytes.fromhex("04" * 32)

        conv_id = message_store.get_or_create_conversation(group_name, group_key, is_group=True)

        # Save a received group message
        ciphertext = b"group_encrypted"
        nonce = bytes(12)
        ephemeral_key = bytes.fromhex("05" * 32)
        salt = bytes(16)
        timestamp = int(time.time())

        message_store.save_message(
            conversation_id=conv_id,
            direction='received',
            ciphertext=ciphertext,
            nonce=nonce,
            ephemeral_public_key=ephemeral_key,
            salt=salt,
            sender_name="Alice",
            recipient_name="Team",
            timestamp=timestamp,
            is_group=True
        )

        # Retrieve messages
        messages = message_store.get_messages(conv_id)
        assert len(messages) == 1
        msg = messages[0]
        assert msg['sender_name'] == "Alice"
        assert msg['recipient_name'] == "Team"
        assert msg['direction'] == 'received'
        assert msg['is_group'] == True

    def test_save_message_with_signature(self, message_store):
        """Test saving message with Ed25519 signature."""
        contact_name = "Charlie"
        public_key = bytes.fromhex("06" * 32)

        conv_id = message_store.get_or_create_conversation(contact_name, public_key, is_group=False)

        signature = bytes(64)  # Ed25519 signature

        message_store.save_message(
            conversation_id=conv_id,
            direction='sent',
            ciphertext=b"cipher",
            nonce=bytes(12),
            ephemeral_public_key=bytes.fromhex("07" * 32),
            salt=bytes(16),
            sender_name="Alice",
            recipient_name="Charlie",
            timestamp=int(time.time()),
            is_group=False,
            signature=signature
        )

        messages = message_store.get_messages(conv_id)
        assert len(messages) == 1
        assert messages[0]['signature'] == signature

    def test_save_message_with_ttl(self, message_store):
        """Test saving message with TTL."""
        contact_name = "Dave"
        public_key = bytes.fromhex("08" * 32)

        conv_id = message_store.get_or_create_conversation(contact_name, public_key, is_group=False)

        message_store.save_message(
            conversation_id=conv_id,
            direction='sent',
            ciphertext=b"cipher",
            nonce=bytes(12),
            ephemeral_public_key=bytes.fromhex("09" * 32),
            salt=bytes(16),
            sender_name="Alice",
            recipient_name="Dave",
            timestamp=int(time.time()),
            is_group=False,
            ttl=3600  # 1 hour
        )

        messages = message_store.get_messages(conv_id)
        assert len(messages) == 1
        assert messages[0]['ttl'] == 3600

    def test_get_messages_filters_expired(self, message_store):
        """Test that get_messages filters out expired TTL messages."""
        contact_name = "Eve"
        public_key = bytes.fromhex("0a" * 32)

        conv_id = message_store.get_or_create_conversation(contact_name, public_key, is_group=False)

        # Save expired message (TTL 1 second, timestamp in past)
        message_store.save_message(
            conversation_id=conv_id,
            direction='sent',
            ciphertext=b"expired",
            nonce=bytes(12),
            ephemeral_public_key=bytes.fromhex("0b" * 32),
            salt=bytes(16),
            sender_name="Alice",
            recipient_name="Eve",
            timestamp=int(time.time()) - 10,  # 10 seconds ago
            is_group=False,
            ttl=1  # 1 second TTL
        )

        # Save non-expired message
        message_store.save_message(
            conversation_id=conv_id,
            direction='sent',
            ciphertext=b"valid",
            nonce=bytes(12),
            ephemeral_public_key=bytes.fromhex("0c" * 32),
            salt=bytes(16),
            sender_name="Alice",
            recipient_name="Eve",
            timestamp=int(time.time()),
            is_group=False,
            ttl=3600
        )

        # Should only get the valid message
        messages = message_store.get_messages(conv_id)
        assert len(messages) == 1
        assert messages[0]['ciphertext'] == b"valid"

    def test_cleanup_expired_messages(self, message_store):
        """Test cleanup_expired_messages removes expired messages."""
        contact_name = "Frank"
        public_key = bytes.fromhex("0d" * 32)

        conv_id = message_store.get_or_create_conversation(contact_name, public_key, is_group=False)

        # Add expired message
        message_store.save_message(
            conversation_id=conv_id,
            direction='sent',
            ciphertext=b"expired",
            nonce=bytes(12),
            ephemeral_public_key=bytes.fromhex("0e" * 32),
            salt=bytes(16),
            sender_name="Alice",
            recipient_name="Frank",
            timestamp=int(time.time()) - 10,
            is_group=False,
            ttl=1
        )

        # Add valid message
        message_store.save_message(
            conversation_id=conv_id,
            direction='sent',
            ciphertext=b"valid",
            nonce=bytes(12),
            ephemeral_public_key=bytes.fromhex("0f" * 32),
            salt=bytes(16),
            sender_name="Alice",
            recipient_name="Frank",
            timestamp=int(time.time()),
            is_group=False,
            ttl=3600
        )

        # Cleanup
        removed = message_store.cleanup_expired_messages()
        assert removed == 1

        # Only valid message should remain
        messages = message_store.get_messages(conv_id)
        assert len(messages) == 1
        assert messages[0]['ciphertext'] == b"valid"

    def test_get_conversation_info(self, message_store):
        """Test getting conversation info."""
        contact_name = "Grace"
        public_key = bytes.fromhex("10" * 32)

        conv_id = message_store.get_or_create_conversation(contact_name, public_key, is_group=False)

        # Add a message
        message_store.save_message(
            conversation_id=conv_id,
            direction='sent',
            ciphertext=b"test",
            nonce=bytes(12),
            ephemeral_public_key=bytes.fromhex("11" * 32),
            salt=bytes(16),
            sender_name="Alice",
            recipient_name="Grace",
            timestamp=int(time.time()),
            is_group=False
        )

        info = message_store.get_conversation_info(contact_name, is_group=False)
        assert info is not None
        assert info['id'] == conv_id
        assert info['contact_name'] == contact_name
        assert info['contact_public_key'] == public_key
        assert info['is_group'] == False
        assert info['message_count'] == 1

    def test_get_conversation_info_not_found(self, message_store):
        """Test getting info for non-existent conversation."""
        info = message_store.get_conversation_info("NonExistent", is_group=False)
        assert info is None

    def test_list_conversations(self, message_store):
        """Test listing all conversations."""
        # Add multiple conversations
        for i, name in enumerate(["Alice", "Bob", "Charlie"]):
            public_key = bytes.fromhex(f"{i:02x}" * 32)
            conv_id = message_store.get_or_create_conversation(name, public_key, is_group=False)
            message_store.save_message(
                conversation_id=conv_id,
                direction='sent',
                ciphertext=b"test",
                nonce=bytes(12),
                ephemeral_public_key=bytes.fromhex(f"{i+10:02x}" * 32),
                salt=bytes(16),
                sender_name="Me",
                recipient_name=name,
                timestamp=int(time.time()),
                is_group=False
            )

        conversations = message_store.list_conversations()
        assert len(conversations) == 3
        names = [c['contact_name'] for c in conversations]
        assert "Alice" in names
        assert "Bob" in names
        assert "Charlie" in names

    def test_delete_conversation(self, message_store):
        """Test deleting conversation and its messages."""
        contact_name = "Henry"
        public_key = bytes.fromhex("12" * 32)

        conv_id = message_store.get_or_create_conversation(contact_name, public_key, is_group=False)

        # Add messages
        for i in range(3):
            message_store.save_message(
                conversation_id=conv_id,
                direction='sent',
                ciphertext=f"msg{i}".encode(),
                nonce=bytes(12),
                ephemeral_public_key=bytes.fromhex(f"{i:02x}" * 32),
                salt=bytes(16),
                sender_name="Alice",
                recipient_name="Henry",
                timestamp=int(time.time()),
                is_group=False
            )

        # Verify messages exist
        messages = message_store.get_messages(conv_id)
        assert len(messages) == 3

        # Delete conversation
        result = message_store.delete_conversation(contact_name, is_group=False)
        assert result is True

        # Messages should be gone
        messages = message_store.get_messages(conv_id)
        assert len(messages) == 0

        # Conversation info should be gone
        info = message_store.get_conversation_info(contact_name, is_group=False)
        assert info is None

    def test_delete_conversation_not_found(self, message_store):
        """Test deleting non-existent conversation."""
        result = message_store.delete_conversation("NonExistent", is_group=False)
        assert result is False

    def test_conversation_uniqueness(self, message_store):
        """Test that contact_name + is_group uniquely identifies conversation."""
        # Same name, different is_group should be different conversations
        public_key = bytes.fromhex("13" * 32)

        conv_id1 = message_store.get_or_create_conversation("Test", public_key, is_group=False)
        conv_id2 = message_store.get_or_create_conversation("Test", None, is_group=True)

        assert conv_id1 != conv_id2

    def test_message_edit_tracking(self, message_store):
        """Test saving messages with edit tracking."""
        contact_name = "Ivy"
        public_key = bytes.fromhex("14" * 32)

        conv_id = message_store.get_or_create_conversation(contact_name, public_key, is_group=False)

        # Save original message
        message_store.save_message(
            conversation_id=conv_id,
            direction='sent',
            ciphertext=b"original",
            nonce=bytes(12),
            ephemeral_public_key=bytes.fromhex("15" * 32),
            salt=bytes(16),
            sender_name="Alice",
            recipient_name="Ivy",
            timestamp=int(time.time()),
            is_group=False
        )

        # Save edit of that message
        message_store.save_message(
            conversation_id=conv_id,
            direction='sent',
            ciphertext=b"edited",
            nonce=bytes(12),
            ephemeral_public_key=bytes.fromhex("16" * 32),
            salt=bytes(16),
            sender_name="Alice",
            recipient_name="Ivy",
            timestamp=int(time.time()) + 1,
            is_group=False,
            edit_of_sender="Alice",
            edit_of_recipient="Ivy",
            edit_of_timestamp=1234567890
        )

        messages = message_store.get_messages(conv_id)
        assert len(messages) == 2

        # Find edit message
        edit_msg = next(m for m in messages if m['edit_of_sender'] == "Alice")
        assert edit_msg['edit_of_sender'] == "Alice"
        assert edit_msg['edit_of_recipient'] == "Ivy"
        assert edit_msg['edit_of_timestamp'] == 1234567890

    def test_message_delete_tracking(self, message_store):
        """Test saving messages with delete tracking."""
        contact_name = "Jack"
        public_key = bytes.fromhex("17" * 32)

        conv_id = message_store.get_or_create_conversation(contact_name, public_key, is_group=False)

        # Save delete message
        message_store.save_message(
            conversation_id=conv_id,
            direction='sent',
            ciphertext=b"",
            nonce=bytes(12),
            ephemeral_public_key=bytes.fromhex("18" * 32),
            salt=bytes(16),
            sender_name="Alice",
            recipient_name="Jack",
            timestamp=int(time.time()),
            is_group=False,
            delete_of_sender="Alice",
            delete_of_recipient="Jack",
            delete_of_timestamp=1234567890
        )

        messages = message_store.get_messages(conv_id)
        assert len(messages) == 1

        delete_msg = messages[0]
        assert delete_msg['delete_of_sender'] == "Alice"
        assert delete_msg['delete_of_recipient'] == "Jack"
        assert delete_msg['delete_of_timestamp'] == 1234567890


if __name__ == "__main__":
    pytest.main([__file__, "-v"])