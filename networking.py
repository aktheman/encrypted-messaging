"""
Networking layer for the encrypted messaging app.
Handles WebSocket-based message transport with TLS support and reconnection logic.
"""

import asyncio
import json
import os
import ssl
import threading
import time
import logging
from typing import Set, Callable, Optional, List, TYPE_CHECKING
from queue import Queue
import websockets
import websockets.server
import websockets.client

# Import identity functions for certificate validation
from identity import IdentityManager
from config import config

# Setup logging
logger = logging.getLogger(__name__)


class WebSocketServer:
    """WebSocket server with TLS support and client management."""

    def __init__(self, host: str = None, port: int = None, secure: bool = None, auth_method: str = None,
                 cert_data: Optional[bytes] = None, key_data: Optional[bytes] = None):
        # Use configuration values as defaults
        networking_config = config.get_networking_config()
        self.host = host if host is not None else networking_config.get("default_host", "localhost")
        self.port = port if port is not None else networking_config.get("default_port", 8765)
        self.secure = secure if secure is not None else networking_config.get("secure", False)
        self.auth_method = auth_method if auth_method is not None else networking_config.get("auth_method", "tofu")
        self.cert_data = cert_data
        self.key_data = key_data
        self.running = False
        self.server = None
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.messages: Queue = Queue()
        self._server_thread: Optional[threading.Thread] = None
        self._ssl_context: Optional[ssl.SSLContext] = None
        # Map of username -> websocket for message routing
        self.client_usernames: dict[str, websockets.WebSocketServerProtocol] = {}
        # Offline message storage: username -> list of message JSON strings
        self.offline_messages: dict[str, list[str]] = {}

        logger.debug(f"WebSocketServer initialized: host={self.host}, port={self.port}, secure={self.secure}, auth_method={self.auth_method}")

        if self.secure:
            self._setup_ssl_context()

    def _setup_ssl_context(self):
        """Setup SSL context for TLS support.
        Load certificates for actual TLS encryption (server authentication only).
        Client certificate authentication is handled at application layer.
        """
        logger.debug("Setting up SSL context for TLS support")
        self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        # Load the server's certificate and key for TLS (to authenticate server to clients)
        cert_path = os.path.join(os.path.dirname(__file__), "certs", "cert.pem")
        key_path = os.path.join(os.path.dirname(__file__), "certs", "key.pem")
        self._ssl_context.load_cert_chain(cert_path, key_path)

        # Always use CERT_NONE for client certificates - we handle cert auth at application layer
        # This avoids TLS handshake failures with self-signed client certificates
        self._ssl_context.verify_mode = ssl.CERT_NONE
        logger.debug("SSL context configured for server authentication only (client cert handled at app layer)")

    def _extract_x25519_pubkey_from_cert(self, cert):
        """Extract X25519 public key from certificate extension.

        Args:
            cert: x509 certificate object

        Returns:
            bytes: X25519 public key in raw format, or None if not found
        """
        try:
            from identity import X25519_PUBLIC_KEY_OID
            from cryptography.x509 import UnrecognizedExtension

            # Iterate through extensions to find our custom extension
            # (Newer cryptography versions don't have get_extension_for_oid on Certificate)
            for extension in cert.extensions:
                if extension.oid == X25519_PUBLIC_KEY_OID:
                    # For UnrecognizedExtension, the raw value is in _value attribute
                    if isinstance(extension.value, UnrecognizedExtension):
                        return extension.value._value
                    # For other extension types, try the value directly
                    return extension.value

            # Extension not found
            logger.debug("X25519 public key extension not found in certificate")
            return None

        except Exception as e:
            # Failed to extract extension
            logger.error(f"Failed to extract X25519 public key from certificate: {e}")
            return None

    async def _handle_client(self, websocket, path):
        """Handle a connected client."""
        # Add client to the set
        logger.debug(f"New client connected from {websocket.remote_address}")
        self.clients.add(websocket)
        username = None
        try:
            # Wait for registration message first (for both TOFU and cert auth)
            registration_msg = await websocket.recv()
            try:
                reg_data = json.loads(registration_msg)
                if reg_data.get("type") == "register":
                    username = reg_data.get("username")
                    if not username:
                        logger.warning("Registration message missing username")
                        await websocket.close(code=1008, reason="Registration missing username")
                        return

                    if self.auth_method == "cert" and self.secure:
                        # For cert auth, validate certificate from registration message
                        cert_b64 = reg_data.get("certificate")
                        if not cert_b64:
                            logger.warning("Certificate registration missing certificate")
                            await websocket.close(code=1008, reason="Certificate required")
                            return

                        # Parse and validate certificate
                        try:
                            import base64
                            from cryptography import x509
                            from cryptography.hazmat.backends import default_backend
                            import datetime

                            cert_pem = base64.b64decode(cert_b64)
                            # Try to parse as PEM first (handles both PEM and DER)
                            try:
                                client_cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
                            except ValueError:
                                # If PEM parsing fails, try DER
                                client_cert = x509.load_der_x509_certificate(cert_pem, default_backend())

                            # Validate certificate expiration
                            now = datetime.datetime.utcnow()
                            if now < client_cert.not_valid_before or now > client_cert.not_valid_after:
                                logger.warning(f"Client certificate expired or not yet valid: {client_cert.not_valid_before} to {client_cert.not_valid_after}")
                                await websocket.close(code=1008, reason="Certificate expired or not yet valid")
                                return

                            # Extract username from certificate's Common Name
                            cert_username = None
                            try:
                                for attribute in client_cert.subject:
                                    if attribute.oid == x509.NameOID.COMMON_NAME:
                                        cert_username = attribute.value
                                        break
                            except:
                                pass

                            if not cert_username:
                                logger.warning("Client certificate missing username (Common Name)")
                                await websocket.close(code=1008, reason="Invalid certificate: missing username")
                                return

                            # Verify username matches registration
                            if cert_username != username:
                                logger.warning(f"Certificate username ({cert_username}) doesn't match registration ({username})")
                                await websocket.close(code=1008, reason="Certificate username mismatch")
                                return

                            # Extract X25519 public key from certificate extension
                            x25519_pubkey_bytes = self._extract_x25519_pubkey_from_cert(client_cert)
                            if not x25519_pubkey_bytes:
                                logger.warning(f"Could not extract X25519 public key from client certificate for user: {username}")
                                await websocket.close(code=1008, reason="Invalid certificate: missing X25519 key")
                                return

                            # Store the authenticated username and public key with the websocket for later use
                            websocket.authenticated_username = username
                            websocket.authenticated_x25519_pubkey = x25519_pubkey_bytes
                            # Register in client_usernames for message routing
                            self.client_usernames[username] = websocket
                            logger.info(f"Client authenticated via certificate: {username}")

                            # Deliver any offline messages for this user
                            await self._deliver_offline_messages(username, websocket)

                        except Exception as e:
                            logger.error(f"Error validating client certificate: {e}")
                            await websocket.close(code=1008, reason="Certificate validation failed")
                            return
                    else:
                        # TOFU auth - just register the username
                        self.client_usernames[username] = websocket
                        logger.info(f"Client registered: {username}")

                        # Deliver any offline messages for this user
                        await self._deliver_offline_messages(username, websocket)
                else:
                    logger.warning("First message was not a valid registration")
                    await websocket.close(code=1008, reason="Invalid registration")
                    return
            except json.JSONDecodeError:
                logger.warning("First message was not a valid registration JSON")
                await websocket.close(code=1008, reason="Invalid registration format")
                return

            # Handle messages from this client
            async for message in websocket:
                # Get sender username and public key from authenticated connection if available
                sender_username = getattr(websocket, 'authenticated_username', None)
                sender_x25519_pubkey = getattr(websocket, 'authenticated_x25519_pubkey', None)

                # For TOFU, use the registered username if not from cert
                if not sender_username and username:
                    sender_username = username

                # Put received messages in the queue for processing
                # Include sender username and public key for certificate-based authentication
                if self.auth_method == "cert" and sender_username and sender_x25519_pubkey:
                    self.messages.put((message, sender_username, sender_x25519_pubkey))
                    logger.debug(f"Server queued tuple message from {sender_username}: {message[:50]}...")
                else:
                    self.messages.put(message)
                    logger.debug(f"Server queued message from {sender_username}: {message[:50]}...")

                # Route message to recipient(s)
                await self._route_message(message, sender_username)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected normally: {websocket.remote_address}")
        except Exception as e:
            logger.error(f"Error handling client {websocket.remote_address}: {e}")
        finally:
            # Remove client when disconnected
            self.clients.discard(websocket)
            if username:
                self.client_usernames.pop(username, None)
                logger.debug(f"Client {username} removed from registered users")
            logger.debug(f"Client removed from connections: {websocket.remote_address}")

    def start(self):
        """Start the WebSocket server."""
        if self.running:
            logger.warning("Attempt to start server when already running")
            return

        logger.info(f"Starting WebSocket server on {self.host}:{self.port} (secure={self.secure}, auth={self.auth_method})")
        self.running = True
        self._server_thread = threading.Thread(target=self._run_server, daemon=True)
        self._server_thread.start()

    def _run_server(self):
        """Run the server in a separate thread."""
        async def run_server():
            # Prepare server arguments
            server_args = {
                "host": self.host,
                "port": self.port
            }

            # Add SSL context if TLS is enabled
            if self.secure and self._ssl_context:
                server_args["ssl"] = self._ssl_context

            # Create a wrapper function to ensure correct argument passing
            # The websockets library sometimes calls handlers with only the websocket object
            # instead of (websocket, path), so we extract the path from the request
            async def handler_wrapper(websocket, path=None):
                # If path is not provided (None), try to extract it from the request
                if path is None and hasattr(websocket, 'request') and hasattr(websocket.request, 'path'):
                    path = websocket.request.path
                # If we still don't have a path, default to "/"
                if path is None:
                    path = "/"
                return await self._handle_client(websocket, path)
            self.server = await websockets.serve(
                handler_wrapper,
                **server_args
            )
            logger.info(f"WebSocket server started successfully: {self.server}")
            await self.server.wait_closed()

        # Run the asyncio event loop in this thread
        asyncio.run(run_server())

    def stop(self):
        """Stop the WebSocket server."""
        if not self.running:
            logger.warning("Attempt to stop server when not running")
            return

        logger.info("Stopping WebSocket server")
        self.running = False
        if self.server:
            self.server.close()
            logger.info("WebSocket server stopped")
        if self._server_thread:
            self._server_thread.join(timeout=5)
            logger.debug("Server thread joined")

    async def _route_message(self, message: str, sender_username: Optional[str]):
        """Route a message to the appropriate recipient(s) based on message content."""
        try:
            msg_data = json.loads(message)
            recipient_name = msg_data.get('recipient_name')
            is_group = msg_data.get('is_group', False)

            if not recipient_name:
                logger.warning("Message has no recipient_name, cannot route")
                return

            if is_group:
                # For group messages, broadcast to all clients except sender
                logger.debug(f"Broadcasting group message to all clients except {sender_username}")
                for username, client_ws in self.client_usernames.items():
                    if username != sender_username:
                        try:
                            await client_ws.send(message)
                            logger.debug(f"Sent group message to {username}")
                        except Exception as e:
                            logger.error(f"Failed to send group message to {username}: {e}")
                # Also store for offline members (simplified - in real implementation, track group members)
                # For now, we just deliver to online members
            else:
                # For individual messages, send to specific recipient
                if recipient_name in self.client_usernames:
                    recipient_ws = self.client_usernames[recipient_name]
                    try:
                        await recipient_ws.send(message)
                        logger.debug(f"Routed message to {recipient_name}")
                    except Exception as e:
                        logger.error(f"Failed to send message to {recipient_name}: {e}")
                else:
                    logger.warning(f"Recipient {recipient_name} not connected, storing for offline delivery")
                    # Store message for offline delivery
                    if recipient_name not in self.offline_messages:
                        self.offline_messages[recipient_name] = []
                    self.offline_messages[recipient_name].append(message)
                    logger.debug(f"Stored offline message for {recipient_name} (total: {len(self.offline_messages[recipient_name])})")
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse message for routing: {message[:50]}...")
        except Exception as e:
            logger.error(f"Error routing message: {e}")

    async def _deliver_offline_messages(self, username: str, websocket):
        """Deliver any stored offline messages to a newly connected client."""
        if username in self.offline_messages and self.offline_messages[username]:
            offline_msgs = self.offline_messages[username]
            logger.info(f"Delivering {len(offline_msgs)} offline messages to {username}")
            for msg in offline_msgs:
                try:
                    await websocket.send(msg)
                    logger.debug(f"Delivered offline message to {username}")
                except Exception as e:
                    logger.error(f"Failed to deliver offline message to {username}: {e}")
            # Clear the offline messages for this user
            del self.offline_messages[username]
        else:
            logger.debug(f"No offline messages for {username}")

    def get_messages(self) -> List[str]:
        """Get all received messages and clear the queue."""
        messages = []
        while not self.messages.empty():
            try:
                item = self.messages.get_nowait()
                # Handle tuple format (message, username, public_key) from certificate-based authentication
                if isinstance(item, tuple):
                    if len(item) == 3:
                        message, username, public_key = item
                        messages.append(message)
                        logger.debug(f"Retrieved tuple message from {username}")
                    elif len(item) == 2:
                        message, username = item
                        messages.append(message)
                        logger.debug(f"Retrieved tuple message from {username}")
                    else:
                        # For tuples of other length, treat as raw message (shouldn't happen in normal operation)
                        messages.append(str(item))
                        logger.debug(f"Retrieved non-standard tuple message")
                else:
                    messages.append(item)
                    logger.debug("Retrieved plain message")
            except Exception as e:
                logger.error(f"Error retrieving message from queue: {e}")
                break
        logger.debug(f"Server get_messages returning {len(messages)} messages")
        return messages  # Updated for certificate-based auth tuple format


