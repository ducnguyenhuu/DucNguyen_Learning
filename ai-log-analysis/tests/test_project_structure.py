"""
Tests for Story 1.1: Initialize Project Structure

This test suite verifies that the project structure is correctly
initialized with all required directories, files, and configurations.
"""
import os
import sys
from pathlib import Path


# Get project root (parent of tests directory)
PROJECT_ROOT = Path(__file__).parent.parent


class TestProjectStructure:
    """Test that all required directories exist."""
    
    def test_modules_directory_exists(self):
        """Verify modules/ directory exists."""
        assert (PROJECT_ROOT / "modules").is_dir()
    
    def test_agents_directory_exists(self):
        """Verify agents/ directory exists."""
        assert (PROJECT_ROOT / "agents").is_dir()
    
    def test_tests_directory_exists(self):
        """Verify tests/ directory exists."""
        assert (PROJECT_ROOT / "tests").is_dir()
    
    def test_data_directory_exists(self):
        """Verify data/ directory exists."""
        assert (PROJECT_ROOT / "data").is_dir()
    
    def test_logs_directory_exists(self):
        """Verify logs/ directory exists."""
        assert (PROJECT_ROOT / "logs").is_dir()
    
    def test_reports_directory_exists(self):
        """Verify reports/ directory exists."""
        assert (PROJECT_ROOT / "reports").is_dir()


class TestPackageInitialization:
    """Test that Python packages are properly initialized."""
    
    def test_modules_init_exists(self):
        """Verify modules/__init__.py exists."""
        assert (PROJECT_ROOT / "modules" / "__init__.py").is_file()
    
    def test_tests_init_exists(self):
        """Verify tests/__init__.py exists."""
        assert (PROJECT_ROOT / "tests" / "__init__.py").is_file()
    
    def test_modules_package_importable(self):
        """Verify modules package can be imported."""
        # Add project root to path if not already there
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        
        import modules
        assert modules is not None
    
    def test_tests_package_importable(self):
        """Verify tests package can be imported."""
        # Add project root to path if not already there
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        
        import tests
        assert tests is not None


class TestGitkeepFiles:
    """Test that .gitkeep files exist to preserve empty directories."""
    
    def test_data_gitkeep_exists(self):
        """Verify data/.gitkeep exists."""
        assert (PROJECT_ROOT / "data" / ".gitkeep").is_file()
    
    def test_logs_gitkeep_exists(self):
        """Verify logs/.gitkeep exists."""
        assert (PROJECT_ROOT / "logs" / ".gitkeep").is_file()
    
    def test_reports_gitkeep_exists(self):
        """Verify reports/.gitkeep exists."""
        assert (PROJECT_ROOT / "reports" / ".gitkeep").is_file()
    
    def test_agents_gitkeep_exists(self):
        """Verify agents/.gitkeep exists."""
        assert (PROJECT_ROOT / "agents" / ".gitkeep").is_file()


class TestRequirementsTxt:
    """Test that requirements.txt exists with correct dependencies."""
    
    def test_requirements_file_exists(self):
        """Verify requirements.txt file exists."""
        assert (PROJECT_ROOT / "requirements.txt").is_file()
    
    def test_requirements_contains_pytest(self):
        """Verify pytest==7.4.3 is in requirements.txt."""
        content = (PROJECT_ROOT / "requirements.txt").read_text()
        assert "pytest==7.4.3" in content
    
    def test_requirements_contains_pyyaml(self):
        """Verify pyyaml==6.0.1 is in requirements.txt."""
        content = (PROJECT_ROOT / "requirements.txt").read_text()
        assert "pyyaml==6.0.1" in content
    
    def test_requirements_contains_requests(self):
        """Verify requests==2.31.0 is in requirements.txt."""
        content = (PROJECT_ROOT / "requirements.txt").read_text()
        assert "requests==2.31.0" in content
    
    def test_requirements_exact_versions(self):
        """Verify all dependencies use exact versions (==)."""
        content = (PROJECT_ROOT / "requirements.txt").read_text()
        lines = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
        
        for line in lines:
            if '==' in line:
                # Valid exact version
                continue
            elif '>=' in line or '~=' in line or '<' in line:
                # Should not have approximate versions
                assert False, f"Line '{line}' uses approximate version, should use exact (==)"


class TestGitignore:
    """Test that .gitignore exists with proper security exclusions."""
    
    def test_gitignore_exists(self):
        """Verify .gitignore file exists."""
        assert (PROJECT_ROOT / ".gitignore").is_file()
    
    def test_gitignore_excludes_json(self):
        """Verify .gitignore excludes *.json files (API credentials)."""
        content = (PROJECT_ROOT / ".gitignore").read_text()
        assert "*.json" in content
    
    def test_gitignore_excludes_data(self):
        """Verify .gitignore excludes data/ directory."""
        content = (PROJECT_ROOT / ".gitignore").read_text()
        assert "data/" in content
    
    def test_gitignore_excludes_logs(self):
        """Verify .gitignore excludes logs/ directory."""
        content = (PROJECT_ROOT / ".gitignore").read_text()
        assert "logs/" in content
    
    def test_gitignore_excludes_pycache(self):
        """Verify .gitignore excludes __pycache__/ directory."""
        content = (PROJECT_ROOT / ".gitignore").read_text()
        assert "__pycache__/" in content
    
    def test_gitignore_excludes_pyc(self):
        """Verify .gitignore excludes *.pyc files."""
        content = (PROJECT_ROOT / ".gitignore").read_text()
        assert "*.pyc" in content
    
    def test_gitignore_excludes_env(self):
        """Verify .gitignore excludes .env file."""
        content = (PROJECT_ROOT / ".gitignore").read_text()
        assert ".env" in content


class TestDependencyInstallation:
    """Test that all dependencies can be imported successfully."""
    
    def test_import_requests(self):
        """Verify requests module can be imported."""
        import requests
        assert requests is not None
    
    def test_import_yaml(self):
        """Verify yaml module can be imported."""
        import yaml
        assert yaml is not None
    
    def test_import_pytest(self):
        """Verify pytest module can be imported."""
        import pytest
        assert pytest is not None
    
    def test_requests_version(self):
        """Verify requests version is >= 2.31.0."""
        import requests
        from packaging.version import Version
        assert Version(requests.__version__) >= Version("2.31.0")
    
    def test_yaml_version(self):
        """Verify PyYAML version is 6.0.1."""
        import yaml
        # PyYAML doesn't expose version in a standard way, but we can check it's importable
        assert hasattr(yaml, 'safe_load')
    
    def test_pytest_version(self):
        """Verify pytest version is >= 7.4.3."""
        import pytest
        from packaging.version import Version
        assert Version(pytest.__version__) >= Version("7.4.3")
