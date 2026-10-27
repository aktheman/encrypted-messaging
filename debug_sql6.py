#!/usr/bin/env python3
import sqlite3
import tempfile
import os
from pathlib import Path

# Create a temporary database
temp_dir = tempfile.mkdtemp()
db_path = Path(temp_dir) / "test.db"
print(f"Using database: {db_path}")

# Initialize the database with the same schema as in storage.py
with sqlite3.connect(db_path) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            direction TEXT NOT NULL CHECK(direction IN ('sent', 'received')),
            ciphertext BLOB NOT NULL,
            nonce BLOB NOT NULL,
            ephemeral_public_key BLOB NOT NULL,
            salt BLOB NOT NULL,
            timestamp INTEGER NOT NULL,
            is_group BOOLEAN NOT NULL DEFAULT 0,
            ttl INTEGER,  -- NULL for permanent, seconds for ephemeral
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

# Test 1: Try inserting with just the required NOT NULL columns
print("\n=== Test 1: Only NOT NULL columns ===")
try:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO messages
            (conversation_id, direction, ciphertext, nonce, ephemeral_public_key, salt, timestamp, is_group)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, 'received', b'x'*37, b'x'*12, b'x'*32, b'x'*16, 1791726478, 0)
        )
        conn.commit()
        print("SUCCESS: Inserted with only NOT NULL columns")
except Exception as e:
    print(f"FAILED: {e}")

# Test 2: Try adding the ttl column (NULL allowed)
print("\n=== Test 2: Adding ttl column ===")
try:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO messages
            (conversation_id, direction, ciphertext, nonce, ephemeral_public_key, salt, timestamp, is_group, ttl)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, 'received', b'x'*37, b'x'*12, b'x'*32, b'x'*16, 1791726478, 0, None)
        )
        conn.commit()
        print("SUCCESS: Inserted with ttl column")
except Exception as e:
    print(f"FAILED: {e}")

# Test 3: Try adding the first edit column
print("\n=== Test 3: Adding edit_of_sender column ===")
try:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO messages
            (conversation_id, direction, ciphertext, nonce, ephemeral_public_key, salt, timestamp, is_group, ttl, edit_of_sender)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, 'received', b'x'*37, b'x'*12, b'x'*32, b'x'*16, 1791726478, 0, None, None)
        )
        conn.commit()
        print("SUCCESS: Inserted with edit_of_sender column")
except Exception as e:
    print(f"FAILED: {e}")

# Test 4: Try adding the second edit column
print("\n=== Test 4: Adding edit_of_recipient column ===")
try:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO messages
            (conversation_id, direction, ciphertext, nonce, ephemeral_public_key, salt, timestamp, is_group, ttl, edit_of_sender, edit_of_recipient)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, 'received', b'x'*37, b'x'*12, b'x'*32, b'x'*16, 1791726478, 0, None, None, None)
        )
        conn.commit()
        print("SUCCESS: Inserted with edit_of_recipient column")
except Exception as e:
    print(f"FAILED: {e}")

# Test 5: Try adding the third edit column
print("\n=== Test 5: Adding edit_of_timestamp column ===")
try:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO messages
            (conversation_id, direction, ciphertext, nonce, ephemeral_public_key, salt, timestamp, is_group, ttl, edit_of_sender, edit_of_recipient, edit_of_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, 'received', b'x'*37, b'x'*12, b'x'*32, b'x'*16, 1791726478, 0, None, None, None, None)
        )
        conn.commit()
        print("SUCCESS: Inserted with edit_of_timestamp column")
except Exception as e:
    print(f"FAILED: {e}")

# Test 6: Try adding the first delete column
print("\n=== Test 6: Adding delete_of_sender column ===")
try:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO messages
            (conversation_id, direction, ciphertext, nonce, ephemeral_public_key, salt, timestamp, is_group, ttl, edit_of_sender, edit_of_recipient, edit_of_timestamp, delete_of_sender)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, 'received', b'x'*37, b'x'*12, b'x'*32, b'x'*16, 1791726478, 0, None, None, None, None, None)
        )
        conn.commit()
        print("SUCCESS: Inserted with delete_of_sender column")
except Exception as e:
    print(f"FAILED: {e}")

# Test 7: Try adding the second delete column
print("\n=== Test 7: Adding delete_of_recipient column ===")
try:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO messages
            (conversation_id, direction, ciphertext, nonce, ephemeral_public_key, salt, timestamp, is_group, ttl, edit_of_sender, edit_of_recipient, edit_of_timestamp, delete_of_sender, delete_of_recipient)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, 'received', b'x'*37, b'x'*12, b'x'*32, b'x'*16, 1791726478, 0, None, None, None, None, None, None)
        )
        conn.commit()
        print("SUCCESS: Inserted with delete_of_recipient column")
except Exception as e:
    print(f"FAILED: {e}")

# Test 8: Try adding the third delete column (all columns)
print("\n=== Test 8: Adding delete_of_timestamp column (ALL COLUMNS) ===")
try:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO messages
            (conversation_id, direction, ciphertext, nonce, ephemeral_public_key, salt, timestamp, is_group, ttl, edit_of_sender, edit_of_recipient, edit_of_timestamp, delete_of_sender, delete_of_recipient, delete_of_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, 'received', b'x'*37, b'x'*12, b'x'*32, b'x'*16, 1791726478, 0, None, None, None, None, None, None, None)
        )
        conn.commit()
        print("SUCCESS: Inserted with ALL columns")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()

# Clean up
import shutil
shutil.rmtree(temp_dir)