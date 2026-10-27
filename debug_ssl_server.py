#!/usr/bin/env python3
"""
Debug SSL context creation for server.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from identity import IdentityManager
import ssl

def debug_ssl_context_server():
    """Debug SSL context creation for server."""
    print("Debugging SSL context creation for server...")

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

        print(f"Certificate data length: {len(alice_cert_data)} bytes")
        print(f"Key data length: {len(alice_key_data)} bytes")

        # Create temporary files and try to load with SSL as SERVER
        cert_file = None
        key_file = None
        try:
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as f:
                f.write(alice_cert_data)
                cert_file = f.name
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as f:
                f.write(alice_key_data)
                key_file = f.name

            print(f"Certificate file: {cert_file}")
            print(f"Key file: {key_file}")

            # Try to create SSL context as SERVER
            print("Trying to create SSL context as SERVER...")
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(cert_file, key_file)
            print("SUCCESS: SSL context created as SERVER with certificate and key!")

        except Exception as e:
            print(f"FAILED: Could not create SSL context as SERVER: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Clean up temporary files
            if cert_file:
                try:
                    os.unlink(cert_file)
                except:
                    pass
            if key_file:
                try:
                    os.unlink(key_file)
                except:
                    pass

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    debug_ssl_context_server()