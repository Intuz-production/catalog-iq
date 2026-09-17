"""
CatalogIQ — Database Engine and Session Management

Provides SQLAlchemy engine, session factory, and base model
for all database operations.
"""

import logging
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

from app.config import settings

logger = logging.getLogger("catalogiq.database")


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session.

    Yields:
        SQLAlchemy session that auto-closes after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_competitor_price_columns() -> None:
    """Add competitor price columns introduced after initial schema."""
    inspector = inspect(engine)
    if "competitor_prices" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("competitor_prices")}
    statements: list[str] = []

    if "is_simulated" not in existing_columns:
        statements.append(
            "ALTER TABLE competitor_prices "
            "ADD COLUMN is_simulated BOOLEAN NOT NULL DEFAULT FALSE"
        )
    if "match_score" not in existing_columns:
        statements.append(
            "ALTER TABLE competitor_prices ADD COLUMN match_score FLOAT"
        )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
    logger.info("Applied competitor_prices schema updates: %s", ", ".join(statements))


def _migrate_competitor_source_enum() -> None:
    """Add new CompetitorSource enum values for PostgreSQL databases."""
    if not settings.DATABASE_URL.startswith("postgresql"):
        return

    # SQLAlchemy binds CompetitorSource by enum member name (AMAZON, EBAY, …),
    # not the lowercase .value strings — must match existing PG labels.
    new_values = ("EBAY", "TARGET")
    with engine.begin() as connection:
        for value in new_values:
            exists = connection.execute(
                text(
                    "SELECT 1 FROM pg_enum e "
                    "JOIN pg_type t ON e.enumtypid = t.oid "
                    "WHERE t.typname = 'competitorsource' AND e.enumlabel = :label"
                ),
                {"label": value},
            ).scalar()
            if not exists:
                connection.execute(
                    text(f"ALTER TYPE competitorsource ADD VALUE '{value}'")
                )
                logger.info("Added competitorsource enum value: %s", value)


def init_db() -> None:
    """Create all database tables if they do not exist.

    Called on application startup to ensure schema is ready.
    """
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    _migrate_competitor_price_columns()
    _migrate_competitor_source_enum()
    logger.info("Database tables initialized successfully.")
