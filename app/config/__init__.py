"""
CatalogIQ — Application Settings

Centralized configuration loaded from environment variables.
All secrets and configurable values are managed via .env file.
"""

import os
import logging
from functools import lru_cache
from dotenv import load_dotenv

from app.config.marketplaces import MarketplaceConfig, load_marketplace_settings

load_dotenv()


def _env_bool(key: str, default: str = "false") -> bool:
    """Parse a boolean environment variable."""
    return os.getenv(key, default).lower() in ("true", "1", "yes")


def _env_float(key: str, default: str) -> float:
    """Parse a float environment variable."""
    return float(os.getenv(key, default))


def _env_int(key: str, default: str) -> int:
    """Parse an integer environment variable."""
    return int(os.getenv(key, default))


class Settings:
    """Application settings loaded from environment variables."""

    # Required — Groq API
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    GROQ_TEMPERATURE: float = _env_float("GROQ_TEMPERATURE", "0.7")
    GROQ_SEO_TEMPERATURE: float = _env_float("GROQ_SEO_TEMPERATURE", "0.3")
    GROQ_MAX_TOKENS: int = _env_int("GROQ_MAX_TOKENS", "500")
    GROQ_SEO_MAX_TOKENS: int = _env_int("GROQ_SEO_MAX_TOKENS", "200")
    GROQ_MAX_RETRIES: int = _env_int("GROQ_MAX_RETRIES", "3")
    GROQ_RETRY_DELAY_SECONDS: float = _env_float("GROQ_RETRY_DELAY_SECONDS", "1")
    GROQ_BATCH_DELAY_MS: int = _env_int("GROQ_BATCH_DELAY_MS", "250")
    GROQ_MIN_DESCRIPTION_WORDS: int = _env_int("GROQ_MIN_DESCRIPTION_WORDS", "20")
    GROQ_MAX_COMPLETION_TOKENS: int = _env_int("GROQ_MAX_COMPLETION_TOKENS", "2048")
    GROQ_REASONING_EFFORT: str = os.getenv("GROQ_REASONING_EFFORT", "low")
    GROQ_REASONING_FORMAT: str = os.getenv("GROQ_REASONING_FORMAT", "hidden")
    SEO_TITLE_MAX_LENGTH: int = _env_int("SEO_TITLE_MAX_LENGTH", "60")

    # Required — Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DB_POOL_SIZE: int = _env_int("DB_POOL_SIZE", "10")
    DB_MAX_OVERFLOW: int = _env_int("DB_MAX_OVERFLOW", "20")
    DB_ECHO: bool = _env_bool("DB_ECHO", "false")

    # Server
    FASTAPI_HOST: str = os.getenv("FASTAPI_HOST", "0.0.0.0")
    FASTAPI_PORT: int = _env_int("FASTAPI_PORT", "8000")
    FASTAPI_RELOAD: bool = _env_bool("FASTAPI_RELOAD", "true")
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:3000",
    )

    # Scraping
    SCRAPE_INTERVAL_HOURS: int = _env_int("SCRAPE_INTERVAL_HOURS", "6")
    SCRAPE_REQUEST_TIMEOUT: int = _env_int("SCRAPE_REQUEST_TIMEOUT", "15")
    SCRAPE_DELAY_MS: int = _env_int("SCRAPE_DELAY_MS", "1500")
    SCRAPE_MAX_RETRIES: int = _env_int("SCRAPE_MAX_RETRIES", "2")
    SCRAPE_RETRY_BACKOFF_SEC: int = _env_int("SCRAPE_RETRY_BACKOFF_SEC", "2")

    # Competitor alerts
    USD_INR_EXCHANGE_RATE: float = _env_float("USD_INR_EXCHANGE_RATE", "83.0")
    ALERT_UNDERCUT_THRESHOLD_PCT: float = _env_float("ALERT_UNDERCUT_THRESHOLD_PCT", "5")
    ALERT_PRICE_CHANGE_THRESHOLD_PCT: float = _env_float(
        "ALERT_PRICE_CHANGE_THRESHOLD_PCT", "10"
    )

    # Authentication
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES: int = _env_int("JWT_EXPIRE_MINUTES", "1440")
    DEFAULT_ADMIN_EMAIL: str = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@catalogiq.local")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
    DEFAULT_ADMIN_NAME: str = os.getenv("DEFAULT_ADMIN_NAME", "Admin")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def cors_origins(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def scrape_region(self) -> str:
        """Resolved competitor monitoring region (us or in)."""
        return get_marketplace_settings()[0]

    @property
    def scrape_source_ids(self) -> list[str]:
        """Enabled competitor marketplace source IDs from env."""
        return get_marketplace_settings()[1]

    @property
    def marketplaces(self) -> dict[str, MarketplaceConfig]:
        """Enabled marketplace configs keyed by source ID."""
        return get_marketplace_settings()[2]

    @property
    def docs_url(self) -> str:
        """Build the API documentation URL for startup logging."""
        docs_host = "localhost" if self.FASTAPI_HOST == "0.0.0.0" else self.FASTAPI_HOST
        return f"http://{docs_host}:{self.FASTAPI_PORT}/docs"

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


@lru_cache(maxsize=1)
def get_marketplace_settings() -> tuple[str, list[str], dict[str, MarketplaceConfig]]:
    """Load and cache marketplace settings from environment variables."""
    return load_marketplace_settings()


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
