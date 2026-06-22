"""
CatalogIQ — Application Settings (re-export)

Import convenience: from app.config.settings import settings
"""

from app.config import settings, Settings, setup_logging

__all__ = ["settings", "Settings", "setup_logging"]
