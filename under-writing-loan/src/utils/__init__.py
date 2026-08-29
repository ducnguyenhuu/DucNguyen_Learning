"""
Utility modules for the underwriting system.

This package contains shared utilities:
- config: Configuration management
- validation_engine: Rule-based validation engine
- helpers: Common helper functions
"""

from .config import config
from .validation_engine import ValidationRuleEngine, RuleSeverity
from .helpers import *

__all__ = [
    "config",
    "ValidationRuleEngine",
    "RuleSeverity",
]
