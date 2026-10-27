import sys
import os

# Add current directory to path so we can import main
sys.path.insert(0, os.getcwd())

# Import and run main with our arguments
sys.argv = [
    "main.py",
    "init",
    "--username", "Alice",
    "--data-dir", "./test_ttl/alice",
    "--queue-dir", "./test_ttl/queue"
]

# Execute main.py
exec(open("main.py").read())
