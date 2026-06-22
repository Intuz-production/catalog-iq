"""
CatalogIQ — Application Settings

Centralized configuration loaded from environment variables.
All secrets and configurable values are managed via .env file.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    # Required — Groq API
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # Required — Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Optional — Server
    FASTAPI_HOST: str = os.getenv("FASTAPI_HOST", "0.0.0.0")
    FASTAPI_PORT: int = int(os.getenv("FASTAPI_PORT", "8000"))

    # Optional — Scraping
    SCRAPE_INTERVAL_HOURS: int = int(os.getenv("SCRAPE_INTERVAL_HOURS", "6"))

    # Optional — Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> None:
        """Validate all required settings are configured.

        Raises:
            EnvironmentError: If any required variables are missing.
        """
        missing: list[str] = []
        if not cls.GROQ_API_KEY:
            missing.append("GROQ_API_KEY (get from https://console.groq.com/keys)")
        if not cls.DATABASE_URL:
            missing.append("DATABASE_URL (PostgreSQL connection string)")
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables:\n"
                + "\n".join(f"  - {var}" for var in missing)
                + "\n\nPlease copy .env.example to .env and fill in the values."
            )


settings = Settings()


def setup_logging() -> logging.Logger:
    """Configure application-wide logging.

    Returns:
        Configured root logger for the application.
    """
    logger = logging.getLogger("catalogiq")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
