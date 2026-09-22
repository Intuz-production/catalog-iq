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


def _migrate_data_issue_review_columns() -> None:
    """Add review columns on data_issues introduced for AI rewrite review."""
    inspector = inspect(engine)
    if "data_issues" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("data_issues")}
    statements: list[str] = []

    if "suggested_value" not in existing_columns:
        statements.append("ALTER TABLE data_issues ADD COLUMN suggested_value TEXT")
    if "suggestion_source" not in existing_columns:
        statements.append("ALTER TABLE data_issues ADD COLUMN suggestion_source VARCHAR(20)")
    if "review_status" not in existing_columns:
        statements.append(
            "ALTER TABLE data_issues ADD COLUMN review_status VARCHAR(20) DEFAULT 'pending'"
        )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
    logger.info("Applied data_issues schema updates: %s", ", ".join(statements))


def _migrate_ingestion_job_ai_columns() -> None:
    """Add AI analysis progress columns on ingestion_jobs."""
    inspector = inspect(engine)
    if "ingestion_jobs" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("ingestion_jobs")}
    statements: list[str] = []
    if "ai_analyzed_rows" not in existing_columns:
        statements.append(
            "ALTER TABLE ingestion_jobs ADD COLUMN ai_analyzed_rows INTEGER DEFAULT 0"
        )
    if "ai_error_count" not in existing_columns:
        statements.append(
            "ALTER TABLE ingestion_jobs ADD COLUMN ai_error_count INTEGER DEFAULT 0"
        )
    if "skipped_rows" not in existing_columns:
        statements.append(
            "ALTER TABLE ingestion_jobs ADD COLUMN skipped_rows INTEGER DEFAULT 0"
        )
    if "skip_summary" not in existing_columns:
        statements.append(
            "ALTER TABLE ingestion_jobs ADD COLUMN skip_summary TEXT"
        )
    if "group_name" not in existing_columns:
        statements.append(
            "ALTER TABLE ingestion_jobs ADD COLUMN group_name VARCHAR(255)"
        )

    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
        logger.info("Applied ingestion_jobs schema updates: %s", ", ".join(statements))

    # Backfill group_name from filename for rows created before the column existed.
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE ingestion_jobs SET group_name = filename "
                "WHERE group_name IS NULL OR TRIM(group_name) = ''"
            )
        )


def _migrate_issue_type_enum() -> None:
    """Add later IssueType values for PostgreSQL native enums."""
    if not settings.DATABASE_URL.startswith("postgresql"):
        return

    labels = (
        "AI_INFERRED",
        "ai_inferred",
        "ATTRIBUTE_NOT_IN_COPY",
        "attribute_not_in_copy",
    )
    with engine.begin() as connection:
        for label in labels:
            exists = connection.execute(
                text(
                    "SELECT 1 FROM pg_enum e "
                    "JOIN pg_type t ON e.enumtypid = t.oid "
                    "WHERE t.typname = 'issuetype' AND e.enumlabel = :label"
                ),
                {"label": label},
            ).scalar()
            if exists:
                continue
            type_exists = connection.execute(
                text("SELECT 1 FROM pg_type WHERE typname = 'issuetype'")
            ).scalar()
            if not type_exists:
                return
            connection.execute(text(f"ALTER TYPE issuetype ADD VALUE '{label}'"))
            logger.info("Added issuetype enum value: %s", label)


def _migrate_product_ingestion_job_column() -> None:
    """Add last_ingestion_job_id so products can be listed by uploaded file."""
    inspector = inspect(engine)
    if "products" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("products")}
    if "last_ingestion_job_id" in existing_columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE products ADD COLUMN last_ingestion_job_id INTEGER")
        )
    logger.info("Applied products schema update: last_ingestion_job_id")


def _migrate_product_ai_analysis_status_column() -> None:
    """Add ai_analysis_status for per-row AI progress during ingest."""
    inspector = inspect(engine)
    if "products" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("products")}
    if "ai_analysis_status" in existing_columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE products ADD COLUMN ai_analysis_status VARCHAR(20)")
        )
    logger.info("Applied products schema update: ai_analysis_status")


def init_db() -> None:
    """Create all database tables if they do not exist.

    Called on application startup to ensure schema is ready.
    """
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    _migrate_competitor_price_columns()
    _migrate_competitor_source_enum()
    _migrate_data_issue_review_columns()
    _migrate_ingestion_job_ai_columns()
    _migrate_product_ingestion_job_column()
    _migrate_product_ai_analysis_status_column()
    _migrate_issue_type_enum()
    logger.info("Database tables initialized successfully.")
