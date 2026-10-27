#!/usr/bin/env python3
import sqlite3
import tempfile
import os
from pathlib import Path

# Create a temporary database
temp_dir = tempfile.mkdtemp()
db_path = Path(temp_dir) / "test.db"
print(f"Using database: {db_path}")

# Initialize a simple table with 1 column
with sqlite3.connect(db_path) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS test_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            value1 TEXT
        )
    """)
    conn.commit()

# Try to insert a row with 1 value
try:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO test_table (value1)
            VALUES (?)
            """,
            ("test",)
        )
        conn.commit()
        print("INSERT with 1 value successful!")
except Exception as e:
    print(f"INSERT with 1 value failed: {e}")

# Try to insert a row with 2 values (should fail)
try:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO test_table (value1)
            VALUES (?, ?)
            """,
            ("test", "extra")
        )
        conn.commit()
        print("INSERT with 2 values successful (unexpected)!")
except Exception as e:
    print(f"INSERT with 2 values failed as expected: {e}")

# Clean up
import shutil
shutil.rmtree(temp_dir)