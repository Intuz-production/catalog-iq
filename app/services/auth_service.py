"""
CatalogIQ — Auth Service

Business logic for user login and token issuance.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.schemas import TokenResponse
from app.services import user_service
from app.utils.security import create_access_token

logger = logging.getLogger("catalogiq.services.auth")


def login_user(db: Session, email: str, password: str) -> Optional[TokenResponse]:
    """Authenticate a user and return a JWT access token.

    Args:
        db: Database session.
        email: Login email address.
        password: Plain-text password.

    Returns:
        Token response when credentials are valid, otherwise None.
    """
    user = user_service.authenticate_user(db, email, password)
    if not user:
        logger.warning("Failed login attempt for email: %s", email)
        return None

    access_token = create_access_token(user.email)
    logger.info("User logged in: %s", user.email)
    return TokenResponse(access_token=access_token)
