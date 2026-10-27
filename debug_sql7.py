#!/usr/bin/env python3
import sqlite3
import tempfile
import os
from pathlib import Path

# Create a temporary database
temp_dir = tempfile.mkdtemp()
db_path = Path(temp_dir) / "test.db"
print(f"Using database: {db_path}")

# Initialize a table with just the delete_of_sender column plus required columns
with sqlite3.connect(db_path) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            delete_of_sender TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )
    """)
    conn.commit()

# Try to insert a row with values for conversation_id and delete_of_sender
print("\n=== Testing delete_of_sender column ===")
try:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO messages
            (conversation_id, delete_of_sender)
            VALUES (?, ?)
            """,
            (1, "test")
        )
        conn.commit()
        print("SUCCESS: Inserted into delete_of_sender column")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()

# Clean up
import shutil
shutil.rmtree(temp_dir)