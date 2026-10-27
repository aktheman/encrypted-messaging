#!/usr/bin/env python3
"""
Debug test for TTL functionality - checks raw database values
"""

import os
import sys
import time
import tempfile
import shutil
from pathlib import Path
import sqlite3

sys.path.insert(0, os.getcwd())

from messaging import SecureMessenger

def debug_ttl_functionality():
    """Debug TTL functionality by checking raw database values"""
    print("Debugging TTL functionality...")
    
    # Create temporary directories for testing
    test_dir = Path(tempfile.mkdtemp(prefix="debug_ttl_test_"))
    alice_dir = test_dir / "alice"
    bob_dir = test_dir / "bob"
    queue_dir = test_dir / "queue"
    
    alice_dir.mkdir(parents=True)
    bob_dir.mkdir(parents=True)
    queue_dir.mkdir(parents=True)
    
    try:
        # Create messengers for Alice and Bob
        alice_messenger = SecureMessenger(
            username="Alice",
            data_dir=str(alice_dir),
            queue_dir=str(queue_dir)
        )
        
        bob_messenger = SecureMessenger(
            username="Bob",
            data_dir=str(bob_dir),
            queue_dir=str(queue_dir)
        )
        
        # Exchange public keys
        _, alice_pubkey, _ = alice_messenger.get_identity()
        _, bob_pubkey, _ = bob_messenger.get_identity()
        
        alice_messenger.add_contact("Bob", bob_pubkey.hex())
        bob_messenger.add_contact("Alice", alice_pubkey.hex())
        
        print("* Identities exchanged and contacts added")
        
        # Send a regular message (no TTL)
        print("\nSending regular message...")
        result1 = alice_messenger.send_message("Bob", "Hello Bob! This is a regular message.")
        print(f"Regular message sent: {result1}")
        
        # Send an ephemeral message with 2-second TTL
        print("\nSending ephemeral message (TTL=2 seconds)...")
        result2 = alice_messenger.send_message("Bob", "Hello Bob! This message will self-destruct.", ttl=2)
        print(f"Ephemeral message sent: {result2}")
        
        # Simulate network transport
        print("\nSimulating network transport...")
        outbox_path = queue_dir / "outbox"
        inbox_path = queue_dir / "inbox"
        
        if outbox_path.exists():
            for msg_file in outbox_path.glob("*.msg"):
                with open(msg_file, 'r') as f:
                    message_data = f.read()
                (inbox_path / msg_file.name).write_text(message_data)
                msg_file.unlink()
        
        # Give Bob time to process the messages
        time.sleep(0.1)
        
        # Check what Bob received
        print("\nChecking Bob's received messages...")
        received = bob_messenger.receive_and_process_messages()
        print(f"Bob received {len(received)} message(s):")
        for sender, text in received:
            print(f"  From {sender}: {text}")
        
        # Now let's inspect the raw database to see what's actually stored
        print(f"\nInspecting Bob's database directly...")
        conn = sqlite3.connect(str(bob_dir / "messaging.db"))
        conn.row_factory = sqlite3.Row
        
        # Check conversations
        print("\nConversations:")
        cursor = conn.execute("SELECT * FROM conversations")
        for row in cursor.fetchall():
            print(f"  {dict(row)}")
        
        # Check messages
        print("\nMessages:")
        cursor = conn.execute("SELECT * FROM messages")
        messages = cursor.fetchall()
        for i, row in enumerate(messages):
            msg_dict = dict(row)
            print(f"  Message {i}:")
            for key, value in msg_dict.items():
                print(f"    {key}: {value}")
            
            # Calculate if message should be expired
            if msg_dict['ttl'] is not None:
                expiry_time = msg_dict['timestamp'] + msg_dict['ttl']
                current_time = int(time.time())
                is_expired = current_time >= expiry_time
                print(f"    TTL: {msg_dict['ttl']} seconds")
                print(f"    Timestamp: {msg_dict['timestamp']}")
                print(f"    Expires at: {expiry_time}")
                print(f"    Current time: {current_time}")
                print(f"    Is expired: {is_expired}")
            else:
                print(f"    TTL: None (permanent)")
            print()
        
        conn.close()
        
        # Wait for TTL to expire
        print("\nWaiting 3 seconds for TTL to expire...")
        time.sleep(3)
        
        # Check database again after waiting
        print(f"\nInspecting Bob's database after waiting...")
        conn = sqlite3.connect(str(bob_dir / "messaging.db"))
        conn.row_factory = sqlite3.Row
        
        # Check messages
        print("\nMessages after waiting:")
        cursor = conn.execute("SELECT * FROM messages")
        messages = cursor.fetchall()
        for i, row in enumerate(messages):
            msg_dict = dict(row)
            print(f"  Message {i}:")
            for key, value in msg_dict.items():
                print(f"    {key}: {value}")
            
            # Calculate if message should be expired
            if msg_dict['ttl'] is not None:
                expiry_time = msg_dict['timestamp'] + msg_dict['ttl']
                current_time = int(time.time())
                is_expired = current_time >= expiry_time
                print(f"    TTL: {msg_dict['ttl']} seconds")
                print(f"    Timestamp: {msg_dict['timestamp']}")
                print(f"    Expires at: {expiry_time}")
                print(f"    Current time: {current_time}")
                print(f"    Is expired: {is_expired}")
            else:
                print(f"    TTL: None (permanent)")
            print()
        
        conn.close()
        
        # Now test the actual get_messages method
        print("\nTesting get_messages method...")
        history = bob_messenger.get_conversation_history("Alice", limit=10)
        print(f"get_conversation_history returned {len(history)} messages:")
        for i, msg in enumerate(history):
            direction = ">>" if msg['direction'] == 'sent' else "<<"
            timestamp = time.strftime("%H:%M:%S", time.localtime(msg['timestamp']))
            print(f"  [{timestamp}] {direction} {msg['text']}")
        
        # Test cleanup
        print("\nTesting cleanup_expired_messages...")
        removed_count = bob_messenger.message_store.cleanup_expired_messages()
        print(f"cleanup_expired_messages removed {removed_count} messages")
        
        # Check history again after cleanup
        print("\nTesting get_messages method after cleanup...")
        history_after = bob_messenger.get_conversation_history("Alice", limit=10)
        print(f"get_conversation_history returned {len(history_after)} messages after cleanup:")
        for i, msg in enumerate(history_after):
            direction = ">>" if msg['direction'] == 'sent' else "<<"
            timestamp = time.strftime("%H:%M:%S", time.localtime(msg['timestamp']))
            print(f"  [{timestamp}] {direction} {msg['text']}")
        
        return True
            
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up test directory
        shutil.rmtree(test_dir, ignore_errors=True)

if __name__ == "__main__":
    success = debug_ttl_functionality()
    sys.exit(0 if success else 1)
