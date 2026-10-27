import sys
sys.argv = [
    "main.py",
    "init",
    "--username", "Alice",
    "--data-dir", "./test_ttl/alice",
    "--queue-dir", "./test_ttl/queue"
]
exec(open("main.py").read())
