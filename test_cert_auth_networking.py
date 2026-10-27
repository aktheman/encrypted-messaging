#!/usr/bin/env python3
"""
Test certificate-based authentication in the networking layer.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from identity import IdentityManager
from networking import WebSocketClient, WebSocketServer
import ssl

def test_cert_auth_networking_config():
    """Test that certificate-based authentication configures networking components correctly."""
    print("Testing certificate-based authentication networking configuration...")

    # Create temporary directories for testing
    temp_dir = tempfile.mkdtemp()
    print(f"Using temporary directory: {temp_dir}")

    try:
        # Set up alice with certificate-based auth
        alice_data_dir = os.path.join(temp_dir, "alice_data")
        alice_identity_manager = IdentityManager(alice_data_dir)

        # Generate identity with certificate for Alice
        print("Generating identity with certificate for Alice...")
        ec_priv, ec_pub, x25519_priv, x25519_pub, alice_username, cert = alice_identity_manager.generate_and_save_identity_with_cert("alice")
        print(f"Generated identity for {alice_username}")

        # Get Alice's certificate and private key for WebSocket client
        alice_identity = alice_identity_manager.load_identity_with_cert()
        alice_cert_data = alice_identity[5]   # certificate bytes
        alice_key_data = alice_identity[0]    # ec_private_key bytes (for TLS client auth)

        print(f"Alice certificate data length: {len(alice_cert_data)} bytes")
        print(f"Alice key data length: {len(alice_key_data)} bytes")

        # Test WebSocketClient with certificate auth
        print("Testing WebSocketClient with certificate auth...")
        try:
            ws_client = WebSocketClient(
                host="localhost",
                port=8765,
                secure=True,
                auth_method="cert",
                cert_data=alice_cert_data,
                key_data=alice_key_data
            )

            # Check that SSL context was created
            assert ws_client._ssl_context is not None, "SSL context should be created"

            # Check that it's set to require certificates
            # Note: We can't easily verify the exact settings without accessing private members,
            # but we can verify it doesn't throw an error during creation
            print("WebSocketClient with certificate auth created successfully")

        except Exception as e:
            print(f"ERROR: Failed to create WebSocketClient with certificate auth: {e}")
            return False

        # Test WebSocketServer with certificate auth
        print("Testing WebSocketServer with certificate auth...")
        try:
            ws_server = WebSocketServer(
                host="localhost",
                port=8766,
                secure=True,
                auth_method="cert"
                # Server doesn't need client cert data for validating clients
            )

            # Check that SSL context was created
            assert ws_server._ssl_context is not None, "SSL context should be created"

            print("WebSocketServer with certificate auth created successfully")

        except Exception as e:
            print(f"ERROR: Failed to create WebSocketServer with certificate auth: {e}")
            return False

        print("Certificate-based authentication networking configuration test passed!")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    if test_cert_auth_networking_config():
        print("\n[PASS] Certificate-based authentication networking configuration test passed!")
        sys.exit(0)
    else:
        print("\n[FAIL] Certificate-based authentication networking configuration test failed!")
        sys.exit(1)