#!/usr/bin/env python3

import sys
sys.path.insert(0, '.')

from crypto import *
from identity import IdentityManager

def test_key_derivation():
    """Test that Alice and Bob derive the same keys."""
    print("=== Testing Key Derivation ===")

    # Initialize Alice and Bob
    alice_id = IdentityManager("./test_alice")
    bob_id = IdentityManager("./test_bob")

    # Generate identities if needed
    alice_priv_bytes, alice_pub_bytes = alice_id.generate_and_save_identity("alice")
    bob_priv_bytes, bob_pub_bytes = bob_id.generate_and_save_identity("bob")
    alice_username = "alice"
    bob_username = "bob"

    print(f"Alice username: {alice_username}")
    print(f"Bob username: {bob_username}")

    # Deserialize keys
    alice_priv = deserialize_private_key(alice_priv_bytes)
    alice_pub = deserialize_public_key(alice_pub_bytes)
    bob_priv = deserialize_private_key(bob_priv_bytes)
    bob_pub = deserialize_public_key(bob_pub_bytes)

    print(f"Alice public key: {alice_pub_bytes.hex()}")
    print(f"Bob public key: {bob_pub_bytes.hex()}")

    # Simulate Alice sending a message to Bob
    print("\n--- Alice's computation (sending to Bob) ---")

    # Alice generates ephemeral key pair
    alice_eph_priv, alice_eph_pub = generate_ephemeral_keypair()
    print(f"Alice ephemeral public key: {serialize_public_key(alice_eph_pub).hex()}")

    # Alice computes DH: her ephemeral private + Bob's identity public
    alice_shared_eph = perform_dh_key_exchange(alice_eph_priv, bob_pub)
    print(f"Alice shared secret (ephemeral): {alice_shared_eph.hex()}")

    # Alice computes DH: her identity private + Bob's identity public
    alice_shared_id = perform_dh_key_exchange(alice_priv, bob_pub)
    print(f"Alice shared secret (identity): {alice_shared_id.hex()}")

    # Alice combines secrets
    alice_combined = alice_shared_eph + alice_shared_id
    print(f"Alice combined secret: {alice_combined.hex()}")

    # Alice derives key
    alice_key, alice_salt = derive_key(alice_combined)
    print(f"Alice derived key: {alice_key.hex()}")
    print(f"Alice salt: {alice_salt.hex()}")

    # Simulate Bob receiving the message from Alice
    print("\n--- Bob's computation (receiving from Alice) ---")

    # Bob gets Alice's ephemeral public key from message (simulated)
    bob_eph_pub_from_msg = alice_eph_pub  # This is what Alice sent
    print(f"Bob received ephemeral public key: {serialize_public_key(bob_eph_pub_from_msg).hex()}")

    # Bob computes DH: his identity private + Alice's ephemeral public
    bob_shared_eph = perform_dh_key_exchange(bob_priv, bob_eph_pub_from_msg)
    print(f"Bob shared secret (ephemeral): {bob_shared_eph.hex()}")

    # Bob computes DH: his identity private + Alice's identity public
    bob_shared_id = perform_dh_key_exchange(bob_priv, alice_pub)
    print(f"Bob shared secret (identity): {bob_shared_id.hex()}")

    # Bob combines secrets
    bob_combined = bob_shared_eph + bob_shared_id
    print(f"Bob combined secret: {bob_combined.hex()}")

    # Bob derives key
    bob_key, bob_salt = derive_key(bob_combined)
    print(f"Bob derived key: {bob_key.hex()}")
    print(f"Bob salt: {bob_salt.hex()}")

    # Compare
    print("\n--- Comparison ---")
    print(f"Combined secrets equal: {alice_combined == bob_combined}")
    print(f"Derived keys equal: {alice_key == bob_key}")
    print(f"Salts equal: {alice_salt == bob_salt}")

    if alice_key == bob_key and alice_salt == bob_salt:
        print("SUCCESS: Keys match!")
        return True
    else:
        print("FAILURE: Keys do not match!")
        return False

if __name__ == "__main__":
    test_key_derivation()