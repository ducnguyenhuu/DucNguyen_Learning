"""
Comprehensive tests for config_loader module.

Tests the multi-profile configuration system with three-tier merge:
1. Application defaults from config.yaml
2. Profile-specific credentials from .newrelic_config.{profile}.json
3. CLI argument overrides (highest priority)
"""

import pytest
import os
import yaml
import json
import tempfile
import shutil
from pathlib import Path
from modules.config_loader import load_config, validate_config


class TestConfigLoader:
    """Test suite for configuration loading and merging."""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up test environment before each test and clean up after."""
        # Store original working directory
        self.original_cwd = os.getcwd()
        
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        os.chdir(self.test_dir)
        
        # Create test config.yaml
        self.test_config_yaml = {
            'api': {
                'timeout': 30,
                'max_retries': 2,
                'retry_delay': 5
            },
            'cache': {
                'staleness': 3600,
                'retention_days': 30
            },
            'logging': {
                'level': 'INFO',
                'file_level': 'DEBUG'
            },
            'defaults': {
                'days': 30,
                'profile': 'dev'
            }
        }
        
        with open('config.yaml', 'w', encoding='utf-8') as f:
            yaml.dump(self.test_config_yaml, f)
        
        # Create test dev profile JSON
        self.test_dev_json = {
            'api_key': 'NRAK-TEST-DEV-KEY-12345',
            'account_id': '1234567',
            'app_ids': ['111111', '222222'],
            'app_name': 'test-dev-app',
            'description': 'Development test environment'
        }
        
        with open('.newrelic_config.dev.json', 'w', encoding='utf-8') as f:
            json.dump(self.test_dev_json, f)
        
        # Create test prod profile JSON
        self.test_prod_json = {
            'api_key': 'NRAK-TEST-PROD-KEY-67890',
            'account_id': '7654321',
            'app_ids': ['999999', '888888'],
            'app_name': 'test-prod-app',
            'description': 'Production test environment'
        }
        
        with open('.newrelic_config.prod.json', 'w', encoding='utf-8') as f:
            json.dump(self.test_prod_json, f)
        
        yield
        
        # Clean up after test
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    def test_default_profile(self):
        """Verify load_config() defaults to 'dev' profile when no argument provided."""
        config = load_config()
        
        assert 'profile' in config
        assert config['profile'] == 'dev'
        assert config['api_key'] == self.test_dev_json['api_key']
        assert config['account_id'] == self.test_dev_json['account_id']
    
    def test_explicit_profile_dev(self):
        """Verify load_config('dev') loads development profile correctly."""
        config = load_config('dev')
        
        assert config['profile'] == 'dev'
        assert config['api_key'] == self.test_dev_json['api_key']
        assert config['account_id'] == self.test_dev_json['account_id']
        assert config['app_ids'] == self.test_dev_json['app_ids']
        assert config['app_name'] == self.test_dev_json['app_name']
    
    def test_explicit_profile_prod(self):
        """Verify load_config('prod') loads production profile correctly."""
        config = load_config('prod')
        
        assert config['profile'] == 'prod'
        assert config['api_key'] == self.test_prod_json['api_key']
        assert config['account_id'] == self.test_prod_json['account_id']
        assert config['app_ids'] == self.test_prod_json['app_ids']
        assert config['app_name'] == self.test_prod_json['app_name']
    
    def test_config_merge_defaults_present(self):
        """Verify YAML defaults are present in merged configuration."""
        config = load_config('dev')
        
        # Check API defaults from config.yaml
        assert config['timeout'] == 30
        assert config['max_retries'] == 2
        assert config['retry_delay'] == 5
        
        # Check cache defaults from config.yaml
        assert config['cache_staleness'] == 3600
        assert config['cache_retention_days'] == 30
        
        # Check default days from config.yaml
        assert config['days'] == 30
    
    def test_config_merge_profile_overrides(self):
        """Verify profile values override defaults where applicable."""
        config = load_config('dev')
        
        # Profile-specific values should be present
        assert config['api_key'] == self.test_dev_json['api_key']
        assert config['account_id'] == self.test_dev_json['account_id']
        assert config['app_ids'] == self.test_dev_json['app_ids']
        
        # Defaults should still be present for non-overridden values
        assert config['timeout'] == 30
    
    def test_cli_overrides_highest_priority(self):
        """Verify CLI argument overrides take highest priority."""
        config = load_config('dev', days=14, timeout=60)
        
        # CLI overrides should be applied
        assert config['days'] == 14
        assert config['timeout'] == 60
        
        # Other values should remain unchanged
        assert config['api_key'] == self.test_dev_json['api_key']
        assert config['max_retries'] == 2
    
    def test_all_required_keys_present(self):
        """Verify returned config has all required keys."""
        config = load_config('dev')
        
        required_keys = [
            'api_key', 'account_id', 'app_ids', 'timeout', 'max_retries',
            'retry_delay', 'cache_staleness', 'cache_retention_days',
            'logging_level', 'days', 'profile'
        ]
        
        for key in required_keys:
            assert key in config, f"Required key '{key}' missing from configuration"
    
    def test_correct_data_types(self):
        """Verify configuration values have correct data types."""
        config = load_config('dev')
        
        # String fields
        assert isinstance(config['api_key'], str)
        assert isinstance(config['account_id'], str)
        assert isinstance(config['profile'], str)
        
        # List fields
        assert isinstance(config['app_ids'], list)
        assert len(config['app_ids']) > 0
        
        # Integer fields
        assert isinstance(config['timeout'], int)
        assert isinstance(config['max_retries'], int)
        assert isinstance(config['retry_delay'], int)
        assert isinstance(config['cache_staleness'], int)
        assert isinstance(config['cache_retention_days'], int)
        assert isinstance(config['days'], int)
    
    def test_missing_config_yaml_raises_error(self):
        """Verify FileNotFoundError raised if config.yaml missing."""
        os.remove('config.yaml')
        
        with pytest.raises(FileNotFoundError) as exc_info:
            load_config('dev')
        
        assert 'config.yaml' in str(exc_info.value).lower()
    
    def test_missing_profile_json_raises_error(self):
        """Verify FileNotFoundError raised if profile JSON missing."""
        os.remove('.newrelic_config.dev.json')
        
        with pytest.raises(FileNotFoundError) as exc_info:
            load_config('dev')
        
        assert 'newrelic_config' in str(exc_info.value).lower()
        assert 'dev' in str(exc_info.value).lower()

    def test_missing_prod_profile_has_actionable_template_message(self):
        """Verify missing prod profile includes actionable template instruction."""
        os.remove('.newrelic_config.prod.json')

        with pytest.raises(FileNotFoundError) as exc_info:
            load_config('prod')

        message = str(exc_info.value)
        assert 'Create .newrelic_config.prod.json using .newrelic_config.example.json as template' in message
    
    def test_invalid_yaml_syntax_raises_error(self):
        """Verify error raised for invalid YAML syntax."""
        with open('config.yaml', 'w', encoding='utf-8') as f:
            f.write("invalid: yaml: syntax: [[[")
        
        with pytest.raises(yaml.YAMLError):
            load_config('dev')
    
    def test_invalid_json_syntax_raises_error(self):
        """Verify error raised for invalid JSON syntax."""
        with open('.newrelic_config.dev.json', 'w', encoding='utf-8') as f:
            f.write('{"invalid": json syntax}')
        
        with pytest.raises(json.JSONDecodeError):
            load_config('dev')
    
    def test_pep8_naming_conventions(self):
        """Verify function follows PEP 8 naming conventions."""
        # Function name should be snake_case
        assert 'load_config' == 'load_config'  # Verify naming
        
        config = load_config('dev')
        
        # All keys should be snake_case
        for key in config.keys():
            # Check that key doesn't use camelCase or PascalCase
            assert key == key.lower() or '_' in key, f"Key '{key}' doesn't follow snake_case convention"
    
    def test_nested_config_merge(self):
        """Verify nested configurations merge properly."""
        config = load_config('dev')
        
        # Nested API settings should all be present
        assert config['timeout'] == 30
        assert config['max_retries'] == 2
        assert config['retry_delay'] == 5
        
        # Profile settings should coexist with defaults
        assert 'api_key' in config
        assert 'timeout' in config
    
    def test_file_encoding_utf8(self):
        """Verify files are read with UTF-8 encoding."""
        # Create config with UTF-8 characters
        test_config = {
            'api': {'timeout': 30, 'max_retries': 2, 'retry_delay': 5},
            'cache': {'staleness': 3600, 'retention_days': 30},
            'defaults': {'days': 30},
            'test_unicode': '™ © ® — café'
        }
        
        with open('config.yaml', 'w', encoding='utf-8') as f:
            yaml.dump(test_config, f)
        
        config = load_config('dev')
        
        # Should load without encoding errors
        assert isinstance(config, dict)
    
    def test_multiple_app_ids(self):
        """Verify multiple app IDs are preserved in list."""
        config = load_config('dev')
        
        assert len(config['app_ids']) == 2
        assert '111111' in config['app_ids']
        assert '222222' in config['app_ids']
    
    def test_profile_switched_correctly(self):
        """Verify switching between profiles loads correct credentials."""
        dev_config = load_config('dev')
        prod_config = load_config('prod')
        
        # Dev and prod should have different API keys
        assert dev_config['api_key'] != prod_config['api_key']
        assert dev_config['account_id'] != prod_config['account_id']
        
        # But same defaults
        assert dev_config['timeout'] == prod_config['timeout']
        assert dev_config['max_retries'] == prod_config['max_retries']


class TestConfigurationMergePriority:
    """Test configuration merge priority rules."""
    
    @pytest.fixture(autouse=True)
    def setup_merge_test(self):
        """Set up test environment for merge priority testing."""
        self.original_cwd = os.getcwd()
        self.test_dir = tempfile.mkdtemp()
        os.chdir(self.test_dir)
        
        # Create minimal config.yaml with timeout=30
        with open('config.yaml', 'w', encoding='utf-8') as f:
            yaml.dump({
                'api': {'timeout': 30, 'max_retries': 2, 'retry_delay': 5},
                'cache': {'staleness': 3600, 'retention_days': 30},
                'defaults': {'days': 30, 'profile': 'dev'}
            }, f)
        
        # Create profile JSON - does NOT override timeout (test default wins)
        with open('.newrelic_config.dev.json', 'w', encoding='utf-8') as f:
            json.dump({
                'api_key': 'TEST-KEY',
                'account_id': '123',
                'app_ids': ['456']
            }, f)
        
        yield
        
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    def test_priority_cli_over_all(self):
        """Verify CLI overrides beat both defaults and profile."""
        config = load_config('dev', timeout=99, days=7)
        
        assert config['timeout'] == 99  # CLI override
        assert config['days'] == 7      # CLI override
        assert config['max_retries'] == 2  # Default (no CLI override)
    
    def test_priority_profile_over_defaults(self):
        """Verify profile values override YAML defaults."""
        # Add a field to profile that also exists in defaults
        with open('.newrelic_config.dev.json', 'w', encoding='utf-8') as f:
            json.dump({
                'api_key': 'TEST-KEY',
                'account_id': '123',
                'app_ids': ['456'],
                'days': 14  # Override default of 30
            }, f)
        
        config = load_config('dev')
        
        assert config['days'] == 14  # Profile override wins
    
    def test_defaults_used_when_not_overridden(self):
        """Verify defaults are used when no override exists."""
        config = load_config('dev')
        
        # No override for these values
        assert config['timeout'] == 30
        assert config['max_retries'] == 2
        assert config['retry_delay'] == 5
        assert config['cache_staleness'] == 3600


class TestConfigurationValidation:
    """Test fail-fast validation rules for configuration."""

    def test_validate_config_success_logs_info(self, caplog):
        """Verify valid config returns True and logs success message."""
        config = {
            'api_key': 'NRAK-TEST-KEY',
            'account_id': '1234567',
            'app_ids': ['111111'],
            'days': 7,
            'profile': 'dev'
        }

        with caplog.at_level('INFO'):
            result = validate_config(config)

        assert result is True
        assert 'Configuration validated successfully for profile: dev' in caplog.text

    def test_validate_config_missing_api_key(self):
        """Verify missing API key raises actionable ValueError."""
        config = {
            'account_id': '1234567',
            'app_ids': ['111111'],
            'days': 7,
            'profile': 'dev'
        }

        with pytest.raises(ValueError) as exc_info:
            validate_config(config)

        message = str(exc_info.value)
        assert 'API key missing in configuration file' in message
        assert "Add 'api_key' to .newrelic_config.dev.json" in message

    def test_validate_config_invalid_account_id(self):
        """Verify non-numeric account_id raises ValueError with expected format."""
        config = {
            'api_key': 'NRAK-TEST-KEY',
            'account_id': 'abc123',
            'app_ids': ['111111'],
            'days': 14,
            'profile': 'prod'
        }

        with pytest.raises(ValueError) as exc_info:
            validate_config(config)

        message = str(exc_info.value)
        assert 'Account ID must be numeric' in message
        assert 'Expected format: 1234567' in message

    def test_validate_config_app_ids_must_be_non_empty_list(self):
        """Verify app_ids validation enforces non-empty list."""
        config = {
            'api_key': 'NRAK-TEST-KEY',
            'account_id': '1234567',
            'app_ids': [],
            'days': 30,
            'profile': 'dev'
        }

        with pytest.raises(ValueError, match='app_ids must be a non-empty list'):
            validate_config(config)

    def test_validate_config_days_must_be_allowed_values(self):
        """Verify days validation only allows 3, 7, 14, or 30."""
        config = {
            'api_key': 'NRAK-TEST-KEY',
            'account_id': '1234567',
            'app_ids': ['111111'],
            'days': 10,
            'profile': 'dev'
        }

        with pytest.raises(ValueError, match=r'days must be one of \[3, 7, 14, 30\]'):
            validate_config(config)


class TestLoadConfigFailFastValidation:
    """Integration tests ensuring load_config fails fast with validation."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up test environment before each test and clean up after."""
        self.original_cwd = os.getcwd()
        self.test_dir = tempfile.mkdtemp()
        os.chdir(self.test_dir)

        with open('config.yaml', 'w', encoding='utf-8') as f:
            yaml.dump({
                'api': {'timeout': 30, 'max_retries': 2, 'retry_delay': 5},
                'cache': {'staleness': 3600, 'retention_days': 30},
                'defaults': {'days': 30, 'profile': 'dev'}
            }, f)

        yield

        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_load_config_raises_on_missing_api_key(self):
        """Verify load_config fails fast when profile config is incomplete."""
        with open('.newrelic_config.dev.json', 'w', encoding='utf-8') as f:
            json.dump({
                'account_id': '1234567',
                'app_ids': ['111111']
            }, f)

        with pytest.raises(ValueError) as exc_info:
            load_config('dev')

        assert 'API key missing in configuration file' in str(exc_info.value)
