# Encrypted Messaging App

A CLI-based prototype for end-to-end encrypted messaging with forward secrecy.

## Features

- End-to-end encryption using X25519 Diffie-Hellman key exchange
- Forward secrecy through ephemeral keys (one per message)
- Key derivation using HKDF
- Message encryption using AES-256-GCM
- Identity key pairs (long-term) for authentication
- Contact management (store public keys of contacts)
- **Group chat capabilities** (pairwise encryption for group members)
- Local storage of conversations and messages (SQLite)
- **Two transport options**:
  - File-based queue prototype (simulates network transport)
  - WebSocket-based networking (real network transport)
- Command-line interface for all operations
- Trust on First Use (TOFU) support with trust levels (unknown/trusted/blocked)

## Security Properties

- **End-to-End Encryption**: Messages are encrypted on the sender's device and can only be decrypted by the recipient's device.
- **Forward Secrecy**: Each message uses a new ephemeral key pair, so compromise of long-term keys does not compromise past messages.
- **Authentication**: Recipients verify that messages come from the claimed sender (via contact public keys).
- **Integrity**: AES-GCM provides authentication and confidentiality, preventing tampering.

## Limitations

- This is a prototype for educational purposes.
- Local message storage is currently encrypted, but sent messages cannot be decrypted for history viewing due to the ephemeral nature of the encryption keys (a design trade-off for forward secrecy). Received messages can be decrypted and stored in history.
- WebSocket implementation is basic and lacks production-level features like reconnection handling, TLS encryption, etc.
- No protection against traffic analysis or metadata leakage.
- No authentication mechanism beyond pre-shared public keys and TOFU.

## Usage

### Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Generate your identity:
   ```bash
   python main.py init --username your_name
   ```

3. Add a contact (exchange public keys manually):
   ```bash
   python main.py add-contact --username your_name --data-dir ./data/your_name --queue-dir ./queue contact_name contact_public_key_hex
   ```

### Group Management

1. Create a group:
   ```bash
   python main.py create-group --username your_name --data-dir ./data/your_name --queue-dir ./queue group_name member1 member2 member3
   ```

2. Add a member to a group:
   ```bash
   python main.py add-group-member --username your_name --data-dir ./data/your_name --queue-dir ./queue group_name member_name
   ```

3. Remove a member from a group:
   ```bash
   python main.py remove-group-member --username your_name --data-dir ./data/your_name --queue-dir ./queue group_name member_name
   ```

4. List group members:
   ```bash
   python main.py list-group-members --username your_name --data-dir ./data/your_name --queue-dir ./queue group_name
   ```

5. List all groups:
   ```bash
   python main.py list-groups --username your_name --data-dir ./data/your_name --queue-dir ./queue
   ```

6. Delete a group:
   ```bash
   python main.py delete-group --username your_name --data-dir ./data/your_name --queue-dir ./queue group_name
   ```

### Sending a Message (File-based Queue - Default)

```bash
python main.py send --username your_name --data-dir ./data/your_name --queue-dir ./queue recipient_name "Your message here"
```

The recipient can be either an individual contact or a group name.

### Receiving Messages (File-based Queue)

```bash
python main.py receive --username your_name --data-dir ./data/your_name --queue-dir ./queue
```

### Simulating Network Transport (File-based Queue Only)

After sending a message, simulate network delivery:

```bash
python main.py simulate --username your_name --data-dir ./data/your_name --queue-dir ./queue --delay 0.1
```

### Using WebSocket Networking

1. **Start a WebSocket server** (run this in one terminal):
   ```bash
   python main.py init --username server --data-dir ./data/server --networking --server
   ```

2. **Run clients** (in separate terminals):
   ```bash
   # Client 1 (Alice)
   python main.py init --username Alice --data-dir ./data/Alice --networking --host localhost --port 8765
   python main.py add-contact --username Alice --data-dir ./data/Alice --networking --host localhost --port 8765 Bob <Bob's public key>
   
   # Client 2 (Bob)  
   python main.py init --username Bob --data-dir ./data/Bob --networking --host localhost --port 8765
   python main.py add-contact --username Bob --data-dir ./data/Bob --networking --host localhost --port 8765 Alice <Alice's public key>
   ```

