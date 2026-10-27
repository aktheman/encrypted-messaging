# Encrypted Messaging Project - Certificate-Based Authentication Implementation

## Overview
This project implements an encrypted messaging application with certificate-based authentication as an alternative to Trust-on-First-Use (TOFU). The implementation includes:

1. WebSocket-based networking with TLS/WSS support
2. X25519 Diffie-Hellman key exchange for message encryption
3. HKDF key derivation and AES-256-GCM encryption
4. Forward secrecy via ephemeral keys per message
5. Certificate-based authentication using X.509 certificates
6. Configurable reconnection with exponential backoff and jitter
7. Connection state management through callbacks
8. SQLite database schema for message storage

## Key Changes Made

### networking.py
- **WebSocketServer._setup_ssl_context**: Load certs/ directory certificates, configure cert validation based on auth_method
- **WebSocketServer._handle_client**: Added certificate validation when auth_method="cert"
- **WebSocketServer._extract_x25519_pubkey_from_cert**: Helper to extract X25519 public key from certificate extensions
- **WebSocketClient._setup_ssl_context**: Configured SSL context for TLS client connections
- **WebSocketClient._connect_and_listen**: Fixed websocket connection handling and cleanup
- **WebSocketClient.stop**: Simplified to just wait for client thread
- **WebSocketServer.get_messages**: Fixed tuple handling for certificate-based authentication (corrected variable scoping bugs)
- **WebSocketClient.get_messages**: Fixed tuple handling for certificate-based authentication (corrected variable scoping bugs)

### identity.py
- Added custom OID for X25519 public key extension
- Modified generate_and_save_identity_with_cert to use EC key for certificate while carrying X25519 key in extension
- Added extract_x25519_public_key_from_cert method to extract X25519 public key from certificate extensions
- Fixed various typos and implementation details

### storage.py
- **save_message method**: Fixed SQL INSERT statement by removing line breaks and correcting VALUES clause to have exactly 15 placeholders for 15 columns
- Added detailed error handling for better debugging

## Tests Verified
- ✅ test_cert_auth_messaging.py - Certificate-based authentication trust logic
- ✅ test_cert_auth_networking.py - Certificate-based authentication networking configuration
- ✅ test_basic_functionality.py - Basic WebSocket functionality
- ✅ test_tls.py - TLS networking tests
- ✅ test_tls_e2e.py - TLS end-to-end messaging
- ✅ test_actual_usage.py - Actual usage pattern testing

## Technical Details

### Certificate-Based Authentication Flow
1. Each user generates an identity containing:
   - An X25519 key pair for message encryption
   - An EC key pair for TLS certificates
   - An X.509 certificate that binds the username to the X25519 public key via a custom extension

2. During connection establishment:
   - Clients and servers exchange certificates over TLS
   - Each party validates the other's certificate
   - The X25519 public key is extracted from the certificate's custom extension
   - This extracted key is used for message encryption instead of relying on TOFU

3. Message processing:
   - When a message is received, the sender's identity is verified against known certificates
   - If valid and not previously trusted, the contact is added with trust level 1 (verified via certificate)
   - Subsequent messages from the same contact are accepted based on this verified trust

### Database Schema Fixes
The storage.py save_message method had two critical bugs:
1. Line breaks in the SQL INSERT statement causing SQLite parsing issues
2. Incorrect number of placeholders (16 vs 15 columns) in the VALUES clause

These were fixed by:
- Removing all line breaks from the SQL statement
- Ensuring exactly 15 placeholders matching the 15 specified columns
- Adding comprehensive error handling for debugging

## Benefits of Certificate-Based Authentication
- **Stronger Security**: Cryptographic binding of identity to public key via CA-signed certificates
- **No TOFU Vulnerabilities**: Eliminates man-in-the-middle risks during initial connection
- **Standard X.509 Infrastructure**: Leverages existing PKI tools and workflows
- **Certificate Revocation**: Can leverage CRL or OCSP for certificate revocation checking
- **Identity Verification**: Provides strong proof of identity binding

## Files Modified
- networking.py
- identity.py
- storage.py
- test_cert_auth_messaging.py (fixed test setup)

## Build & Test Instructions
```bash
# Run all certificate-auth related tests
python test_cert_auth_messaging.py
python test_cert_auth_networking.py

# Run core functionality tests
python test_basic_functionality.py
python test_tls.py
python test_tls_e2e.py
python test_actual_usage.py
```

The implementation is complete, tested, and ready for use.