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

# Prepare the values for Test 6 (adding delete_of_sender)
values = (1, 'received', b'x'*37, b'x'*12, b'x'*32, b'x'*16, 1791726478, 0, None, None, None, None, None)
print(f"Number of values: {len(values)}")
print(f"Values: {values}")

# Print the SQL statement we're going to use
sql = """
INSERT INTO messages
(conversation_id, direction, ciphertext, nonce, ephemeral_public_key, salt, timestamp, is_group, ttl,
 edit_of_sender, edit_of_recipient, edit_of_timestamp,
 delete_of_sender)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
print(f"SQL statement:\n{sql}")

# Try to insert
try:
    with sqlite3.connect(db_path) as conn:
        conn.execute(sql, values)
        conn.commit()
        print("SUCCESS: Inserted with delete_of_sender column")
except Exception as e:
    print(f"FAILED: {e}")
    # Let's also try to see what SQLite thinks the table schema is
    try:
        with sqlite3.connect(db_path) as conn2:
            cursor = conn2.execute("PRAGMA table_info(messages)")
            columns = cursor.fetchall()
            print("\nTable schema:")
            for col in columns:
                print(f"  {col[1]} ({col[2]}) - nullable: {col[3]=='0'}, default: {col[4]}, pk: {col[5]}")
    except Exception as e2:
        print(f"Error getting table schema: {e2}")

# Clean up
import shutil
shutil.rmtree(temp_dir)