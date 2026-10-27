"""
Unit tests for identity management (IdentityManager, ContactManager).
"""
import pytest
import os
import sys
import tempfile
import shutil
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from identity import IdentityManager, ContactManager
from crypto import (
    generate_identity_keypair,
    serialize_public_key,
    generate_signing_keypair,
    serialize_signing_public_key,
)


class TestIdentityManager:
    """Tests for IdentityManager class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def identity_manager(self, temp_dir):
        """Create an IdentityManager instance with temporary directory."""
        return IdentityManager(temp_dir)

    def test_generate_and_load_identity(self, identity_manager):
        """Test generating and loading identity."""
        username = "Alice"
        private_key, public_key = identity_manager.generate_and_save_identity(username)

        assert len(private_key) == 32
        assert len(public_key) == 32

        # Load identity
        loaded = identity_manager.load_identity()
        assert loaded is not None
        loaded_private, loaded_public, loaded_username = loaded
        assert loaded_private == private_key
        assert loaded_public == public_key
        assert loaded_username == username

    def test_load_nonexistent_identity(self, identity_manager):
        """Test loading identity when none exists."""
        loaded = identity_manager.load_identity()
        assert loaded is None

    def test_get_public_key_bytes(self, identity_manager):
        """Test getting public key bytes."""
        identity_manager.generate_and_save_identity("Bob")
        public_key = identity_manager.get_public_key_bytes()
        assert public_key is not None
        assert len(public_key) == 32

    def test_get_public_key_hex(self, identity_manager):
        """Test getting public key as hex."""
        identity_manager.generate_and_save_identity("Charlie")
        public_key_hex = identity_manager.get_public_key_hex()
        assert public_key_hex is not None
        assert len(public_key_hex) == 64  # 32 bytes = 64 hex chars

    def test_get_signing_keys(self, identity_manager):
        """Test getting Ed25519 signing keys."""
        identity_manager.generate_and_save_identity("Dave")

        signing_public = identity_manager.get_signing_public_key_bytes()
        signing_private = identity_manager.get_signing_private_key_bytes()

        assert signing_public is not None
        assert len(signing_public) == 32
        assert signing_private is not None
        assert len(signing_private) == 32

    def test_get_signing_public_key_hex(self, identity_manager):
        """Test getting signing public key as hex."""
        identity_manager.generate_and_save_identity("Eve")
        signing_hex = identity_manager.get_signing_public_key_hex()
        assert signing_hex is not None
        assert len(signing_hex) == 64

    def test_delete_identity(self, identity_manager):
        """Test deleting identity."""
        identity_manager.generate_and_save_identity("Frank")
        assert identity_manager.load_identity() is not None

        result = identity_manager.delete_identity()
        assert result is True
        assert identity_manager.load_identity() is None

        # Deleting again should return False
        result = identity_manager.delete_identity()
        assert result is False

    def test_load_identity_with_signing_keys(self, identity_manager):
        """Test loading identity with signing keys."""
        identity_manager.generate_and_save_identity("Grace")

        loaded = identity_manager.load_identity_with_signing_keys()
        assert loaded is not None
        private_key, public_key, signing_private, signing_public, username = loaded

        assert username == "Grace"
        assert len(private_key) == 32
        assert len(public_key) == 32
        assert len(signing_private) == 32
        assert len(signing_public) == 32


class TestContactManager:
    """Tests for ContactManager class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def contact_manager(self, temp_dir):
        """Create a ContactManager instance with temporary directory."""
        return ContactManager(temp_dir)

    def test_add_contact(self, contact_manager):
        """Test adding a contact."""
        public_key_hex = "01" * 32
        result = contact_manager.add_contact("Alice", public_key_hex)
        assert result is True

        contacts = contact_manager.load_contacts()
        assert "Alice" in contacts
        assert contacts["Alice"]["public_key"] == public_key_hex
        assert contacts["Alice"]["trust_level"] == 0

    def test_add_contact_with_trust_level(self, contact_manager):
        """Test adding a contact with specific trust level."""
        public_key_hex = "02" * 32
        contact_manager.add_contact("Bob", public_key_hex, trust_level=1)

        contacts = contact_manager.load_contacts()
        assert contacts["Bob"]["trust_level"] == 1
        assert contacts["Bob"]["verified_at"] is not None

    def test_add_contact_with_signing_key(self, contact_manager):
        """Test adding a contact with Ed25519 signing key."""
        public_key_hex = "03" * 32
        signing_key_hex = "04" * 32  # Ed25519 public key is 32 bytes = 64 hex chars

        contact_manager.add_contact("Charlie", public_key_hex, signing_key_hex=signing_key_hex)

        contacts = contact_manager.load_contacts()
        assert "Charlie" in contacts
        assert contacts["Charlie"]["public_key"] == public_key_hex
        assert contacts["Charlie"]["signing_key"] == signing_key_hex

    def test_get_contact_public_key(self, contact_manager):
        """Test getting contact's public key."""
        public_key_hex = "05" * 32
        contact_manager.add_contact("Dave", public_key_hex)

        key = contact_manager.get_contact_public_key("Dave")
        assert key is not None
        assert key.hex() == public_key_hex

    def test_get_contact_public_key_blocked(self, contact_manager):
        """Test that blocked contacts return None for public key."""
        public_key_hex = "06" * 32
        contact_manager.add_contact("Eve", public_key_hex, trust_level=2)

        key = contact_manager.get_contact_public_key("Eve")
        assert key is None

    def test_get_contact_signing_key(self, contact_manager):
        """Test getting contact's signing key."""
        public_key_hex = "07" * 32
        signing_key_hex = "08" * 32
        contact_manager.add_contact("Frank", public_key_hex, signing_key_hex=signing_key_hex)

        key = contact_manager.get_contact_signing_key("Frank")
        assert key is not None
        assert key.hex() == signing_key_hex

    def test_get_contact_signing_key_not_found(self, contact_manager):
        """Test getting signing key for contact without one."""
        public_key_hex = "09" * 32
        contact_manager.add_contact("Grace", public_key_hex)

        key = contact_manager.get_contact_signing_key("Grace")
        assert key is None

    def test_list_contacts(self, contact_manager):
        """Test listing all contacts."""
        contact_manager.add_contact("Alice", "01" * 32)
        contact_manager.add_contact("Bob", "02" * 32, trust_level=1)

        contacts = contact_manager.list_contacts()
        assert len(contacts) == 2
        assert "Alice" in contacts
        assert "Bob" in contacts

    def test_get_contact_trust_level(self, contact_manager):
        """Test getting contact trust level."""
        contact_manager.add_contact("Alice", "01" * 32)  # default trust_level=0
        contact_manager.add_contact("Bob", "02" * 32, trust_level=1)
        contact_manager.add_contact("Charlie", "03" * 32, trust_level=2)

        assert contact_manager.get_contact_trust_level("Alice") == 0
        assert contact_manager.get_contact_trust_level("Bob") == 1
        assert contact_manager.get_contact_trust_level("Charlie") == 2
        assert contact_manager.get_contact_trust_level("NonExistent") == 0

    def test_set_contact_trust_level(self, contact_manager):
        """Test setting contact trust level."""
        contact_manager.add_contact("Dave", "01" * 32)

        # Set to trusted
        result = contact_manager.set_contact_trust_level("Dave", 1)
        assert result is True
        assert contact_manager.get_contact_trust_level("Dave") == 1
        assert contact_manager.load_contacts()["Dave"]["verified_at"] is not None

        # Set to blocked
        result = contact_manager.set_contact_trust_level("Dave", 2)
        assert result is True
        assert contact_manager.get_contact_trust_level("Dave") == 2
        assert contact_manager.load_contacts()["Dave"]["verified_at"] is None

        # Set back to unknown
        result = contact_manager.set_contact_trust_level("Dave", 0)
        assert result is True
        assert contact_manager.get_contact_trust_level("Dave") == 0

    def test_set_trust_level_nonexistent(self, contact_manager):
        """Test setting trust level for non-existent contact."""
        result = contact_manager.set_contact_trust_level("NonExistent", 1)
        assert result is False

    def test_trust_contact(self, contact_manager):
        """Test trust_contact shortcut."""
        contact_manager.add_contact("Eve", "01" * 32)
        assert contact_manager.trust_contact("Eve") is True
        assert contact_manager.get_contact_trust_level("Eve") == 1

    def test_block_contact(self, contact_manager):
        """Test block_contact shortcut."""
        contact_manager.add_contact("Frank", "01" * 32)
        assert contact_manager.block_contact("Frank") is True
        assert contact_manager.get_contact_trust_level("Frank") == 2

    def test_remove_contact(self, contact_manager):
        """Test removing a contact."""
        contact_manager.add_contact("Grace", "01" * 32)
        assert contact_manager.remove_contact("Grace") is True
        assert "Grace" not in contact_manager.load_contacts()

        # Removing again should return False
        assert contact_manager.remove_contact("Grace") is False

    def test_add_pending_contact(self, contact_manager):
        """Test adding pending contact (TOFU)."""
        result = contact_manager.add_pending_contact("Helen", "01" * 32)
        assert result is True

        pending = contact_manager.get_pending_contacts()
        assert "Helen" in pending
        assert pending["Helen"]["trust_level"] == 0

    def test_get_pending_contacts(self, contact_manager):
        """Test getting pending contacts."""
        contact_manager.add_contact("Alice", "01" * 32)  # unknown
        contact_manager.add_contact("Bob", "02" * 32, trust_level=1)  # trusted
        contact_manager.add_contact("Charlie", "03" * 32, trust_level=2)  # blocked

        pending = contact_manager.get_pending_contacts()
        assert len(pending) == 1
        assert "Alice" in pending

    def test_get_trusted_contacts(self, contact_manager):
        """Test getting trusted contacts."""
        contact_manager.add_contact("Alice", "01" * 32)
        contact_manager.add_contact("Bob", "02" * 32, trust_level=1)
        contact_manager.add_contact("Charlie", "03" * 32, trust_level=2)

        trusted = contact_manager.get_trusted_contacts()
        assert len(trusted) == 1
        assert "Bob" in trusted

    def test_get_blocked_contacts(self, contact_manager):
        """Test getting blocked contacts."""
        contact_manager.add_contact("Alice", "01" * 32)
        contact_manager.add_contact("Bob", "02" * 32, trust_level=1)
        contact_manager.add_contact("Charlie", "03" * 32, trust_level=2)

        blocked = contact_manager.get_blocked_contacts()
        assert len(blocked) == 1
        assert "Charlie" in blocked

    def test_preserve_trust_level_on_update(self, contact_manager):
        """Test that updating contact preserves trust level."""
        contact_manager.add_contact("Alice", "01" * 32, trust_level=1)
        # Update with trust_level=0 (default) should preserve existing trust level
        contact_manager.add_contact("Alice", "01" * 32, trust_level=0)

        assert contact_manager.get_contact_trust_level("Alice") == 1

    def test_update_public_key_preserves_trust(self, contact_manager):
        """Test that updating public key preserves trust level."""
        contact_manager.add_contact("Bob", "01" * 32, trust_level=1)
        contact_manager.add_contact("Bob", "02" * 32)  # Different key

        contacts = contact_manager.load_contacts()
        assert contacts["Bob"]["public_key"] == "02" * 32
        assert contacts["Bob"]["trust_level"] == 1


