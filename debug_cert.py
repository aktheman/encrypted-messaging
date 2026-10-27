#!/usr/bin/env python3
"""
Debug certificate data.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from identity import IdentityManager
import ssl

def debug_cert_data():
    """Debug certificate data format."""
    print("Debugging certificate data...")

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
        print(f"EC private key length: {len(ec_priv)} bytes")
        print(f"EC public key length: {len(ec_pub)} bytes")
        print(f"X25519 private key length: {len(x25519_priv)} bytes")
        print(f"X25519 public key length: {len(x25519_pub)} bytes")
        print(f"Certificate length: {len(cert)} bytes")

        # Try to load the certificate data
        print("\nTrying to load certificate data...")
        print(f"First 100 bytes of cert: {cert[:100]}")

        # Check if it looks like PEM
        if cert.startswith(b'-----BEGIN CERTIFICATE-----'):
            print("Certificate appears to be in PEM format")
        else:
            print("Certificate does NOT appear to be in PEM format")
            print(f"Actual start: {cert[:50]}")

        # Try to load it with ssl

        # Create a temporary file with the certificate
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as f:
            f.write(cert)
            cert_file = f.name

        try:
            # Try to load as certificate
            cert_obj = ssl.PEM_cert_to_DER_cert(cert)
            print("Certificate loaded successfully with PEM_cert_to_DER_cert")
        except Exception as e:
            print(f"Failed to load with PEM_cert_to_DER_cert: {e}")

        # Try to create SSL context and load certificate
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.load_cert_chain(cert_file, cert_file)  # Using same file for cert and key for now
            print("SSL context created and certificate loaded successfully")
        except Exception as e:
            print(f"Failed to load certificate in SSL context: {e}")
        finally:
            try:
                os.unlink(cert_file)
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
    debug_cert_data()