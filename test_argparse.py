import argparse
import sys
import os
sys.path.insert(0, os.getcwd())

parser = argparse.ArgumentParser(
    description="Test"
)
parser.add_argument(
    "--username", "-u",
    required=True,
    help="Your username"
)
parser.add_argument(
    "--data-dir",
    default="./data",
    help="Data directory"
)

subparsers = parser.add_subparsers(dest="command", help="Available commands")
init_parser = subparsers.add_parser("init", help="Initialize")

try:
    args = parser.parse_args()
    print("Success!")
    print(f"Username: {args.username}")
    print(f"Data dir: {args.data_dir}")
    print(f"Command: {args.command}")
except Exception as e:
    print(f"Error: {e}")
