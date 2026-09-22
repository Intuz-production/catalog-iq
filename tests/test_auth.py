"""
CatalogIQ — Authentication Tests

Tests for password hashing and JWT token helpers.
"""

from app.utils.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordSecurity:
    """Tests for password hashing and verification."""

    def test_hash_and_verify_password(self):
        hashed = hash_password("admin123")
        assert hashed != "admin123"
        assert verify_password("admin123", hashed) is True

    def test_verify_password_rejects_invalid_value(self):
        hashed = hash_password("admin123")
        assert verify_password("wrong-password", hashed) is False


class TestJwtSecurity:
    """Tests for JWT creation and decoding."""

    def test_create_and_decode_access_token(self):
        token = create_access_token("admin@catalogiq.local")
        assert decode_access_token(token) == "admin@catalogiq.local"

    def test_decode_access_token_rejects_invalid_token(self):
        assert decode_access_token("not-a-valid-token") is None
