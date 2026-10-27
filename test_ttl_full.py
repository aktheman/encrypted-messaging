import sys
import os
import time

# Add current directory to path so we can import main
sys.path.insert(0, os.getcwd())

def run_main_with_args(args_list):
    """Run main.py with given arguments"""
    sys.argv = ["main.py"] + args_list
    try:
        exec(open("main.py").read())
    except SystemExit:
        pass  # Expected when main() calls sys.exit()
    except Exception as e:
        print(f"Error running main: {e}")

# Clean up test directory
import shutil
if os.path.exists("./test_ttl"):
    shutil.rmtree("./test_ttl")
os.makedirs("./test_ttl/{alice,bob,queue}", exist_ok=True)

print("Setting up Alice...")
run_main_with_args([
    "init",
    "--username", "Alice",
    "--data-dir", "./test_ttl/alice",
    "--queue-dir", "./test_ttl/queue"
])

print("Setting up Bob...")
run_main_with_args([
    "init",
    "--username", "Bob",
    "--data-dir", "./test_ttl/bob",
    "--queue-dir", "./test_ttl/queue"
])

print("Alice adding Bob as contact...")
# Get Bob's public key first
sys.argv = ["main.py", "init", "--username", "Bob", "--data-dir", "./test_ttl/bob", "--queue-dir", "./test_ttl/queue"]
try:
    exec(open("main.py").read())
except SystemExit:
    pass

# Now get Bob's public key and add it to Alice's contacts
from messaging import SecureMessenger
bob_messenger = SecureMessenger("Bob", "./test_ttl/bob", "./test_ttl/queue")
_, bob_pubkey, _ = bob_messenger.get_identity()
alice_messenger = SecureMessenger("Alice", "./test_ttl/alice", "./test_ttl/queue")
alice_messenger.add_contact("Bob", bob_pubkey.hex())

print("Bob adding Alice as contact...")
# Get Alice's public key and add it to Bob's contacts
alice_messenger = SecureMessenger("Alice", "./test_ttl/alice", "./test_ttl/queue")
_, alice_pubkey, _ = alice_messenger.get_identity()
bob_messenger = SecureMessenger("Bob", "./test_ttl/bob", "./test_ttl/queue")
bob_messenger.add_contact("Alice", alice_pubkey.hex())

print("Sending regular message from Alice to Bob...")
run_main_with_args([
    "send",
    "--username", "Alice",
    "--data-dir", "./test_ttl/alice",
    "--queue-dir", "./test_ttl/queue",
    "Bob",
    "Hello Bob! This is a regular message."
])

print("Sending ephemeral message (TTL=5 seconds) from Alice to Bob...")
run_main_with_args([
    "send",
    "--username", "Alice",
    "--data-dir", "./test_ttl/alice",
    "--queue-dir", "./test_ttl/queue",
    "--ttl", "5",
    "Bob",
    "Hello Bob! This message will self-destruct in 5 seconds."
])

print("Simulating network transport...")
run_main_with_args([
    "simulate",
    "--username", "Alice",
    "--data-dir", "./test_ttl/alice",
    "--queue-dir", "./test_ttl/queue",
    "--delay", "0.1"
])

print("Checking conversation history for Bob (should see both messages)...")
run_main_with_args([
    "history",
    "--username", "Bob",
    "--data-dir", "./test_ttl/bob",
    "--queue-dir", "./test_ttl/queue",
    "Alice"
])

print("Waiting 6 seconds for ephemeral message to expire...")
time.sleep(6)

print("Checking conversation history for Bob after TTL expiry (should only see regular message)...")
run_main_with_args([
    "history",
    "--username", "Bob",
    "--data-dir", "./test_ttl/bob",
    "--queue-dir", "./test_ttl/queue",
    "Alice"
])

print("Test complete!")
