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

# Prepare the values tuple
values = (1, 'received', b'x'*37, b'x'*12, b'x'*32, b'x'*16, 1791726478, 0, None, None, None, None, None, None, None)
print(f"Number of values: {len(values)}")

# Try to insert with the original formatting (line breaks)
try:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO messages
            (conversation_id, direction, ciphertext, nonce, ephemeral_public_key, salt, timestamp, is_group, ttl,
             edit_of_sender, edit_of_recipient, edit_of_timestamp,
             delete_of_sender, delete_of_recipient, delete_of_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values
        )
        conn.commit()
        print("INSERT with line breaks successful!")
except Exception as e:
    print(f"INSERT with line breaks failed: {e}")

# Try to insert with all on one line
try:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, direction, ciphertext, nonce, ephemeral_public_key, salt, timestamp, is_group, ttl, edit_of_sender, edit_of_recipient, edit_of_timestamp, delete_of_sender, delete_of_recipient, delete_of_timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            values
        )
        conn.commit()
        print("INSERT on one line successful!")
except Exception as e:
    print(f"INSERT on one line failed: {e}")

# Clean up
import shutil
shutil.rmtree(temp_dir)