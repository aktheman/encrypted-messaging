#!/usr/bin/env python3
"""
Debug certificate data in more detail.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from identity import IdentityManager

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

        # Write certificate to file and display it
        cert_file = os.path.join(temp_dir, "debug_cert.pem")
        with open(cert_file, 'wb') as f:
            f.write(cert)

        print(f"Certificate written to {cert_file}")
        print("Certificate content:")
        print('-' * 50)
        try:
            print(cert.decode('utf-8'))
        except UnicodeDecodeError:
            print("Cannot display as UTF-8, showing hex:")
            print(cert.hex())
        print('-' * 50)

        # Try to load it with ssl using proper error handling
        import ssl
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            # Try with certificate only first
            ctx.load_verify_locations(cert_file)
            print("SSL context created with certificate as CA successfully")
        except Exception as e:
            print(f"Failed to load certificate as CA: {e}")

        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            # Try to load certificate and key (using cert as both for now)
            ctx.load_cert_chain(cert_file, cert_file)
            print("SSL context created with certificate and key successfully")
        except Exception as e:
            print(f"Failed to load certificate and key: {e}")

        # Try to understand what's in the certificate
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization

        try:
            parsed_cert = x509.load_pem_x509_certificate(cert, default_backend())
            print(f"Certificate parsed successfully")
            print(f"Subject: {parsed_cert.subject}")
            print(f"Issuer: {parsed_cert.issuer}")
            print(f"Public key algorithm: {parsed_cert.public_key().__class__.__name__}")

            # Check if it's actually a valid certificate
            print(f"Not before: {parsed_cert.not_valid_before}")
            print(f"Not after: {parsed_cert.not_valid_after}")

        except Exception as e:
            print(f"Failed to parse certificate with cryptography: {e}")
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
    debug_cert_data()