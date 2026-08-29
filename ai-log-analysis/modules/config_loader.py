"""Configuration loader for New Relic APM Health Assessment Tool.

Supports multi-profile environments (dev/prod) with three-tier configuration:
1. Application defaults from config.yaml
2. Profile-specific credentials from .newrelic_config.{profile}.json
3. CLI argument overrides (highest priority)
"""

import logging
import yaml
import json
from pathlib import Path
from typing import Any, Dict

# Constants
DEFAULT_PROFILE = 'dev'
CONFIG_FILE = 'config.yaml'
PROFILE_CONFIG_TEMPLATE = '.newrelic_config.{profile}.json'
ALLOWED_DAYS = {1, 3, 7, 14, 30}


logger = logging.getLogger(__name__)


def load_config(profile: str = 'dev', **cli_overrides: Any) -> Dict[str, Any]:
    """Load configuration with multi-source merging.
    
    Args:
        profile: Environment profile ('dev' or 'prod'). Defaults to 'dev'.
        **cli_overrides: CLI argument overrides (highest priority).
        
    Returns:
        Complete configuration dictionary with all required keys.
        
    Raises:
        FileNotFoundError: If config.yaml or profile JSON file missing.
        yaml.YAMLError: If config.yaml has invalid syntax.
        json.JSONDecodeError: If profile JSON has invalid syntax.
    
    Example:
        >>> config = load_config('dev')
        >>> config['api_key']
        'NRAK-...'
        
        >>> config = load_config('prod', days=14, timeout=60)
        >>> config['days']
        14
    """
    # Load defaults from YAML
    defaults = _load_yaml_defaults()
    
    # Load profile-specific configuration
    profile_config = _load_profile_config(profile)
    
    # Merge configurations with proper precedence
    merged = _merge_configs(defaults, profile_config, cli_overrides)
    
    # Add profile name to final config
    merged['profile'] = profile

    # Validate configuration (fail-fast)
    validate_config(merged)
    
    return merged


def _load_yaml_defaults() -> Dict[str, Any]:
    """Load application defaults from config.yaml.
    
    Returns:
        Dictionary of default configuration settings.
        
    Raises:
        FileNotFoundError: If config.yaml not found.
        yaml.YAMLError: If YAML syntax invalid.
    """
    config_path = Path(CONFIG_FILE)
    
    if not config_path.exists():
        raise FileNotFoundError(
            f"config.yaml not found at project root. Ensure file exists."
        )
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML syntax in config.yaml: {e}")
    
    # Flatten nested structure for easier access
    flattened = {}
    
    # Extract API settings
    if 'api' in yaml_config:
        flattened['timeout'] = yaml_config['api'].get('timeout', 30)
        flattened['max_retries'] = yaml_config['api'].get('max_retries', 2)
        flattened['retry_delay'] = yaml_config['api'].get('retry_delay', 5)
    
    # Extract cache settings
    if 'cache' in yaml_config:
        flattened['cache_staleness'] = yaml_config['cache'].get('staleness', 3600)
        flattened['cache_retention_days'] = yaml_config['cache'].get('retention_days', 30)
    
    # Extract logging settings
    if 'logging' in yaml_config:
        flattened['logging_level'] = yaml_config['logging'].get('level', 'INFO')
        flattened['logging_file_level'] = yaml_config['logging'].get('file_level', 'DEBUG')
    
    # Extract defaults
    if 'defaults' in yaml_config:
        flattened['days'] = yaml_config['defaults'].get('days', 30)
    
    return flattened


def _load_profile_config(profile: str) -> Dict[str, Any]:
    """Load profile-specific configuration from JSON file.
    
    Args:
        profile: Environment profile name ('dev' or 'prod').
        
    Returns:
        Dictionary of profile-specific settings (API credentials, app IDs).
        
    Raises:
        FileNotFoundError: If profile JSON file not found.
        json.JSONDecodeError: If JSON syntax invalid.
    """
    profile_filename = PROFILE_CONFIG_TEMPLATE.format(profile=profile)
    profile_path = Path(profile_filename)
    
    if not profile_path.exists():
        raise FileNotFoundError(
            f"Profile file '{profile_filename}' not found. "
            f"Create {profile_filename} using .newrelic_config.example.json as template."
        )
    
    try:
        with open(profile_path, 'r', encoding='utf-8') as f:
            profile_config = json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON syntax in {profile_filename}", 
            e.doc, 
            e.pos
        )
    
    return profile_config


def _merge_configs(defaults: Dict[str, Any], 
                   profile: Dict[str, Any], 
                   overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Merge configuration sources with proper precedence.
    
    Priority: CLI overrides > profile config > defaults
    
    Args:
        defaults: Application defaults from config.yaml
        profile: Profile-specific settings from .newrelic_config.{profile}.json
        overrides: CLI argument overrides
        
    Returns:
        Merged configuration dictionary.
    """
    # Start with defaults
    merged = defaults.copy()
    
    # Apply profile config (overrides defaults)
    merged.update(profile)
    
    # Apply CLI overrides (highest priority)
    merged.update(overrides)
    
    return merged


def validate_config(config: Dict[str, Any]) -> bool:
    """Validate merged configuration and fail fast on invalid values.

    Args:
        config: Fully merged configuration dictionary.

    Returns:
        True if configuration is valid.

    Raises:
        ValueError: If required fields are missing or invalid.
    """
    profile = config.get('profile', DEFAULT_PROFILE)

    api_key = config.get('api_key')
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError(
            f"API key missing in configuration file. "
            f"Add 'api_key' to .newrelic_config.{profile}.json"
        )

    account_id = config.get('account_id')
    if not isinstance(account_id, str) or not account_id.isdigit():
        raise ValueError("Account ID must be numeric. Expected format: 1234567")

    app_ids = config.get('app_ids')
    if not isinstance(app_ids, list) or not app_ids:
        raise ValueError("app_ids must be a non-empty list")

    days = config.get('days')
    if not isinstance(days, int) or days not in ALLOWED_DAYS:
        raise ValueError("days must be one of [3, 7, 14, 30]")

    logger.info("Configuration validated successfully for profile: %s", profile)
    return True
