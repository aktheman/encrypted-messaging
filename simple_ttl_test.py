#!/usr/bin/env python3
"""
Simple test for TTL functionality in the encrypted messaging app.
This test uses the classes directly to avoid command-line parsing issues.
"""

import os
import sys
import time
import tempfile
import shutil
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.getcwd())

from messaging import SecureMessenger

def test_ttl_functionality():
    """Test that TTL functionality works correctly"""
    print("Testing TTL functionality...")
    
    # Create temporary directories for testing
    test_dir = Path(tempfile.mkdtemp(prefix="ttl_test_"))
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
        
        # Simulate network transport (move messages from outbox to inbox)
        print("\nSimulating network transport...")
        # Access the message queue directly to simulate transport
        if hasattr(alice_messenger.message_queue, '_deliver_message'):
            # File-based queue - simulate delivery
            outbox_path = queue_dir / "outbox"
            inbox_path = queue_dir / "inbox"
            
            if outbox_path.exists():
                for msg_file in outbox_path.glob("*.msg"):
                    # Read the message
                    with open(msg_file, 'r') as f:
                        message_data = f.read()
                    # Write to inbox (simulating network delivery)
                    (inbox_path / msg_file.name).write_text(message_data)
                    # Remove from outbox
                    msg_file.unlink()
        
        # Give Bob time to process the messages
        time.sleep(0.1)
        
        # Check what Bob received
        print("\nChecking Bob's received messages...")
        received = bob_messenger.receive_and_process_messages()
        print(f"Bob received {len(received)} message(s):")
        for sender, text in received:
            print(f"  From {sender}: {text}")
        
        # Check conversation history for Bob
        print("\nChecking Bob's conversation history with Alice...")
        history = bob_messenger.get_conversation_history("Alice", limit=10)
        print(f"Bob has {len(history)} message(s) in history:")
        for i, msg in enumerate(history):
            direction = ">>" if msg['direction'] == 'sent' else "<<"
            timestamp = time.strftime("%H:%M:%S", time.localtime(msg['timestamp']))
            print(f"  [{timestamp}] {direction} {msg['text']}")
        
        # Wait for TTL to expire (2 seconds + a bit more)
        print("\nWaiting 3 seconds for TTL to expire...")
        time.sleep(3)
        
        # Clean up expired messages from storage
        print("\nCleaning up expired messages...")
        alice_messenger.message_store.cleanup_expired_messages()
        bob_messenger.message_store.cleanup_expired_messages()
        
        # Check conversation history again after TTL expiry
        print("\nChecking Bob's conversation history after TTL expiry...")
        history_after = bob_messenger.get_conversation_history("Alice", limit=10)
        print(f"Bob has {len(history_after)} message(s) in history after cleanup:")
        for i, msg in enumerate(history_after):
            direction = ">>" if msg['direction'] == 'sent' else "<<"
            timestamp = time.strftime("%H:%M:%S", time.localtime(msg['timestamp']))
            print(f"  [{timestamp}] {direction} {msg['text']}")
        
        # Verify that we still have the regular message but the ephemeral one is gone
        regular_count = sum(1 for msg in history_after if "regular message" in msg['text'])
        ephemeral_count = sum(1 for msg in history_after if "self-destruct" in msg['text'])
        
        print(f"\nResults:")
        print(f"  Regular messages found: {regular_count} (expected: 1)")
        print(f"  Ephemeral messages found: {ephemeral_count} (expected: 0)")
        
        if regular_count == 1 and ephemeral_count == 0:
            print("\n* TTL test PASSED: Regular message preserved, ephemeral message expired correctly")
            return True
        else:
            print("\n* TTL test FAILED: Unexpected message counts")
            return False
            
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up test directory
        shutil.rmtree(test_dir, ignore_errors=True)

if __name__ == "__main__":
    success = test_ttl_functionality()
    sys.exit(0 if success else 1)
