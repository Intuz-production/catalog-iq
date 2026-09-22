"""
CatalogIQ — Auth Dependencies

FastAPI dependencies for authenticated route access.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import User
from app.services import user_service
from app.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from a JWT bearer token.

    Args:
        token: JWT access token from Authorization header.
        db: Database session.

    Returns:
        Authenticated user.

    Raises:
        HTTPException: If the token is invalid or the user is inactive.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    email = decode_access_token(token)
    if not email:
        raise credentials_error

    user = user_service.get_user_by_email(db, email)
    if not user or not user.is_active:
        raise credentials_error

    return user