class TestGroupManagement:
    """Tests for group management in ContactManager."""

    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def contact_manager(self, temp_dir):
        return ContactManager(temp_dir)

    def test_create_group(self, contact_manager):
        """Test creating a group."""
        # Add members as contacts first
        contact_manager.add_contact("Alice", "01" * 32)
        contact_manager.add_contact("Bob", "02" * 32)

        result = contact_manager.create_group("Team", ["Alice", "Bob"], creator="Charlie")
        assert result is True

        groups = contact_manager.load_groups()
        assert "Team" in groups
        assert set(groups["Team"]["members"]) == {"Alice", "Bob", "Charlie"}

    def test_create_group_creator_not_in_contacts(self, contact_manager):
        """Test creating group where creator is not in contacts (should work)."""
        contact_manager.add_contact("Alice", "01" * 32)
        contact_manager.add_contact("Bob", "02" * 32)

        # Creator "Charlie" is not in contacts - should still work
        result = contact_manager.create_group("Team", ["Alice", "Bob"], creator="Charlie")
        assert result is True

        groups = contact_manager.load_groups()
        assert "Charlie" in groups["Team"]["members"]

    def test_create_group_member_not_in_contacts(self, contact_manager):
        """Test creating group with member not in contacts (should fail)."""
        contact_manager.add_contact("Alice", "01" * 32)

        # Bob is not in contacts
        result = contact_manager.create_group("Team", ["Alice", "Bob"], creator="Alice")
        assert result is False

    def test_create_duplicate_group(self, contact_manager):
        """Test creating duplicate group fails."""
        contact_manager.add_contact("Alice", "01" * 32)
        contact_manager.add_contact("Bob", "02" * 32)

        contact_manager.create_group("Team", ["Alice", "Bob"], creator="Charlie")
        result = contact_manager.create_group("Team", ["Alice", "Bob"], creator="Charlie")
        assert result is False

    def test_add_group_member(self, contact_manager):
        """Test adding member to group."""
        contact_manager.add_contact("Alice", "01" * 32)
        contact_manager.add_contact("Bob", "02" * 32)
        contact_manager.add_contact("Charlie", "03" * 32)

        contact_manager.create_group("Team", ["Alice", "Bob"], creator="Alice")
        result = contact_manager.add_group_member("Team", "Charlie")
        assert result is True

        members = contact_manager.get_group_members("Team")
        assert "Charlie" in members

    def test_add_group_member_nonexistent_group(self, contact_manager):
        """Test adding member to non-existent group."""
        contact_manager.add_contact("Alice", "01" * 32)
        result = contact_manager.add_group_member("NonExistent", "Alice")
        assert result is False

    def test_add_group_member_not_in_contacts(self, contact_manager):
        """Test adding member not in contacts to group."""
        contact_manager.add_contact("Alice", "01" * 32)
        contact_manager.create_group("Team", ["Alice"], creator="Alice")

        result = contact_manager.add_group_member("Team", "NonExistent")
        assert result is False

    def test_remove_group_member(self, contact_manager):
        """Test removing member from group."""
        contact_manager.add_contact("Alice", "01" * 32)
        contact_manager.add_contact("Bob", "02" * 32)

        contact_manager.create_group("Team", ["Alice", "Bob"], creator="Alice")
        result = contact_manager.remove_group_member("Team", "Bob")
        assert result is True

        members = contact_manager.get_group_members("Team")
        assert "Bob" not in members
        assert "Alice" in members

    def test_remove_group_member_not_in_group(self, contact_manager):
        """Test removing member not in group (should return True)."""
        contact_manager.add_contact("Alice", "01" * 32)
        contact_manager.create_group("Team", ["Alice"], creator="Alice")

        result = contact_manager.remove_group_member("Team", "Bob")
        assert result is True  # Nothing to do, but not an error

    def test_get_group_members(self, contact_manager):
        """Test getting group members."""
        contact_manager.add_contact("Alice", "01" * 32)
        contact_manager.add_contact("Bob", "02" * 32)
        contact_manager.add_contact("Charlie", "03" * 32)

        contact_manager.create_group("Team", ["Alice", "Bob"], creator="Charlie")

        members = contact_manager.get_group_members("Team")
        assert set(members) == {"Alice", "Bob", "Charlie"}

    def test_get_group_members_nonexistent(self, contact_manager):
        """Test getting members of non-existent group."""
        members = contact_manager.get_group_members("NonExistent")
        assert members == []

    def test_list_groups(self, contact_manager):
        """Test listing groups."""
        contact_manager.add_contact("Alice", "01" * 32)
        contact_manager.add_contact("Bob", "02" * 32)

        contact_manager.create_group("Team1", ["Alice", "Bob"], creator="Alice")
        contact_manager.create_group("Team2", ["Alice"], creator="Bob")

        groups = contact_manager.load_groups()
        assert len(groups) == 2
        assert "Team1" in groups
        assert "Team2" in groups

    def test_delete_group(self, contact_manager):
        """Test deleting a group."""
        contact_manager.add_contact("Alice", "01" * 32)
        contact_manager.add_contact("Bob", "02" * 32)

        contact_manager.create_group("Team", ["Alice", "Bob"], creator="Alice")
        result = contact_manager.delete_group("Team")
        assert result is True

        groups = contact_manager.load_groups()
        assert "Team" not in groups

    def test_delete_nonexistent_group(self, contact_manager):
        """Test deleting non-existent group."""
        result = contact_manager.delete_group("NonExistent")
        assert result is False

    def test_is_contact_in_group(self, contact_manager):
        """Test checking if contact is in group."""
        contact_manager.add_contact("Alice", "01" * 32)
        contact_manager.add_contact("Bob", "02" * 32)

        contact_manager.create_group("Team", ["Alice", "Bob"], creator="Charlie")

        assert contact_manager.is_contact_in_group("Team", "Alice") is True
        assert contact_manager.is_contact_in_group("Team", "Bob") is True
        assert contact_manager.is_contact_in_group("Team", "Charlie") is True
        assert contact_manager.is_contact_in_group("Team", "Dave") is False
        assert contact_manager.is_contact_in_group("NonExistent", "Alice") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])