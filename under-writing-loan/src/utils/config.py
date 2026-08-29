"""
Configuration management for the loan underwriting system.

Loads environment variables and provides centralized access to Azure credentials
and service endpoints.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """
    Central configuration class for all services.
    
    Loads credentials from environment variables with validation.
    """
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    AZURE_OPENAI_DEPLOYMENT_GPT4: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT4", "gpt-4o")
    AZURE_OPENAI_DEPLOYMENT_EMBEDDING: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_EMBEDDING", "text-embedding-ada-002")
    
    # Azure Document Intelligence Configuration
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
    
    # Azure AI Search Configuration
    AZURE_SEARCH_ENDPOINT: str = os.getenv("AZURE_SEARCH_ENDPOINT", "")
    AZURE_SEARCH_ADMIN_KEY: str = os.getenv("AZURE_SEARCH_ADMIN_KEY", "")
    AZURE_SEARCH_INDEX_NAME: str = os.getenv("AZURE_SEARCH_INDEX_NAME", "lending-policies-index")
    
    # MLflow Configuration
    MLFLOW_TRACKING_URI: str = os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")
    
    # MCP Server Configuration
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
    
    # Project Paths
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    APPLICATIONS_DIR: Path = DATA_DIR / "applications"
    EXTRACTED_DIR: Path = DATA_DIR / "extracted"
    POLICIES_DIR: Path = DATA_DIR / "policies"
    
    # Database Paths
    CREDIT_DB_PATH: Path = DATA_DIR / "mock_credit_bureau.db"
    APP_DB_PATH: Path = DATA_DIR / "database.sqlite"
    
    @classmethod
    def validate_azure_openai(cls) -> bool:
        """
        Validate Azure OpenAI configuration.
        
        Returns:
            True if all required credentials are present
        """
        return bool(
            cls.AZURE_OPENAI_API_KEY 
            and cls.AZURE_OPENAI_ENDPOINT
            and cls.AZURE_OPENAI_DEPLOYMENT_GPT4
        )
    
    @classmethod
    def validate_document_intelligence(cls) -> bool:
        """
        Validate Document Intelligence configuration.
        
        Returns:
            True if all required credentials are present
        """
        return bool(
            cls.AZURE_DOCUMENT_INTELLIGENCE_KEY
            and cls.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
        )
    
    @classmethod
    def validate_ai_search(cls) -> bool:
        """
        Validate AI Search configuration.
        
        Returns:
            True if all required credentials are present
        """
        return bool(
            cls.AZURE_SEARCH_ENDPOINT
            and cls.AZURE_SEARCH_ADMIN_KEY
        )
    
    @classmethod
    def validate_all(cls) -> dict[str, bool]:
        """
        Validate all service configurations.
        
        Returns:
            Dictionary with validation results for each service
        """
        return {
            "azure_openai": cls.validate_azure_openai(),
            "document_intelligence": cls.validate_document_intelligence(),
            "ai_search": cls.validate_ai_search(),
        }
    
    @classmethod
    def get_missing_credentials(cls) -> list[str]:
        """
        Get list of missing credential environment variables.
        
        Returns:
            List of missing environment variable names
        """
        missing = []
        
        if not cls.AZURE_OPENAI_API_KEY:
            missing.append("AZURE_OPENAI_API_KEY")
        if not cls.AZURE_OPENAI_ENDPOINT:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not cls.AZURE_DOCUMENT_INTELLIGENCE_KEY:
            missing.append("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        if not cls.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT:
            missing.append("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        if not cls.AZURE_SEARCH_ENDPOINT:
            missing.append("AZURE_SEARCH_ENDPOINT")
        if not cls.AZURE_SEARCH_ADMIN_KEY:
            missing.append("AZURE_SEARCH_ADMIN_KEY")
        
        return missing


# Convenience instance
config = Config()


def check_credentials() -> None:
    """
    Check if all required credentials are configured.
    
    Raises:
        ValueError: If any required credentials are missing
    """
    missing = Config.get_missing_credentials()
    
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Please copy .env.example to .env and fill in your Azure credentials."
        )