class WebSocketClient:
    """WebSocket client with TLS support and reconnection logic."""

    def __init__(self, host: str = None, port: int = None, secure: bool = None,
                 auth_method: str = None, cert_data: Optional[bytes] = None, key_data: Optional[bytes] = None,
                 max_reconnect_attempts: int = None, base_reconnect_delay: float = None,
                 max_reconnect_delay: float = None, username: Optional[str] = None):
        # Use configuration values as defaults
        networking_config = config.get_networking_config()
        self.host = host if host is not None else networking_config.get("default_host", "localhost")
        self.port = port if port is not None else networking_config.get("default_port", 8765)
        self.secure = secure if secure is not None else networking_config.get("secure", False)
        self.auth_method = auth_method if auth_method is not None else networking_config.get("auth_method", "tofu")
        self.cert_data = cert_data
        self.key_data = key_data
        self._max_reconnect_attempts = max_reconnect_attempts if max_reconnect_attempts is not None else networking_config.get("max_reconnect_attempts", 10)
        self._base_reconnect_delay = base_reconnect_delay if base_reconnect_delay is not None else networking_config.get("base_reconnect_delay", 1.0)
        self._max_reconnect_delay = max_reconnect_delay if max_reconnect_delay is not None else networking_config.get("max_reconnect_delay", 60.0)
        self.username = username
        self.running = False
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.messages: Queue = Queue()
        self._client_thread: Optional[threading.Thread] = None
        self._reconnect_attempts = 0
        self._ssl_context: Optional[ssl.SSLContext] = None
        self._client_cert_data: Optional[bytes] = None
        self._client_key_data: Optional[bytes] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        # Connection state callbacks
        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        self.on_reconnecting: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

        logger.debug(f"WebSocketClient initialized: host={self.host}, port={self.port}, secure={self.secure}, auth_method={self.auth_method}, username={self.username}")

        if self.secure:
            self._setup_ssl_context()

    def _setup_ssl_context(self):
        """Setup SSL context for TLS support.
        Load certificates for actual TLS encryption (server authentication only).
        Client certificate authentication is handled at application layer.
        """
        logger.debug("Setting up SSL context for TLS client")
        self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        import os

        # Always validate server certificate (using the same cert as CA for this prototype)
        # In production, you would use proper CA certificates
        cert_path = os.path.join(os.path.dirname(__file__), "certs", "cert.pem")
        self._ssl_context.load_verify_locations(cert_path)
        self._ssl_context.verify_mode = ssl.CERT_REQUIRED
        self._ssl_context.check_hostname = False  # We're using self-signed certs

        # Load client certificate/key for application-layer authentication (sent in registration message)
        # We don't use it for TLS client auth since server uses CERT_NONE
        if self.auth_method == "cert" and self.secure and self.cert_data and self.key_data:
            # Store cert/key data for later use in registration message
            self._client_cert_data = self.cert_data
            self._client_key_data = self.key_data
            logger.debug("Stored client certificate for application-layer authentication")
        else:
            self._client_cert_data = None
            self._client_key_data = None
            logger.debug("No client certificate for application-layer authentication")

    async def _connect_and_listen(self):
        """Connect to server and listen for messages with reconnection logic."""
        # Determine URI scheme based on secure flag
        scheme = "wss" if self.secure else "ws"
        uri = f"{scheme}://{self.host}:{self.port}"
        logger.info(f"Attempting to connect to WebSocket server at {uri}")

        while self.running:
            try:
                # Reset reconnect counter on successful connection
                self._reconnect_attempts = 0

                # Prepare connection arguments
                connect_args = {}
                if self.secure and self._ssl_context:
                    connect_args["ssl"] = self._ssl_context

                # Connect to server
                self.websocket = await websockets.connect(uri, **connect_args)
                logger.info(f"WebSocket connection established to {uri}")

                # Send registration for TOFU or cert auth
                if self.auth_method == "tofu" and self.username:
                    registration_msg = json.dumps({"type": "register", "username": self.username})
                    await self.websocket.send(registration_msg)
                    logger.info(f"Sent registration for user: {self.username}")
                elif self.auth_method == "cert" and self.username and self._client_cert_data:
                    # For cert auth, send certificate in registration message
                    import base64
                    cert_b64 = base64.b64encode(self._client_cert_data).decode('ascii')
                    registration_msg = json.dumps({
                        "type": "register",
                        "username": self.username,
                        "certificate": cert_b64
                    })
                    await self.websocket.send(registration_msg)
                    logger.info(f"Sent certificate registration for user: {self.username}")

                # Notify of successful connection
                if self.on_connect:
                    try:
                        self.on_connect()
                        logger.debug("on_connect callback executed")
                    except Exception as e:
                        logger.error(f"Error in on_connect callback: {e}")

                # Listen for messages
                async for message in self.websocket:
                    # Put received messages in the queue
                    self.messages.put(message)
                    logger.debug(f"Client queued message: {message[:50]}...")

            except websockets.exceptions.ConnectionClosedOK:
                # Normal closure - server closed connection cleanly
                if self.running:
                    logger.info("WebSocket connection closed normally by server")
                    if self.on_disconnect:
                        try:
                            self.on_disconnect()
                            logger.debug("on_disconnect callback executed")
                        except Exception as e:
                            logger.error(f"Error in on_disconnect callback: {e}")
                    await self._handle_reconnection()
            except websockets.exceptions.ConnectionClosedError as e:
                # Abnormal closure with error code
                if self.running:
                    logger.warning(f"WebSocket connection closed with error: {e}")
                    if self.on_disconnect:
                        try:
                            self.on_disconnect()
                            logger.debug("on_disconnect callback executed")
                        except Exception as e:
                            logger.error(f"Error in on_disconnect callback: {e}")
                    await self._handle_reconnection()
            except websockets.exceptions.ConnectionClosed as e:
                # Other connection closed variants
                if self.running:
                    logger.warning(f"WebSocket connection closed: {e}")
                    if self.on_disconnect:
                        try:
                            self.on_disconnect()
                            logger.debug("on_disconnect callback executed")
                        except Exception as e:
                            logger.error(f"Error in on_disconnect callback: {e}")
                    await self._handle_reconnection()
            except TimeoutError as e:
                # Connection timeout
                if self.running:
                    logger.warning(f"WebSocket connection timeout: {e}")
                    if self.on_error:
                        try:
                            self.on_error(e)
                            logger.debug("on_error callback executed")
                        except Exception as e2:
                            logger.error(f"Error in on_error callback: {e2}")
                    await self._handle_reconnection()
            except OSError as e:
                # Network-related errors (connection refused, host unreachable, etc.)
                if self.running:
                    logger.warning(f"WebSocket network error: {e}")
                    if self.on_error:
                        try:
                            self.on_error(e)
                            logger.debug("on_error callback executed")
                        except Exception as e2:
                            logger.error(f"Error in on_error callback: {e2}")
                    await self._handle_reconnection()
            except Exception as e:
                # Catch-all for unexpected errors
                if self.running:
                    logger.error(f"WebSocket client unexpected error: {e}")
                    if self.on_error:
                        try:
                            self.on_error(e)
                            logger.debug("on_error callback executed")
                        except Exception as e2:
                            logger.error(f"Error in on_error callback: {e2}")
                    await self._handle_reconnection()
            finally:
                # Close websocket connection if it exists
                if self.websocket:
                    try:
                        await self.websocket.close()
                        logger.debug("WebSocket connection closed")
                    except:
                        pass  # Ignore errors during close
                # Clean up websocket reference
                self.websocket = None
                # Notify of disconnection (if we were running)
                if self.running:
                    if self.on_disconnect:
                        try:
                            self.on_disconnect()
                            logger.debug("on_disconnect callback executed")
                        except Exception as e:
                            logger.error(f"Error in on_disconnect callback: {e}")

    async def _handle_reconnection(self):
        """Handle reconnection with exponential backoff and jitter."""
        if not self.running or self._reconnect_attempts >= self._max_reconnect_attempts:
            self.running = False
            logger.info("Stopping reconnection attempts - max attempts reached or not running")
            return

        # Calculate delay with exponential backoff and jitter
        delay = min(
            self._base_reconnect_delay * (2 ** self._reconnect_attempts),
            self._max_reconnect_delay
        )
        # Add jitter to prevent thundering herd
        import random
        delay *= (0.5 + random.random() * 0.5)

        self._reconnect_attempts += 1
        logger.info(f"WebSocket client reconnecting in {delay:.1f}s (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})")

        # Notify of reconnection attempt
        if self.on_reconnecting:
            try:
                self.on_reconnecting()
                logger.debug("on_reconnecting callback executed")
            except Exception as e:
                logger.error(f"Error in on_reconnecting callback: {e}")

        await asyncio.sleep(delay)

    def start(self):
        """Start the WebSocket client with reconnection logic."""
        if self.running:
            logger.warning("Attempt to start client when already running")
            return

        logger.info(f"Starting WebSocket client for {self.host}:{self.port} (secure={self.secure}, auth={self.auth_method})")
        self.running = True
        self._client_thread = threading.Thread(target=self._run_client, daemon=True)
        self._client_thread.start()

    def _run_client(self):
        """Run the client in a separate thread."""
        logger.debug("Starting WebSocket client thread")
        # Store the event loop for cross-thread communication
        self._event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._event_loop)
        try:
            self._event_loop.run_until_complete(self._connect_and_listen())
        finally:
            self._event_loop.close()
            self._event_loop = None

    def stop(self):
        """Stop the WebSocket client."""
        if not self.running:
            logger.warning("Attempt to stop client when not running")
            return

        logger.info("Stopping WebSocket client")
        self.running = False
        if self._client_thread:
            self._client_thread.join(timeout=5)
            logger.debug("Client thread joined")

    def get_messages(self) -> List[str]:
        """Get all received messages and clear the queue."""
        messages = []
        while not self.messages.empty():
            try:
                item = self.messages.get_nowait()
                # Handle tuple format (message, username, public_key) from certificate-based authentication
                if isinstance(item, tuple):
                    if len(item) == 3:
                        message, username, public_key = item
                        messages.append(message)
                        logger.debug(f"Retrieved tuple message from {username}")
                    elif len(item) == 2:
                        message, username = item
                        messages.append(message)
                        logger.debug(f"Retrieved tuple message from {username}")
                    else:
                        # For tuples of other length, treat as raw message (shouldn't happen in normal operation)
                        messages.append(str(item))
                        logger.debug(f"Retrieved non-standard tuple message")
                else:
                    messages.append(item)
                    logger.debug("Retrieved plain message")
            except Exception as e:
                logger.error(f"Error retrieving message from queue: {e}")
                break
        logger.debug(f"Client get_messages returning {len(messages)} messages")
        return messages  # Updated for certificate-based auth tuple format


