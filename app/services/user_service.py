"""
CatalogIQ — User Service

Database operations for user accounts and authentication.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.schemas import User, UserCreate
from app.utils.security import hash_password, verify_password

logger = logging.getLogger("catalogiq.services.user")


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Fetch a user by email address.

    Args:
        db: Database session.
        email: User email.

    Returns:
        User if found, otherwise None.
    """
    return db.query(User).filter(User.email == email.lower()).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Fetch a user by primary key.

    Args:
        db: Database session.
        user_id: User ID.

    Returns:
        User if found, otherwise None.
    """
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, user_data: UserCreate) -> User:
    """Create a new user with a hashed password.

    Args:
        db: Database session.
        user_data: User creation payload.

    Returns:
        Newly created user.
    """
    user = User(
        email=user_data.email.lower().strip(),
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        is_superuser=user_data.is_superuser,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Created user account: %s", user.email)
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Validate user credentials.

    Args:
        db: Database session.
        email: Login email.
        password: Plain-text password.

    Returns:
        User if credentials are valid and account is active, otherwise None.
    """
    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
