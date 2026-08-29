"""
Application Settings - Centralized Configuration Management

This module defines all application settings using Pydantic BaseSettings.
Settings are loaded from .env file and can be overridden by environment variables.

Benefits:
- Type safety: Automatic type conversion and validation
- Single source of truth: All settings in one place
- Environment-specific configs: Easy to switch between dev/test/prod
- IDE support: Autocomplete and type hints
- Testability: Easy to override settings in tests

Usage:
    from src.shelf_monitor.config.settings import settings
    
    # Access settings
    db_url = settings.database_url
    threshold = settings.confidence_threshold
    
    # Override in tests
    test_settings = Settings(database_url="sqlite:///:memory:")

Related:
- Environment file: .env (not committed to Git)
- Template: .env.example (committed to Git)
"""

from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from .env file.
    
    All settings have defaults for development.
    Override in .env for different environments.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ========================================================================
    # Database Configuration
    # ========================================================================
    
    database_url: str = Field(
        default="sqlite:///data/retail_shelf_monitoring.db",
        description="Database connection URL (SQLite, PostgreSQL, etc.)"
    )
    
    # ========================================================================
    # API Server Configuration
    # ========================================================================
    
    api_title: str = Field(
        default="Retail Shelf Monitoring API",
        description="API title shown in OpenAPI docs"
    )
    
    api_version: str = Field(
        default="1.0.0",
        description="API version"
    )
    
    api_host: str = Field(
        default="127.0.0.1",
        description="API server host"
    )
    
    api_port: int = Field(
        default=8000,
        description="API server port"
    )
    
    api_reload: bool = Field(
        default=True,
        description="Enable auto-reload for development"
    )
    
    cors_origins: str = Field(
        default="*",
        description="Allowed CORS origins (comma-separated or JSON array)"
    )
    
    # ========================================================================
    # ML Model Configuration
    # ========================================================================
    
    yolo_model_path: str = Field(
        default="models/yolo_sku110k_best.pt",
        description="Path to trained YOLO model checkpoint"
    )
    
    confidence_threshold: float = Field(
        default=0.5,
        description="Minimum confidence score for detections (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    
    nms_threshold: float = Field(
        default=0.4,
        description="Non-maximum suppression threshold (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    
    max_detections_per_image: int = Field(
        default=100,
        description="Maximum number of detections per image",
        ge=1
    )
    
    # ========================================================================
    # Challenge 1: Out-of-Stock Detection
    # ========================================================================
    
    min_gap_width: int = Field(
        default=100,
        description="Minimum gap width in pixels to consider as out-of-stock",
        ge=10
    )
    
    gap_detection_threshold: float = Field(
        default=0.3,
        description="Threshold for gap detection sensitivity (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    
    # ========================================================================
    # Challenge 2: Object Counting
    # ========================================================================
    
    min_object_confidence: float = Field(
        default=0.5,
        description="Minimum confidence for counting objects (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    
    # ========================================================================
    # Image Processing
    # ========================================================================
    
    max_image_size: int = Field(
        default=2048,
        description="Maximum image dimension (width or height) in pixels",
        ge=640
    )
    
    image_size: int = Field(
        default=640,
        description="YOLO input image size (640, 1280, etc.)",
        ge=320
    )
    
    allowed_image_types: List[str] = Field(
        default=["image/jpeg", "image/png", "image/jpg"],
        description="Allowed image MIME types for upload"
    )
    
    # ========================================================================
    # File Paths
    # ========================================================================
    
    data_dir: str = Field(
        default="data",
        description="Root data directory"
    )
    
    models_dir: str = Field(
        default="models",
        description="Directory for trained models"
    )
    
    upload_dir: str = Field(
        default="data/uploads",
        description="Directory for uploaded images"
    )
    
    # ========================================================================
    # Logging Configuration
    # ========================================================================
    
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    
    log_file: str = Field(
        default="logs/app.log",
        description="Log file path"
    )
    
    log_sql_queries: bool = Field(
        default=False,
        description="Enable SQL query logging (verbose, for debugging)"
    )
    
    # ========================================================================
    # Application Settings
    # ========================================================================
    
    environment: str = Field(
        default="development",
        description="Application environment (development, production, testing)"
    )
    
    # ========================================================================
    # Validators
    # ========================================================================
    
    @field_validator("log_level")
    def validate_log_level(cls, v):
        """Ensure log level is valid."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v.upper()
    
    @field_validator("environment")
    def validate_environment(cls, v):
        """Ensure environment is valid."""
        allowed = ["development", "production", "testing"]
        if v.lower() not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v.lower()
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, list):
            return ",".join(v)  # Convert list to comma-separated string
        return v  # Keep as string
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @field_validator("image_size")
    def validate_image_size(cls, v):
        """Ensure image size is valid for YOLO (multiple of 32)."""
        if v % 32 != 0:
            raise ValueError("image_size must be a multiple of 32 (e.g., 640, 1280)")
        return v


# ============================================================================
# Global Settings Instance
# ============================================================================

# Create global settings instance that loads from .env
# This is imported by other modules: from config.settings import settings
settings = Settings()


# ============================================================================
# Helper Functions
# ============================================================================

def get_settings() -> Settings:
    """
    Get settings instance.
    
    Useful for dependency injection in FastAPI:
        @app.get("/config")
        def get_config(settings: Settings = Depends(get_settings)):
            return {"environment": settings.environment}
    
    Returns:
        Settings: Application settings instance
    """
    return settings


def reload_settings() -> Settings:
    """
    Reload settings from .env file.
    
    Useful for testing or reloading config without restarting app.
    
    Returns:
        Settings: New settings instance with reloaded values
    """
    global settings
    settings = Settings()
    return settings