3. **Send messages** (networking is automatic):
   ```bash
   # From Alice's terminal
   python main.py send --username Alice --data-dir ./data/Alice --networking --host localhost --port 8765 Bob "Hello Bob!"
   
   # From Bob's terminal (to receive)
   python main.py receive --username Bob --data-dir ./data/Bob --networking --host localhost --port 8765
   ```

### Viewing Conversation History

```bash
python main.py history --username your_name --data-dir ./data/your_name --queue-dir ./queue contact_name_or_group
```

### Listing Conversations

```bash
python main.py list-convos --username your_name --data-dir ./data/your_name --queue-dir ./queue
```

### Listing Contacts

```bash
python main.py list-contacts --username your_name --data-dir ./data/your_name --queue-dir ./queue
```

### Managing Contact Trust Levels (TOFU)

List pending contact requests:
```bash
python main.py pending-contacts --username your_name --data-dir ./data/your_name --queue-dir ./queue
```

Trust a contact:
```bash
python main.py trust-contact --username your_name --data-dir ./data/your_name --queue-dir ./queue contact_name
```

Block a contact:
```bash
python main.py block-contact --username your_name --data-dir ./data/your_name --queue-dir ./queue contact_name
```

## Files

- `main.py`: CLI entry point
- `messaging.py`: Message formatting, encryption/decryption, and queue abstraction (file/WebSocket)
- `storage.py`: Local persistence using SQLite
- `identity.py`: Key pair generation and management
- `crypto.py`: Cryptographic primitives (X25519, HKDF, AES-GCM)
- `networking.py`: WebSocket networking layer
- `demo.py`: Demonstration script showing individual and group chat
- `requirements.txt`: Dependencies (cryptography library, websockets)

## Demo

Run the demo to see simulated conversations (uses file-based queue):

```bash
python demo.py
```

The demo will prompt you to choose between individual chat (Alice & Bob) or group chat (Alice, Bob, & Charlie).

## Networking Example

For a working networking example, follow the WebSocket networking instructions above.

## Design

### Cryptographic Layer

- **Identity Key Pair**: Long-term X25519 key pair used for authentication.
- **Ephemereal Key Pair**: Temporary X25519 key pair generated per message for forward secrecy.
- **Key Exchange**: 
  1. Sender combines their ephemeral private key with recipient's identity public key.
  2. Sender combines their identity private key with recipient's identity public key.
  3. The two shared secrets are concatenated and fed into HKDF to derive encryption key and salt.
- **Encryption**: AES-256-GCM with a random nonce.

### Message Format

Each message is a JSON object containing:
- `sender_name`: Sender's username
- `recipient_name`: Recipient's username (individual or group)
- `ciphertext`: Encrypted message (hex)
- `nonce`: Nonce used for encryption (hex)
- `ephemeral_public_key`: Sender's ephemeral public key (hex)
- `salt`: Salt used for key derivation (hex)
- `timestamp`: Unix timestamp of message creation
- `is_group`: Boolean indicating if this is a group message

### Local Storage

- **Conversations Table**: Stores contact/group name, public key (NULL for groups), and group flag.
- **Messages Table**: Stores message details (direction, ciphertext, nonce, ephemeral public key, salt, timestamp, is_group flag) linked to a conversation.

### Networking (WebSocket)

- Uses the `websockets` library for real-time, full-duplex communication
- One server instance can handle multiple clients
- Messages are broadcast from server to all connected clients
- Automatic reconnection handling would be needed for production use

## Future Improvements

- Add certificate-based authentication as an alternative to TOFU.
- Implement message deletion or ephemeral messages.
- Add GUI version (web or desktop).
- Implement perfect forward secrecy with regular key rotation of identity keys.
- Store sent messages in a way that allows decryption for history (e.g., encrypt with a storage key derived from identity).
- Enhance WebSocket implementation with TLS, reconnection logic, and better error handling.
- Add message reactions or threading capabilities.

## License

This project is for educational and demonstrative purposes only.