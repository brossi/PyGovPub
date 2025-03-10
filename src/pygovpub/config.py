"""
Configuration module for PyGovPub SDK.

This module provides comprehensive configuration management, including:
- Environment profiles (development, test, production)
- Feature toggles for conditional feature enabling
- API credentials management with secure storage
- Configuration validation
- Multi-format configuration file support (JSON, YAML, ENV)
"""

import base64
import json
import os
import re
import logging
from datetime import datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import yaml

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pydantic import BaseModel, Field, validator


# Set up logging
logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Exception raised for configuration validation errors."""
    pass


class ConfigFormat(str, Enum):
    """Supported configuration file formats."""
    
    JSON = "json"
    YAML = "yaml"
    ENV = "env"
    
    def get_extension(self) -> str:
        """Get file extension for this format."""
        if self == ConfigFormat.JSON:
            return ".json"
        elif self == ConfigFormat.YAML:
            return ".yaml"
        elif self == ConfigFormat.ENV:
            return ".env"
        else:
            raise ValueError(f"Unknown format: {self}")
    
    @classmethod
    def from_extension(cls, extension: str) -> "ConfigFormat":
        """Get format from file extension."""
        if extension in (".json",):
            return cls.JSON
        elif extension in (".yaml", ".yml"):
            return cls.YAML
        elif extension in (".env",):
            return cls.ENV
        else:
            raise ValueError(f"Unsupported file extension: {extension}")


class Environment(str, Enum):
    """Environment options for the SDK."""
    
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"
    
    @classmethod
    def from_string(cls, value: str) -> "Environment":
        """Create Environment enum from string."""
        try:
            return cls(value.lower())
        except ValueError:
            # Default to DEVELOPMENT if unknown
            logger.warning(f"Unknown environment: {value}, defaulting to DEVELOPMENT")
            return cls.DEVELOPMENT


class FeatureFlag(str, Enum):
    """Feature flags for conditional enabling of features."""
    
    CACHE_ENABLED = "cache_enabled"
    ADVANCED_ROUTING = "advanced_routing"
    DEBUG_MODE = "debug_mode"
    
    @property
    def default_value(self) -> bool:
        """Get default value for this feature flag."""
        defaults = {
            self.CACHE_ENABLED: True,
            self.ADVANCED_ROUTING: False,
            self.DEBUG_MODE: False,
        }
        return defaults.get(self, False)


class ApiConfig(BaseModel):
    """Configuration for a specific API."""
    
    base_url: str
    api_key: Optional[str] = None
    rate_limit: int
    rate_limit_period: int = 3600  # in seconds (default 1 hour)


class MockConfig(BaseModel):
    """Configuration for the mock server."""
    
    enabled: bool = False
    latency_ms: int = 0
    simulate_rate_limits: bool = False
    record_mode: bool = False
    fixtures_path: str = "fixtures"


class ProfileConfig(BaseModel):
    """Configuration for an environment profile."""
    
    name: Environment
    api_base_urls: Dict[str, str] = Field(default_factory=dict)
    features: Dict[str, bool] = Field(default_factory=dict)
    options: Dict[str, Any] = Field(default_factory=dict)
    
    @validator("features", pre=True, always=True)
    def set_default_features(cls, v):
        """Set default values for features."""
        defaults = {flag.value: flag.default_value for flag in FeatureFlag}
        if isinstance(v, dict):
            return {**defaults, **v}
        return defaults


def _parse_env_value(value: str) -> Any:
    """Parse environment variable value to appropriate type."""
    # Convert to lowercase for boolean values
    lower_value = value.lower()
    
    # Handle boolean values
    if lower_value in ("true", "yes", "1", "on"):
        return True
    if lower_value in ("false", "no", "0", "off"):
        return False
    
    # Try to convert to int
    try:
        return int(value)
    except ValueError:
        pass
    
    # Try to convert to float
    try:
        return float(value)
    except ValueError:
        pass
    
    # Return as string
    return value


def load_config_from_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Load configuration from file.
    
    Supports JSON, YAML, and ENV formats based on file extension.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    
    # Determine format based on extension
    format_type = ConfigFormat.from_extension(path.suffix)
    
    # Load based on format
    with open(path, "r", encoding="utf-8") as f:
        if format_type == ConfigFormat.JSON:
            return json.load(f)
        elif format_type == ConfigFormat.YAML:
            return yaml.safe_load(f)
        elif format_type == ConfigFormat.ENV:
            # Parse ENV format
            config = {}
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue
                
                # Parse key=value format
                key, value = line.split("=", 1)
                key = key.strip().lower()
                value = value.strip()
                
                # Parse value to appropriate type
                config[key] = _parse_env_value(value)
            
            return config
    
    raise ValueError(f"Unsupported configuration format: {format_type}")


def save_config_to_file(config: Dict[str, Any], file_path: Union[str, Path]) -> None:
    """Save configuration to file.
    
    Supports JSON, YAML, and ENV formats based on file extension.
    """
    path = Path(file_path)
    
    # Create directory if it doesn't exist
    os.makedirs(path.parent, exist_ok=True)
    
    # Determine format based on extension
    format_type = ConfigFormat.from_extension(path.suffix)
    
    # Save based on format
    with open(path, "w", encoding="utf-8") as f:
        if format_type == ConfigFormat.JSON:
            json.dump(config, f, indent=2, sort_keys=True)
        elif format_type == ConfigFormat.YAML:
            yaml.dump(config, f, default_flow_style=False, sort_keys=True)
        elif format_type == ConfigFormat.ENV:
            # Write ENV format
            for key, value in sorted(config.items()):
                # Convert key to uppercase
                env_key = key.upper()
                
                # Convert value to string based on type
                if isinstance(value, bool):
                    env_value = "true" if value else "false"
                else:
                    env_value = str(value)
                
                f.write(f"{env_key}={env_value}\n")


class SecretHandler:
    """Handler for encrypting and decrypting sensitive configuration."""
    
    def __init__(self, key: Optional[str] = None):
        """Initialize with optional key."""
        if key:
            # Use provided key
            self.key = self._process_key(key)
        else:
            # Generate key from machine-specific information
            machine_salt = self._get_machine_salt()
            self.key = self._derive_key(machine_salt)
        
        self.cipher = Fernet(self.key)
    
    def _process_key(self, key: str) -> bytes:
        """Process key to ensure it's valid for Fernet."""
        # If key is already valid Fernet key, use as is
        try:
            if len(base64.urlsafe_b64decode(key)) == 32:
                return key.encode() if isinstance(key, str) else key
        except Exception:
            pass
        
        # Otherwise, derive key from provided string
        salt = b"PyGovPub-Salt"  # Fixed salt for key derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key_bytes = key.encode() if isinstance(key, str) else key
        derived_key = base64.urlsafe_b64encode(kdf.derive(key_bytes))
        return derived_key
    
    def _get_machine_salt(self) -> bytes:
        """Get machine-specific information for salt."""
        # Use username, hostname, and path info as salt
        username = os.getenv("USER", os.getenv("USERNAME", "user"))
        hostname = os.getenv("HOSTNAME", "localhost")
        base_path = str(Path.home())
        
        return f"{username}@{hostname}:{base_path}".encode()
    
    def _derive_key(self, salt: bytes) -> bytes:
        """Derive encryption key from salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(b"PyGovPub-Secret-Key")
        return base64.urlsafe_b64encode(key)
    
    def encrypt(self, data: Any) -> str:
        """Encrypt data."""
        # Serialize data to JSON
        serialized = json.dumps(data)
        
        # Encrypt
        encrypted = self.cipher.encrypt(serialized.encode())
        
        # Return as string
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted: str) -> Any:
        """Decrypt data."""
        try:
            # Decode from string
            data = base64.urlsafe_b64decode(encrypted)
            
            # Decrypt
            decrypted = self.cipher.decrypt(data)
            
            # Deserialize from JSON
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt data: {e}")
            return None
    
    def secure_config(self, config: Dict[str, Any], sensitive_sections: List[str]) -> Dict[str, Any]:
        """Encrypt sensitive sections of configuration."""
        # Create a copy to avoid modifying the original
        secure_config = config.copy()
        
        # Encrypt sensitive sections
        for section in sensitive_sections:
            if section in secure_config:
                secure_config[section] = self.encrypt(secure_config[section])
        
        return secure_config
    
    def unsecure_config(self, config: Dict[str, Any], encrypted_sections: List[str]) -> Dict[str, Any]:
        """Decrypt encrypted sections of configuration."""
        # Create a copy to avoid modifying the original
        unsecure_config = config.copy()
        
        # Decrypt sensitive sections
        for section in encrypted_sections:
            if section in unsecure_config and isinstance(unsecure_config[section], str):
                decrypted = self.decrypt(unsecure_config[section])
                if decrypted is not None:
                    unsecure_config[section] = decrypted
        
        return unsecure_config


class ConfigManager:
    """Configuration manager with environment and feature management."""
    
    # Sensitive sections that should be encrypted
    SENSITIVE_SECTIONS = ["api_keys"]
    
    # Environment variable prefix
    ENV_PREFIX = "PYGOVPUB_"
    
    def __init__(
        self,
        environment: Environment = Environment.DEVELOPMENT,
        config_dir: Optional[Path] = None,
        secret_key: Optional[str] = None,
    ):
        """Initialize configuration manager."""
        self.environment = environment
        self.config_dir = config_dir or Path.home() / ".pygovpub"
        self.secret_handler = SecretHandler(secret_key)
        
        # Initialize configuration
        self._features: Dict[str, bool] = {
            flag.value: flag.default_value for flag in FeatureFlag
        }
        self._api_keys: Dict[str, str] = {
            "congress": "",
            "govinfo": "",
        }
        self._api_base_urls: Dict[str, str] = {
            "congress": "https://api.congress.gov/v3",
            "govinfo": "https://api.govinfo.gov",
        }
        self._options: Dict[str, Any] = {
            "default_format": "text",
            "cache_ttl": 3600,
        }
        
        # Create profiles
        self._profiles: Dict[Environment, ProfileConfig] = {}
        self._initialize_profiles()
    
    def _initialize_profiles(self) -> None:
        """Initialize environment profiles."""
        # Development profile
        self._profiles[Environment.DEVELOPMENT] = ProfileConfig(
            name=Environment.DEVELOPMENT,
            api_base_urls={
                "congress": "https://api.congress.gov/v3",
                "govinfo": "https://api.govinfo.gov",
            },
            features={
                FeatureFlag.DEBUG_MODE.value: True,
                FeatureFlag.CACHE_ENABLED.value: True,
            },
            options={
                "default_format": "text",
                "cache_ttl": 3600,
                "log_level": "DEBUG",
            },
        )
        
        # Testing profile
        self._profiles[Environment.TEST] = ProfileConfig(
            name=Environment.TEST,
            api_base_urls={
                "congress": "https://api.congress.gov/v3",
                "govinfo": "https://api.govinfo.gov",
            },
            features={
                FeatureFlag.DEBUG_MODE.value: True,
                FeatureFlag.CACHE_ENABLED.value: False,
            },
            options={
                "default_format": "json",
                "cache_ttl": 60,
                "log_level": "INFO",
                "mock_enabled": True,
            },
        )
        
        # Production profile
        self._profiles[Environment.PRODUCTION] = ProfileConfig(
            name=Environment.PRODUCTION,
            api_base_urls={
                "congress": "https://api.congress.gov/v3",
                "govinfo": "https://api.govinfo.gov",
            },
            features={
                FeatureFlag.DEBUG_MODE.value: False,
                FeatureFlag.CACHE_ENABLED.value: True,
                FeatureFlag.ADVANCED_ROUTING.value: True,
            },
            options={
                "default_format": "json",
                "cache_ttl": 7200,
                "log_level": "WARNING",
                "mock_enabled": False,
            },
        )
    
    def get_config_file_path(self, format_type: ConfigFormat = ConfigFormat.JSON) -> Path:
        """Get path to configuration file."""
        # Use XDG_CONFIG_HOME if available
        config_dir = os.environ.get("XDG_CONFIG_HOME")
        if config_dir:
            base_dir = Path(config_dir) / "pygovpub"
        else:
            base_dir = self.config_dir
        
        # Create directory if it doesn't exist
        os.makedirs(base_dir, exist_ok=True)
        
        # Return path with format-specific extension
        return base_dir / f"config{format_type.get_extension()}"
    
    def load_from_env(self) -> None:
        """Load configuration from environment variables."""
        # Environment
        env_value = os.environ.get(f"{self.ENV_PREFIX}ENV")
        if env_value:
            self.environment = Environment.from_string(env_value)
        
        # Feature flags
        for flag in FeatureFlag:
            env_key = f"{self.ENV_PREFIX}FEATURES_{flag.value.upper()}"
            if env_key in os.environ:
                value_str = os.environ[env_key].lower()
                self._features[flag.value] = value_str in ("true", "yes", "1", "on")
        
        # API keys
        for api in self._api_keys:
            env_key = f"{self.ENV_PREFIX}API_{api.upper()}_KEY"
            if env_key in os.environ:
                self._api_keys[api] = os.environ[env_key]
        
        # API base URLs
        for api in self._api_base_urls:
            env_key = f"{self.ENV_PREFIX}API_{api.upper()}_URL"
            if env_key in os.environ:
                self._api_base_urls[api] = os.environ[env_key]
        
        # Options
        for option in self._options:
            env_key = f"{self.ENV_PREFIX}OPTIONS_{option.upper()}"
            if env_key in os.environ:
                self._options[option] = _parse_env_value(os.environ[env_key])
    
    def load_from_file(self, file_path: Optional[Union[str, Path]] = None) -> None:
        """Load configuration from file."""
        # Use default path if not provided
        if file_path is None:
            file_path = self.get_config_file_path()
        
        try:
            # Load config
            config = load_config_from_file(file_path)
            
            # Decrypt sensitive sections
            config = self.secret_handler.unsecure_config(config, self.SENSITIVE_SECTIONS)
            
            # Environment
            if "environment" in config:
                self.environment = Environment.from_string(config["environment"])
            
            # Feature flags
            if "features" in config:
                for flag, value in config["features"].items():
                    if flag in self._features:
                        self._features[flag] = bool(value)
            
            # API keys
            if "api_keys" in config:
                for api, value in config["api_keys"].items():
                    if api in self._api_keys:
                        self._api_keys[api] = value
            
            # API base URLs
            if "api_base_urls" in config:
                for api, value in config["api_base_urls"].items():
                    if api in self._api_base_urls:
                        self._api_base_urls[api] = value
            
            # Options
            if "options" in config:
                for option, value in config["options"].items():
                    self._options[option] = value
        except Exception as e:
            logger.error(f"Failed to load configuration from {file_path}: {e}")
    
    def save_to_file(self, file_path: Optional[Union[str, Path]] = None) -> None:
        """Save configuration to file."""
        # Use default path if not provided
        if file_path is None:
            file_path = self.get_config_file_path()
        
        # Prepare config data
        config = {
            "environment": self.environment.value,
            "features": self._features.copy(),
            "api_keys": self._api_keys.copy(),
            "api_base_urls": self._api_base_urls.copy(),
            "options": self._options.copy(),
            "last_updated": datetime.utcnow().isoformat(),
        }
        
        # Encrypt sensitive sections
        secure_config = self.secret_handler.secure_config(config, self.SENSITIVE_SECTIONS)
        
        try:
            # Save config
            save_config_to_file(secure_config, file_path)
            logger.info(f"Configuration saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration to {file_path}: {e}")
    
    def get_feature_flag(self, flag: FeatureFlag) -> bool:
        """Get feature flag value."""
        return self._features.get(flag.value, flag.default_value)
    
    def set_feature_flag(self, flag: FeatureFlag, value: bool) -> None:
        """Set feature flag value."""
        self._features[flag.value] = bool(value)
    
    def get_api_key(self, api: str) -> str:
        """Get API key."""
        return self._api_keys.get(api, "")
    
    def set_api_key(self, api: str, value: str) -> None:
        """Set API key."""
        self._api_keys[api] = value
    
    def get_api_base_url(self, api: str) -> str:
        """Get API base URL."""
        return self._api_base_urls.get(api, "")
    
    def set_api_base_url(self, api: str, value: str) -> None:
        """Set API base URL."""
        self._api_base_urls[api] = value
    
    def get_option(self, option: str) -> Any:
        """Get option value."""
        return self._options.get(option)
    
    def set_option(self, option: str, value: Any) -> None:
        """Set option value."""
        self._options[option] = value
    
    def switch_profile(self, profile: Environment) -> None:
        """Switch to a different environment profile."""
        if profile not in self._profiles:
            raise ValueError(f"Unknown profile: {profile}")
        
        # Update environment
        self.environment = profile
        
        # Load profile settings
        profile_config = self._profiles[profile]
        
        # Apply feature flags from profile
        for flag, value in profile_config.features.items():
            self._features[flag] = value
        
        # Apply API base URLs from profile
        for api, url in profile_config.api_base_urls.items():
            self._api_base_urls[api] = url
        
        # Apply options from profile
        for option, value in profile_config.options.items():
            self._options[option] = value
        
        logger.info(f"Switched to {profile.value} profile")
    
    def validate(self) -> None:
        """Validate configuration."""
        errors = []
        
        # Check API keys
        missing_keys = []
        for api, key in self._api_keys.items():
            if not key:
                missing_keys.append(api)
        
        if missing_keys:
            errors.append(f"API key missing for: {', '.join(missing_keys)}")
        
        # Check API base URLs
        missing_urls = []
        for api, url in self._api_base_urls.items():
            if not url:
                missing_urls.append(api)
        
        if missing_urls:
            errors.append(f"API base URL missing for: {', '.join(missing_urls)}")
        
        # Check required options
        for option in ["default_format", "cache_ttl"]:
            if option not in self._options:
                errors.append(f"Required option missing: {option}")
        
        # Raise error if any issues found
        if errors:
            raise ConfigValidationError("\n".join(errors))


@lru_cache(maxsize=1)
def get_config_manager() -> ConfigManager:
    """Get the singleton configuration manager instance."""
    manager = ConfigManager()
    
    # Load from environment variables
    manager.load_from_env()
    
    # Try to load from file
    try:
        manager.load_from_file()
    except FileNotFoundError:
        # No config file yet, that's okay
        pass
    
    return manager


# Backwards compatibility for existing code
class Config(BaseModel):
    """Main configuration for the PyGovPub SDK."""
    
    environment: Environment = Field(
        default_factory=lambda: Environment(
            os.getenv("PYGOVPUB_ENV", Environment.DEVELOPMENT)
        )
    )
    apis: Dict[str, ApiConfig] = Field(default_factory=dict)
    mock: MockConfig = Field(default_factory=MockConfig)
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables."""
        config = cls(
            environment=Environment(
                os.getenv("PYGOVPUB_ENV", Environment.DEVELOPMENT)
            ),
            mock=MockConfig(
                enabled=os.getenv("PYGOVPUB_MOCK_ENABLED", "false").lower() == "true",
                latency_ms=int(os.getenv("PYGOVPUB_MOCK_LATENCY_MS", "0")),
                simulate_rate_limits=os.getenv(
                    "PYGOVPUB_MOCK_SIMULATE_RATE_LIMITS", "false"
                ).lower() == "true",
                record_mode=os.getenv("PYGOVPUB_MOCK_RECORD_MODE", "false").lower() == "true",
                fixtures_path=os.getenv("PYGOVPUB_MOCK_FIXTURES_PATH", "fixtures"),
            ),
        )
        
        # Congress.gov API settings
        congress_api_key = os.getenv("CONGRESS_GOV_API_KEY")
        if congress_api_key:
            config.apis["congress"] = ApiConfig(
                base_url=os.getenv(
                    "CONGRESS_GOV_API_URL", 
                    "https://api.congress.gov/v3"
                ),
                api_key=congress_api_key,
                rate_limit=int(os.getenv("CONGRESS_GOV_RATE_LIMIT", "5000")),
            )
        
        # GovInfo.gov API settings
        govinfo_api_key = os.getenv("GOVINFO_API_KEY")
        if govinfo_api_key:
            config.apis["govinfo"] = ApiConfig(
                base_url=os.getenv(
                    "GOVINFO_API_URL", 
                    "https://api.govinfo.gov"
                ),
                api_key=govinfo_api_key,
                rate_limit=int(os.getenv("GOVINFO_RATE_LIMIT", "1000")),
            )
        
        return config


# Default configuration instance for backward compatibility
config = Config.from_env()