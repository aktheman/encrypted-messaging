"""
Configuration management for the encrypted messaging app.
Handles loading, saving, and accessing application configuration.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Setup logging
logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_file: str = "config.json"):
        """
        Initialize configuration manager.

        Args:
            config_file: Path to configuration file
        """
        self.config_file = Path(config_file)
        self.config: Dict[str, Any] = {}
        self._load_defaults()
        self.load_config()
        logger.info(f"ConfigManager initialized with config file: {self.config_file}")

    def _load_defaults(self):
        """Load default configuration values."""
        logger.debug("Loading default configuration")
        self.config = {
            "networking": {
                "default_host": "localhost",
                "default_port": 8765,
                "use_networking": False,
                "secure": False,
                "auth_method": "tofu",
                "max_reconnect_attempts": 10,
                "base_reconnect_delay": 1.0,
                "max_reconnect_delay": 60.0
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": None
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

    def load_config(self) -> bool:
        """
        Load configuration from file.

        Returns:
            bool: True if successful, False if file doesn't exist or invalid
        """
        logger.debug(f"Loading configuration from {self.config_file}")
        if not self.config_file.exists():
            logger.warning(f"Configuration file not found: {self.config_file}")
            return False

        try:
            with open(self.config_file, 'r') as f:
                loaded_config = json.load(f)

            # Merge loaded config with defaults (loaded config overrides defaults)
            self._merge_config(self.config, loaded_config)
            logger.info(f"Configuration loaded successfully from {self.config_file}")
            return True
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load configuration from {self.config_file}: {e}")
            # Keep defaults on error
            return False

    def save_config(self) -> bool:
        """
        Save current configuration to file.

        Returns:
            bool: True if successful
        """
        logger.debug(f"Saving configuration to {self.config_file}")
        try:
            # Ensure directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Configuration saved successfully to {self.config_file}")
            return True
        except IOError as e:
            logger.error(f"Failed to save configuration to {self.config_file}: {e}")
            return False

    def _merge_config(self, defaults: Dict[str, Any], override: Dict[str, Any]):
        """
        Recursively merge override dictionary into defaults dictionary.

        Args:
            defaults: Dictionary to be updated (modified in place)
            override: Dictionary with override values
        """
        for key, value in override.items():
            if key in defaults and isinstance(defaults[key], dict) and isinstance(value, dict):
                self._merge_config(defaults[key], value)
            else:
                defaults[key] = value

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Args:
            key_path: Dot-separated path to the configuration value (e.g., "networking.port")
            default: Default value to return if key is not found

        Returns:
            The configuration value or default if not found
        """
        logger.debug(f"Getting configuration value for key: {key_path}")
        keys = key_path.split('.')
        value = self.config

        try:
            for key in keys:
                value = value[key]
            logger.debug(f"Configuration value retrieved: {value}")
            return value
        except (KeyError, TypeError):
            logger.debug(f"Configuration key not found: {key_path}, returning default: {default}")
            return default

    def set(self, key_path: str, value: Any) -> bool:
        """
        Set a configuration value using dot notation.

        Args:
            key_path: Dot-separated path to the configuration value (e.g., "networking.port")
            value: Value to set

        Returns:
            bool: True if successful
        """
        logger.debug(f"Setting configuration value for key: {key_path} to {value}")
        keys = key_path.split('.')
        config = self.config

        try:
            # Navigate to the parent of the target key
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]

            # Set the value
            config[keys[-1]] = value
            logger.debug(f"Configuration value set successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to set configuration value for {key_path}: {e}")
            return False

    def get_networking_config(self) -> Dict[str, Any]:
        """Get networking configuration."""
        return self.get("networking", {})

    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self.get("logging", {})

    def get_storage_config(self) -> Dict[str, Any]:
        """Get storage configuration."""
        return self.get("storage", {})

    def get_identity_config(self) -> Dict[str, Any]:
        """Get identity configuration."""
        return self.get("identity", {})


# Global configuration instance
config = ConfigManager()

# Setup logging based on configuration
def setup_logging():
    """Setup logging based on configuration."""
    logging_config = config.get_logging_config()
    level = getattr(logging, logging_config.get("level", "INFO").upper())
    format_str = logging_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    log_file = logging_config.get("file")

    logging.basicConfig(
        level=level,
        format=format_str,
        filename=log_file,
        filemode='a' if log_file else None
    )
    logger.info("Logging configured based on configuration")

# Initialize logging
setup_logging()