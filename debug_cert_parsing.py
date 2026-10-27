#!/usr/bin/env python3
"""
Debug certificate parsing.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from identity import IdentityManager
from cryptography import x509
from cryptography.hazmat.primitives import serialization

def debug_cert_parsing():
    """Debug certificate parsing."""
    print("Debugging certificate parsing...")

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

        # Try to parse the certificate
        print("Trying to parse certificate with cryptography...")
        try:
            parsed_cert = x509.load_pem_x509_certificate(cert, None)  # None for default_backend in newer versions
            print("SUCCESS: Certificate parsed successfully!")
            print(f"Subject: {parsed_cert.subject}")
            print(f"Issuer: {parsed_cert.issuer}")
            print(f"Serial number: {parsed_cert.serial_number}")
            print(f"Not valid before: {parsed_cert.not_valid_before}")
            print(f"Not valid after: {parsed_cert.not_valid_after}")

            # Get the public key
            pub_key = parsed_cert.public_key()
            print(f"Public key type: {type(pub_key).__name__}")

        except Exception as e:
            print(f"FAILED: Could not parse certificate: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    debug_cert_parsing()