#!/usr/bin/env python3
"""
Test script to verify TLS functionality in the networking layer.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from networking import WebSocketServer, WebSocketClient
import threading
import time

def test_tls_server_creation():
    """Test that we can create a TLS-enabled WebSocket server."""
    print("Testing TLS WebSocket server creation...")
    try:
        server = WebSocketServer("localhost", 8766, secure=True)
        print("[PASS] TLS WebSocket server created successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Failed to create TLS WebSocket server: {e}")
        return False

def test_tls_client_creation():
    """Test that we can create a TLS-enabled WebSocket client."""
    print("Testing TLS WebSocket client creation...")
    try:
        client = WebSocketClient("localhost", 8766, secure=True)
        print("[PASS] TLS WebSocket client created successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Failed to create TLS WebSocket client: {e}")
        return False

def test_certificates_exist():
    """Test that certificate files exist."""
    print("Testing certificate files existence...")
    cert_path = os.path.join(os.path.dirname(__file__), "certs", "cert.pem")
    key_path = os.path.join(os.path.dirname(__file__), "certs", "key.pem")

    if os.path.exists(cert_path) and os.path.exists(key_path):
        print("[PASS] Certificate files exist")
        return True
    else:
        print(f"[FAIL] Certificate files missing: cert={os.path.exists(cert_path)}, key={os.path.exists(key_path)}")
        return False

if __name__ == "__main__":
    print("=== TLS Networking Test ===\n")

    tests = [
        test_certificates_exist,
        test_tls_server_creation,
        test_tls_client_creation
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print(f"=== Results: {passed}/{total} tests passed ===")

    if passed == total:
        print("[PASS] All TLS tests passed!")
        sys.exit(0)
    else:
        print("[FAIL] Some tests failed!")
        sys.exit(1)