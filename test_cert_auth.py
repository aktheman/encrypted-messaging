#!/usr/bin/env python3
"""
Test certificate-based authentication.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from identity import IdentityManager
from messaging import SecureMessenger

def test_certificate_auth():
    """Test that certificate-based authentication works."""
    print("Testing certificate-based authentication...")

    # Create temporary directories for testing
    temp_dir = tempfile.mkdtemp()
    print(f"Using temporary directory: {temp_dir}")

    try:
        # Test identity generation with certificate
        data_dir = os.path.join(temp_dir, "data")
        identity_manager = IdentityManager(data_dir)

        # Generate identity with certificate
        print("Generating identity with certificate...")
        ec_priv, ec_pub, x25519_priv, x25519_pub, username, cert = identity_manager.generate_and_save_identity_with_cert("testuser")
        print(f"Generated identity for {username}")
        print(f"Certificate length: {len(cert)} bytes")

        # Load identity with certificate
        print("Loading identity with certificate...")
        loaded_identity = identity_manager.load_identity_with_cert()
        if loaded_identity:
            print("Successfully loaded identity with certificate")
            print(f"Username: {loaded_identity[4]}")
            print(f"Certificate length: {len(loaded_identity[5])} bytes")
        else:
            print("ERROR: Failed to load identity with certificate")
            return False

        # Test certificate validation
        print("Testing certificate validation...")
        is_valid, error_msg = identity_manager.validate_certificate(cert)
        if is_valid:
            print("Certificate validation successful")
        else:
            print(f"ERROR: Certificate validation failed: {error_msg}")
            return False

        # Test SecureMessenger with certificate auth
        print("Testing SecureMessenger with certificate auth...")
        messenger = SecureMessenger(
            username="testuser",
            data_dir=data_dir,
            queue_dir=os.path.join(temp_dir, "queue"),
            use_networking=False,  # Use file-based for simplicity
            auth_method="cert"
        )

        # Check that identity was loaded properly
        priv_key, pub_key, user = messenger.get_identity()
        print(f"SecureMessenger identity: {user}")
        print(f"Public key length: {len(pub_key)} bytes")

        print("Certificate-based authentication test completed successfully!")
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
    if test_certificate_auth():
        print("\n[PASS] Certificate-based authentication test passed!")
        sys.exit(0)
    else:
        print("\n[FAIL] Certificate-based authentication test failed!")
        sys.exit(1)