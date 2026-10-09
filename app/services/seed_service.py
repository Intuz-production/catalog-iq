"""
CatalogIQ — Database Seeder Service

Seeds default application data on startup.
"""

import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.models.schemas import UserCreate
from app.services import user_service

logger = logging.getLogger("catalogiq.services.seed")


def seed_default_user(db: Session) -> None:
    """Create the default admin user if it does not already exist.

    Args:
        db: Database session.
    """
    email = settings.DEFAULT_ADMIN_EMAIL.lower().strip()
    existing = user_service.get_user_by_email(db, email)
    if existing:
        logger.info("Default admin user already exists: %s", email)
        return

    user_service.create_user(
        db,
        UserCreate(
            email=email,
            password=settings.DEFAULT_ADMIN_PASSWORD,
            full_name=settings.DEFAULT_ADMIN_NAME,
            is_superuser=True,
        ),
    )
    logger.info("Seeded default admin user: %s", email)
