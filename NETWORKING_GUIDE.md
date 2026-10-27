# WebSocket Networking Guide

This guide shows how to use the WebSocket networking feature of the encrypted messaging app.

## Overview

The app now supports two transport modes:
1. **File-based queue** (default): Simulates network transport using local files
2. **WebSocket networking**: Real network transport using WebSocket protocol

## Setting Up WebSocket Networking

### Step 1: Start the WebSocket Server

In one terminal window, start the server:

```bash
python main.py server-info --username server --data-dir ./data/server --networking --server --host localhost --port 8765
```

This will start a WebSocket server listening on `localhost:8765`.

### Step 2: Configure Clients

In separate terminal windows, configure each client:

#### For Alice:
```bash
# Initialize Alice's identity
python main.py init --username Alice --data-dir ./data/alice --networking --host localhost --port 8765

# Get Alice's public key (from the output above)
# Example: Alice's public key: a4e933d...
```

#### For Bob:
```bash
# Initialize Bob's identity
python main.py init --username Bob --data-dir ./data/bob --networking --host localhost --port 8765

# Get Bob's public key (from the output above)
# Example: Bob's public key: 51cb42c...
```

### Step 3: Exchange Public Keys

Users need to exchange their public keys securely (this could be done via any secure channel - in person, encrypted email, etc.).

#### Alice adds Bob as contact:
```bash
python main.py add-contact --username Alice --data-dir ./data/alice --networking --host localhost --port 8765 Bob [Bob's public key hex]
```

#### Bob adds Alice as contact:
```bash
python main.py add-contact --username Bob --data-dir ./data/bob --networking --host localhost --port 8765 Alice [Alice's public key hex]
```

### Step 4: Send and Receive Messages

#### Alice sends a message to Bob:
```bash
python main.py send --username Alice --data-dir ./data/alice --networking --host localhost --port 8765 Bob "Hello Bob! This is a secure message."
```

#### Bob receives messages:
```bash
python main.py receive --username Bob --data-dir ./data/bob --networking --host localhost --port 8765
```

Bob should see:
```
Received messages:
  From Alice: Hello Bob! This is a secure message.
```

#### Bob replies to Alice:
```bash
python main.py send --username Bob --data-dir ./data/bob --networking --host localhost --port 8765 Alice "Hi Alice! I received your message securely."
```

#### Alice receives Bob's reply:
```bash
python main.py receive --username Alice --data-dir ./data/alice --networking --host localhost --port 8765
```

Alice should see:
```
Received messages:
  From Bob: Hi Alice! I received your message securely.
```

## How It Works

1. **WebSocket Server**: Accepts connections from clients and broadcasts messages to all connected clients
2. **Clients**: Connect to the server and can send/receive messages in real-time
3. **Message Flow**:
   - Client A sends message → WebSocket Server → Broadcast to all connected clients (including Client B)
   - Client B receives message → Decrypts using shared key derived from identity keys

## Important Notes

1. **Server Requirement**: Exactly one instance must run with the `--server` flag
2. **Network Access**: All clients must be able to reach the server at the specified host:port
3. **Firewall**: Ensure port 8765 (or your chosen port) is open if clients are on different machines
4. **Security**: The WebSocket connection itself is not encrypted (ws:// not wss://). For production use, you would want to:
   - Use TLS encryption (wss://)
   - Implement authentication beyond just public key exchange
   - Add reconnection handling
5. **Message Broadcasting**: The current implementation broadcasts all messages to all connected clients. Messages are still encrypted end-to-end, so only the intended recipient can decrypt them.

## Troubleshooting

### Connection Issues
- Verify the server is running and accessible
- Check firewall settings
- Ensure clients are using the correct host:port
- Try using `127.0.0.1` instead of `localhost` if having issues

### Message Not Received
- Verify both clients are connected to the same server
- Check that the recipient is actually running the receive command
- Ensure public keys were exchanged correctly
- Check that the recipient's username matches exactly

## Stopping the Server

To stop the WebSocket server, press `Ctrl+C` in the terminal where it's running.

## Example Session

Here's what a complete session might look like:

**Terminal 1 (Server):**
```bash
$ python main.py server-info --username server --data-dir ./data/server --networking --server
WebSocket server running on localhost:8765
Waiting for client connections...
```

**Terminal 2 (Alice):**
```bash
$ python main.py init --username Alice --data-dir ./data/alice --networking
No existing identity found for Alice. Generating new identity...
Identity generated and saved. Your public key: a4e933d...
Identity for Alice is ready.
Your public key (share this with contacts): a4e933d...

$ python main.py add-contact --username Alice --data-dir ./data/alice --networking Bob 51cb42c...
Contact 'Bob' added successfully.
```

**Terminal 3 (Bob):**
```bash
$ python main.py init --username Bob --data-dir ./data/bob --networking
No existing identity found for Bob. Generating new identity...
Identity generated and saved. Your public key: 51cb42c...
Identity for Bob is ready.
Your public key (share this with contacts): 51cb42c...

$ python main.py add-contact --username Bob --data-dir ./data/bob --networking Alice a4e933d...
Contact 'Alice' added successfully.
```

**Terminal 2 (Alice) - Sending:**
```bash
$ python main.py send --username Alice --data-dir ./data/alice --networking Bob "Hello Bob! This is encrypted."
Message sent to Bob.
```

**Terminal 3 (Bob) - Receiving:**
```bash
$ python main.py receive --username Bob --data-dir ./data/bob --networking
Received messages:
  From Alice: Hello Bob! This is encrypted.
```

**Terminal 3 (Bob) - Replying:**
```bash
$ python main.py send --username Bob --data-dir ./data/bob --networking Alice "Hi Alice! Got your message securely."
Message sent to Alice.
```

**Terminal 2 (Alice) - Receiving Reply:**
```bash
$ python main.py receive --username Alice --data-dir ./data/alice --networking
Received messages:
  From Bob: Hi Alice! Got your message securely.
```