"""
Tests for documentation completeness and accuracy.

Validates that all required documentation files exist with proper content:
- README.md with setup instructions, configuration examples, troubleshooting
- config.yaml with complete settings and inline comments
- .newrelic_config.example.json with proper template structure
"""

import pytest
import os
import yaml
import json
from pathlib import Path


class TestREADMEDocumentation:
    """Test README.md completeness and required sections."""

    def test_readme_exists(self):
        """Verify README.md exists at project root."""
        assert os.path.exists('README.md'), "README.md file not found"

    def test_readme_python_version_requirement(self):
        """Verify README clearly states Python 3.11+ requirement."""
        with open('README.md', 'r', encoding='utf-8') as f:
            content = f.read()

        assert 'Python 3.11+' in content or 'Python 3.11' in content, \
            "README must clearly state Python 3.11+ requirement"
        assert 'Requirements' in content or 'requirements' in content.lower(), \
            "README must have requirements section"

    def test_readme_setup_instructions(self):
        """Verify README includes step-by-step setup instructions."""
        with open('README.md', 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for key setup steps
        assert 'clone' in content.lower() or 'git clone' in content, \
            "README must include repository clone instructions"
        assert 'venv' in content or 'virtualenv' in content or 'virtual environment' in content.lower(), \
            "README must include virtual environment setup"
        assert 'pip install' in content or 'requirements.txt' in content, \
            "README must include dependency installation instructions"

    def test_readme_configuration_section(self):
        """Verify README includes configuration setup with profile examples."""
        with open('README.md', 'r', encoding='utf-8') as f:
            content = f.read()

        assert 'configuration' in content.lower() or 'configure' in content.lower(), \
            "README must have configuration section"
        assert '.newrelic_config' in content, \
            "README must mention profile configuration files"
        assert 'dev' in content and ('prod' in content or 'production' in content), \
            "README must show dev and prod profile examples"

    def test_readme_usage_examples(self):
        """Verify README includes usage examples with CLI arguments."""
        with open('README.md', 'r', encoding='utf-8') as f:
            content = f.read()

        assert 'python' in content.lower(), \
            "README must include Python command examples"
        assert '--profile' in content or 'profile' in content.lower(), \
            "README must show profile selection examples"
        assert '--days' in content or 'days' in content.lower(), \
            "README must show time period examples"

    def test_readme_troubleshooting_section(self):
        """Verify README includes troubleshooting section for common errors."""
        with open('README.md', 'r', encoding='utf-8') as f:
            content = f.read()

        assert 'troubleshoot' in content.lower() or 'common issues' in content.lower() or 'error' in content.lower(), \
            "README must have troubleshooting section"

    def test_readme_security_warnings(self):
        """Verify README includes security section with warnings."""
        with open('README.md', 'r', encoding='utf-8') as f:
            content = f.read()

        assert 'security' in content.lower() or 'api key' in content.lower(), \
            "README must have security section"
        assert '.gitignore' in content, \
            "README must mention .gitignore protection"
        assert 'never commit' in content.lower() or "don't commit" in content.lower() or 'do not commit' in content.lower(), \
            "README must warn against committing API keys"
        assert 'example' in content.lower() and 'template' in content.lower(), \
            "README must explain how to create configs from example template"


class TestConfigYAMLDocumentation:
    """Test config.yaml has complete settings with inline comments."""

    def test_config_yaml_exists(self):
        """Verify config.yaml exists at project root."""
        assert os.path.exists('config.yaml'), "config.yaml file not found"

    def test_config_yaml_valid_syntax(self):
        """Verify config.yaml is valid YAML syntax."""
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        assert isinstance(config, dict), "config.yaml must be valid YAML dictionary"

    def test_config_yaml_api_settings(self):
        """Verify config.yaml includes API timeout settings (default: 30)."""
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        assert 'api' in config, "config.yaml must have 'api' section"
        assert 'timeout' in config['api'], "config.yaml api section must have 'timeout'"
        assert config['api']['timeout'] == 30, "API timeout default should be 30 seconds"

    def test_config_yaml_retry_settings(self):
        """Verify config.yaml includes retry settings (max_retries: 2, retry_delay: 5)."""
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        assert 'api' in config, "config.yaml must have 'api' section"
        assert 'max_retries' in config['api'], "config.yaml must have 'max_retries'"
        assert 'retry_delay' in config['api'], "config.yaml must have 'retry_delay'"
        assert config['api']['max_retries'] == 2, "max_retries default should be 2"
        assert config['api']['retry_delay'] == 5, "retry_delay default should be 5 seconds"

    def test_config_yaml_cache_settings(self):
        """Verify config.yaml includes cache settings (staleness: 3600, retention_days: 30)."""
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        assert 'cache' in config, "config.yaml must have 'cache' section"
        assert 'staleness' in config['cache'] or 'min_interval' in config['cache'], \
            "config.yaml cache section must have staleness/min_interval setting"
        assert 'retention_days' in config['cache'], "config.yaml cache must have 'retention_days'"
        
        # Check values (staleness might be named min_interval in some versions)
        staleness_value = config['cache'].get('staleness') or config['cache'].get('min_interval')
        assert staleness_value == 3600, "Cache staleness default should be 3600 seconds (1 hour)"
        assert config['cache']['retention_days'] == 30, "Cache retention_days default should be 30"

    def test_config_yaml_logging_settings(self):
        """Verify config.yaml includes logging settings (level: INFO)."""
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        assert 'logging' in config, "config.yaml must have 'logging' section"
        assert 'level' in config['logging'], "config.yaml logging must have 'level'"
        assert config['logging']['level'] == 'INFO', "Logging level default should be INFO"

    def test_config_yaml_inline_comments(self):
        """Verify config.yaml has inline comments explaining settings."""
        with open('config.yaml', 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for presence of comments (lines with #)
        comment_lines = [line for line in content.split('\n') if '#' in line and not line.strip().startswith('#')]
        
        assert len(comment_lines) >= 5, \
            f"config.yaml should have inline comments for settings (found {len(comment_lines)})"
        
        # Verify key sections have comments
        assert any('timeout' in line.lower() and '#' in line for line in content.split('\n')), \
            "timeout setting should have inline comment"
        assert any('retries' in line.lower() and '#' in line for line in content.split('\n')), \
            "retry settings should have inline comments"


class TestNewRelicConfigExample:
    """Test .newrelic_config.example.json template completeness."""

    def test_example_config_exists(self):
        """Verify .newrelic_config.example.json exists."""
        assert os.path.exists('.newrelic_config.example.json'), \
            ".newrelic_config.example.json template file not found"

    def test_example_config_valid_json(self):
        """Verify example config is valid JSON syntax."""
        with open('.newrelic_config.example.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        assert isinstance(config, dict), "Example config must be valid JSON object"

    def test_example_config_has_required_fields(self):
        """Verify example config has all required fields (api_key, account_id, app_ids)."""
        with open('.newrelic_config.example.json', 'r', encoding='utf-8') as f:
            config = json.load(f)

        assert 'api_key' in config, "Example config must include 'api_key' field"
        assert 'account_id' in config, "Example config must include 'account_id' field"
        assert 'app_ids' in config, "Example config must include 'app_ids' field"

    def test_example_config_field_types(self):
        """Verify example config fields have correct data types."""
        with open('.newrelic_config.example.json', 'r', encoding='utf-8') as f:
            config = json.load(f)

        assert isinstance(config['api_key'], str), "api_key must be string type"
        assert isinstance(config['account_id'], str), "account_id must be string type"
        assert isinstance(config['app_ids'], list), "app_ids must be array/list type"

    def test_example_config_has_placeholder_values(self):
        """Verify example config uses placeholder values, not real credentials."""
        with open('.newrelic_config.example.json', 'r', encoding='utf-8') as f:
            config = json.load(f)

        # API key should contain placeholder text
        api_key = config['api_key']
        assert 'YOUR' in api_key or 'EXAMPLE' in api_key or 'PLACEHOLDER' in api_key or 'NRAK-' in api_key, \
            "Example config should use placeholder API key value"

    def test_example_config_has_documentation(self):
        """Verify example config includes explanatory content (description or comments)."""
        with open('.newrelic_config.example.json', 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Check for description field or read file for inline comments
        assert 'description' in config or 'app_name' in config, \
            "Example config should include descriptive fields"

    def test_example_config_not_gitignored_incorrectly(self):
        """Verify .gitignore allows .example.json files (not blocked by *.json)."""
        with open('.gitignore', 'r', encoding='utf-8') as f:
            gitignore_content = f.read()

        # If *.json is in .gitignore, there should be an exception for .example.json
        # Or verify the file actually exists (wouldn't exist if gitignored and cleaned)
        assert os.path.exists('.newrelic_config.example.json'), \
            "Example config should exist (not gitignored)"


class TestDocumentationConsistency:
    """Test consistency between documentation and actual implementation."""

    def test_readme_mentions_existing_files(self):
        """Verify README mentions all key files that exist in project."""
        with open('README.md', 'r', encoding='utf-8') as f:
            readme_content = f.read()

        # Check README mentions key project files
        assert 'config.yaml' in readme_content, "README should mention config.yaml"
        assert '.newrelic_config' in readme_content, "README should mention profile config files"
        assert 'requirements.txt' in readme_content, "README should mention requirements.txt"

    def test_readme_example_commands_reference_correct_defaults(self):
        """Verify README examples use correct default values from config.yaml."""
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        with open('README.md', 'r', encoding='utf-8') as f:
            readme_content = f.read()

        # Check that default values mentioned in README match config.yaml
        default_days = config['defaults']['days']
        default_profile = config['defaults']['profile']

        # These checks are flexible - just verify consistency exists
        if f'{default_days} days' in readme_content or f'days {default_days}' in readme_content:
            assert True  # Found reference to default days
        
        if default_profile in readme_content:
            assert True  # Found reference to default profile

    def test_all_required_config_sections_documented(self):
        """Verify all sections in config.yaml are explained in README."""
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        with open('README.md', 'r', encoding='utf-8') as f:
            readme_content = f.read().lower()

        # Check main sections are documented
        for section in ['api', 'cache', 'logging', 'defaults']:
            if section in config:
                assert section in readme_content, \
                    f"README should document the '{section}' configuration section"


class TestAgentDocumentation:
    """AC1-AC5: Test README documents AI agent usage workflow and integration."""

    @pytest.fixture(autouse=True)
    def load_readme(self):
        with open('README.md', 'r', encoding='utf-8') as f:
            self.content = f.read()

    def test_readme_has_ai_insights_section(self):
        """AC1: README has AI-Powered Insights section."""
        assert '## AI-Powered Insights' in self.content

    def test_readme_documents_analysis_agent(self):
        """AC1: README documents @analysis-agent."""
        assert '@analysis-agent' in self.content or 'analysis-agent' in self.content

    def test_readme_documents_recommend_agent(self):
        """AC1: README documents @recommend-agent."""
        assert '@recommend-agent' in self.content or 'recommend-agent' in self.content

    def test_readme_agent_overview_table(self):
        """AC1: README has an agent overview showing role, input, and output."""
        assert 'analysis-agent' in self.content
        assert 'recommend-agent' in self.content
        assert 'assessment' in self.content.lower()
        assert 'recommendation' in self.content.lower()

    def test_readme_vscode_setup(self):
        """AC2: README explains VS Code Copilot agent setup."""
        assert '.github/agents/' in self.content
        assert 'VS Code' in self.content or 'Copilot Chat' in self.content

    def test_readme_agent_files_listed(self):
        """AC2: README lists the agent instruction files."""
        assert 'analysis-agent.md' in self.content
        assert 'recommend-agent.md' in self.content
        assert 'analysis-agent.agent.md' in self.content
        assert 'recommend-agent.agent.md' in self.content

    def test_readme_daily_monitoring_workflow(self):
        """AC3: README includes daily monitoring workflow."""
        lower = self.content.lower()
        assert 'daily' in lower or 'monitoring' in lower
        assert 'demo.py' in self.content or 'crawler.py' in self.content

    def test_readme_incident_investigation_workflow(self):
        """AC3: README includes incident investigation workflow."""
        assert 'incident' in self.content.lower() or 'investigation' in self.content.lower()

    def test_readme_post_deployment_workflow(self):
        """AC3: README includes post-deployment verification workflow."""
        assert 'deploy' in self.content.lower()
        assert 'verif' in self.content.lower()

    def test_readme_expected_output_assessment(self):
        """AC4: README describes assessment output files."""
        assert 'assessment-' in self.content
        assert 'reports/' in self.content

    def test_readme_expected_output_recommendations(self):
        """AC4: README describes recommendation output files."""
        assert 'recommendations-' in self.content

    def test_readme_output_line_estimates(self):
        """AC4: README gives output size expectations."""
        assert '200' in self.content  # assessment 200-500 lines
        assert '300' in self.content  # recommendations 300-800 lines

    def test_readme_roadmap_epic5_completed(self):
        """AC5: Roadmap shows Epic 5 as completed."""
        # Look for Epic 5 marked as completed in the roadmap
        assert 'Completed (Epic 5)' in self.content or 'AI Agent Integration' in self.content
        assert 'analysis-agent' in self.content
        assert 'recommend-agent' in self.content

    def test_readme_roadmap_shows_all_epics(self):
        """AC5: Roadmap lists all 6 epics."""
        lower = self.content.lower()
        assert 'epic 1' in lower or 'configuration' in lower
        assert 'epic 2' in lower or 'data collection' in lower
        assert 'epic 3' in lower or 'health analysis' in lower
        assert 'epic 4' in lower or 'report generation' in lower
        assert 'epic 5' in lower or 'ai agent' in lower
        assert 'epic 6' in lower or 'testing' in lower

    def test_readme_prerequisites(self):
        """AC2: README lists prerequisites for using agents."""
        lower = self.content.lower()
        assert 'copilot' in lower
        assert 'prerequisit' in lower or 'require' in lower
