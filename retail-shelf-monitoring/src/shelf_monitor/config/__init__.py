"""
Configuration Package

This package provides centralized configuration management using Pydantic.
All application settings are defined in settings.py and loaded from .env file.

Usage:
    from src.shelf_monitor.config.settings import settings
    
    database_url = settings.database_url
    log_level = settings.log_level
"""

from .settings import settings

__all__ = ["settings"]
