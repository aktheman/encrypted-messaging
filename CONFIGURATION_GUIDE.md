# Configuration Guide

## Overview
The encrypted messaging application now includes a configuration management system that allows you to customize various aspects of the application without modifying the source code.

## Configuration File
The application uses a JSON configuration file named `config.json` located in the application root directory.

### Default Configuration
If no configuration file is found, the application uses these default values:

```json
{
  "networking": {
    "default_host": "localhost",
    "default_port": 8765,
    "use_networking": false,
    "secure": false,
    "auth_method": "tofu",
    "max_reconnect_attempts": 10,
    "base_reconnect_delay": 1.0,
    "max_reconnect_delay": 60.0
  },
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": null
  },
  "storage": {
    "data_dir": "./data",
    "queue_dir": "./queue",
    "db_path": "./data/messaging.db"
  },
  "identity": {
    "certificate_validity_days": 365
  }
}
```

## Configuration Sections

### Networking Configuration
- `default_host`: Default host for WebSocket connections (default: "localhost")
- `default_port`: Default port for WebSocket connections (default: 8765)
- `use_networking`: Whether to use WebSocket networking instead of file-based queue (default: false)
- `secure`: Whether to use secure WebSocket connections (wss://) with TLS encryption (default: false)
- `auth_method`: Authentication method to use ("tofu" or "cert") (default: "tofu")
- `max_reconnect_attempts`: Maximum number of reconnection attempts (default: 10)
- `base_reconnect_delay`: Base delay in seconds for reconnection attempts (default: 1.0)
- `max_reconnect_delay`: Maximum delay in seconds for reconnection attempts (default: 60.0)

### Logging Configuration
- `level`: Logging level ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL") (default: "INFO")
- `format`: Log message format (default: "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
- `file`: Optional log file path. If null, logs go to console (default: null)

### Storage Configuration
- `data_dir`: Directory for storing identity and contact data (default: "./data")
- `queue_dir`: Directory for file-based message queue (default: "./queue")
- `db_path`: Path to SQLite database for message storage (default: "./data/messaging.db")

### Identity Configuration
- `certificate_validity_days`: Number of days that generated certificates are valid for (default: 365)

## Using the Configuration Manager

### In Your Code
You can access configuration values in your code using the global `config` object:

```python
from config import config

# Get a specific configuration value
host = config.get("networking.default_host", "localhost")

# Get entire configuration sections
networking_config = config.get_networking_config()
storage_config = config.get_storage_config()

# Set a configuration value (and optionally save to file)
config.set("networking.use_networking", True)
config.save_config()  # Save changes to config.json
```

### Command Line Usage
You can also create a simple script to view or modify configuration:

```bash
# View current configuration
python -c "from config import config; import json; print(json.dumps(config.config, indent=2))"

# Set a configuration value
python -c "from config import config; config.set('networking.use_networking', True); config.save_config()"
```

## Enhancements Summary

In addition to the configuration system, the following enhancements have been made:

### 1. Enhanced Logging
- All `print()` statements have been replaced with proper logging using Python's `logging` module
- Log levels are now configurable (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Application components now use appropriate log levels for different types of messages

### 2. Configuration Management
- Centralized configuration system with JSON file support
- Default values provided for all settings
- Runtime access to configuration values
- Ability to modify and save configuration

### 3. Improved Error Handling
- Better error messages with contextual information
- Proper exception handling and propagation
- More informative logging of error conditions

### 4. Code Organization
- Better separation of concerns
- More modular and maintainable code
- Consistent coding patterns across modules

## Example Usage

### Basic File-Based Usage (Default)
```python
from messaging import SecureMessenger

# Create a messenger instance (uses all default values from config)
messenger = SecureMessenger("alice")

# Send a message
messenger.send_message("bob", "Hello, Bob!")

# Receive messages
messages = messenger.receive_and_process_messages()
for sender, text in messages:
    print(f"{sender}: {text}")
```

### Networking Usage
```python
from messaging import SecureMessenger

# Create a messenger instance with networking enabled
messenger = SecureMessenger(
    username="alice",
    use_networking=True,
    is_server=False  # Set to True for server instance
)

# The messenger will now use WebSocket connections instead of file-based queue
```

### Custom Configuration
```python
# First, modify config.json or create your own
# Then the application will automatically use your settings

# Or modify configuration at runtime
from config import config
config.set("networking.use_networking", True)
config.set("networking.secure", True)
config.set("logging.level", "DEBUG")
config.save_config()

# Now create your messenger - it will use the updated settings
from messaging import SecureMessenger
messenger = SecureMessenger("alice")
```

## Best Practices

1. **Environment-Specific Configuration**: Consider having different configuration files for development, testing, and production environments.

2. **Secure Configuration**: Never commit sensitive configuration values (like private keys) to version control. Use environment variables or secure vaults for production secrets.

3. **Logging in Production**: In production environments, consider logging to a file rather than console, and use appropriate log levels (typically WARNING or ERROR).

4. **Backup Configuration**: Keep a backup of your working configuration file.

5. **Test Changes**: Always test configuration changes in a development environment before deploying to production.