class WebSocketMessageQueue:
    """WebSocket-based message queue for network transport."""

    def __init__(self, host: str = None, port: int = None, is_server: bool = False, secure: bool = None,
                 auth_method: str = None, cert_data: Optional[bytes] = None, key_data: Optional[bytes] = None,
                 max_reconnect_attempts: int = None, base_reconnect_delay: float = None,
                 max_reconnect_delay: float = None, username: Optional[str] = None):
        # Use configuration values as defaults
        networking_config = config.get_networking_config()
        self.host = host if host is not None else networking_config.get("default_host", "localhost")
        self.port = port if port is not None else networking_config.get("default_port", 8765)
        self.is_server = is_server
        self.secure = secure if secure is not None else networking_config.get("secure", False)
        self.auth_method = auth_method if auth_method is not None else networking_config.get("auth_method", "tofu")
        self.cert_data = cert_data
        self.key_data = key_data
        self._max_reconnect_attempts = max_reconnect_attempts if max_reconnect_attempts is not None else networking_config.get("max_reconnect_attempts", 10)
        self._base_reconnect_delay = base_reconnect_delay if base_reconnect_delay is not None else networking_config.get("base_reconnect_delay", 1.0)
        self._max_reconnect_delay = max_reconnect_delay if max_reconnect_delay is not None else networking_config.get("max_reconnect_delay", 60.0)
        self.username = username
        self.running = False

        logger.debug(f"WebSocketMessageQueue initialized: host={self.host}, port={self.port}, is_server={self.is_server}, secure={self.secure}, auth_method={self.auth_method}, username={self.username}")

        if is_server:
            # For server, we don't need client cert data (unless doing mutual TLS where server also presents cert)
            # But for now, we'll just pass None for client cert data to server
            logger.debug("Initializing WebSocket server message queue")
            self.server = WebSocketServer(host, port, secure, auth_method, None, None)
            self.message_queue = Queue()
        else:
            logger.debug("Initializing WebSocket client message queue")
            self.client = WebSocketClient(host, port, secure, auth_method, cert_data, key_data,
                                          max_reconnect_attempts=self._max_reconnect_attempts,
                                          base_reconnect_delay=self._base_reconnect_delay,
                                          max_reconnect_delay=self._max_reconnect_delay,
                                          username=self.username)
            self.message_queue = Queue()

        self._message_callback: Optional[Callable] = None

    def set_message_callback(self, callback: Callable):
        """Set a callback to be called when a message is received."""
        logger.debug("Setting message callback")
        self._message_callback = callback

    def start(self):
        """Start the networking component."""
        if self.running:
            logger.warning("Attempt to start message queue when already running")
            return

        logger.info(f"Starting WebSocket message queue ({'server' if self.is_server else 'client'})")
        self.running = True
        if self.is_server:
            self.server.start()
            # Start processing messages from server queue
            self._start_message_processor()
        else:
            self.client.start()

    def _start_message_processor(self):
        """Start processing messages from the server queue."""
        def process_messages():
            while self.running:
                try:
                    # Check for new messages
                    messages = self.server.get_messages()
                    logger.debug(f"Message processor got {len(messages)} messages from server queue")
                    for msg_json in messages:
                        if self._message_callback:
                            self._message_callback(msg_json)
                    time.sleep(0.1)  # Small delay to prevent busy waiting
                except Exception as e:
                    logger.error(f"Error in message processor: {e}")
                    time.sleep(0.1)

        self.processor_thread = threading.Thread(target=process_messages, daemon=True)
        self.processor_thread.start()
        logger.debug("Message processor thread started")

    def stop(self):
        """Stop the networking component."""
        if not self.running:
            logger.warning("Attempt to stop message queue when not running")
            return

        logger.info("Stopping WebSocket message queue")
        self.running = False
        if self.is_server:
            self.server.stop()
            logger.debug("WebSocket server stopped")
        else:
            self.client.stop()
            logger.debug("WebSocket client stopped")

    def send_message(self, message: "Message") -> bool:
        """
        Send a message via WebSocket.

        Args:
            message: Message to send

        Returns:
            bool: True if successful
        """
        try:
            if self.is_server:
                # Server broadcasts to all clients
                logger.debug(f"Broadcasting message from server: {message.to_json()[:50]}...")
                asyncio.run(self._broadcast_message(message))
            else:
                # Client sends to server using thread-safe coroutine execution
                logger.debug(f"Sending message to server: {message.to_json()[:50]}...")
                if self.client._event_loop and self.client._event_loop.is_running():
                    # Schedule the send on the client's event loop
                    future = asyncio.run_coroutine_threadsafe(
                        self._send_message_to_server(message),
                        self.client._event_loop
                    )
                    # Wait for the send to complete with a timeout
                    future.result(timeout=5.0)
                    logger.debug("Message sent to server successfully")
                else:
                    logger.warning("Attempted to send message but client event loop not running")
                    return False
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def _broadcast_message(self, message: "Message"):
        """Broadcast message to all connected clients (server-side)."""
        if self.server.clients:
            message_json = message.to_json()
            logger.debug(f"Broadcasting to {len(self.server.clients)} clients")
            await asyncio.wait([
                client.send(message_json) for client in self.server.clients
            ])

    async def _send_message_to_server(self, message: "Message"):
        """Send message to server (client-side). Must be called on the client's event loop."""
        if self.client.websocket and self.client.running:
            await self.client.websocket.send(message.to_json())
            logger.debug("Message sent to server successfully")
        else:
            logger.warning("Attempted to send message but client not connected")
            raise RuntimeError("Client not connected")

    def receive_messages(self) -> list["Message"]:
        """
        Get messages received from the network.

        Returns:
            list: List of received Message objects
        """
        # Import Message here to avoid circular import
        from messaging import Message

        messages = []
        try:
            if self.is_server:
                # For server, we get messages from clients via callback mechanism
                # This is simplified - in a real implementation, we'd have a proper queue
                logger.debug("Server receive_messages called (simplified implementation)")
                pass
            else:
                # For client, get messages from the client's queue
                msg_jsons = self.client.get_messages()
                for msg_json in msg_jsons:
                    try:
                        message = Message.from_json(msg_json)
                        messages.append(message)
                        logger.debug(f"Received and parsed message: {msg_json[:50]}...")
                    except Exception as e:
                        # Skip malformed messages
                        logger.warning(f"Skipped malformed message: {msg_json[:100]}... Error: {e}")
                        pass
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
        return messages

    def simulate_network_delay(self, message: "Message", delay_seconds: float = 0.1):
        """
        Simulate network delay (maintained for compatibility).

        In the WebSocket version, this is mostly a no-op since messages are sent immediately,
        but we keep the method for interface compatibility.
        """
        logger.debug(f"Simulating network delay of {delay_seconds} seconds")
        time.sleep(delay_seconds)
        # In a real implementation, the delay happens naturally in network transmission


# Global instances for easy access (for backward compatibility)
websocket_server = WebSocketServer()
websocket_client = WebSocketClient()

# Log that the module has been initialized
logger.info("Networking module initialized")