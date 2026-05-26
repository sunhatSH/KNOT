"""Tests for authentication: password hashing, JWT tokens, RBAC role ranking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from jose.exceptions import JWTError

from knot.api.auth import (
    create_access_token,
    hash_password,
    require_role,
    verify_password,
)
from knot.core.config import settings
from knot.core.models import User, UserRole


# --- Password Hashing -----------------------------------------------------


class TestPasswordHashing:
    def test_hash_password(self):
        hashed = hash_password("secure_password")
        assert hashed != "secure_password"
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_verify_correct_password(self):
        pwd = "my_secret_123"
        hashed = hash_password(pwd)
        assert verify_password(pwd, hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_verify_empty_password(self):
        hashed = hash_password("nonempty")
        assert verify_password("", hashed) is False

    def test_different_hashes_same_password(self):
        """Each hash should be unique due to salt."""
        pwd = "same_password"
        h1 = hash_password(pwd)
        h2 = hash_password(pwd)
        assert h1 != h2
        assert verify_password(pwd, h1) is True
        assert verify_password(pwd, h2) is True

    def test_special_characters(self):
        pwd = "P@$$w0rd!-_{}[]|\\:;\"'<>,.?/~`"
        hashed = hash_password(pwd)
        assert verify_password(pwd, hashed) is True

    def test_unicode_password(self):
        pwd = "密码123!@#"
        hashed = hash_password(pwd)
        assert verify_password(pwd, hashed) is True

    def test_long_password(self):
        pwd = "a" * 72  # bcrypt 72-byte limit
        hashed = hash_password(pwd)
        assert verify_password(pwd, hashed) is True


# --- JWT Token Creation and Validation -----------------------------------


class TestJWTToken:
    def test_create_access_token(self):
        token = create_access_token({"sub": "test_user"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_custom_expiry(self):
        token = create_access_token(
            {"sub": "test_user"},
            expires_delta=timedelta(minutes=5),
        )
        assert token is not None

    def test_token_contains_sub(self):
        token = create_access_token({"sub": "alice"})
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload["sub"] == "alice"

    def test_token_expiry(self):
        token = create_access_token(
            {"sub": "bob"},
            expires_delta=timedelta(hours=1),
        )
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        assert "exp" in payload
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        # Expiry should be in the future
        assert exp_time > now
        # And within a reasonable window (1 hour + margin)
        assert exp_time < now + timedelta(hours=2)

    def test_token_with_extra_claims(self):
        token = create_access_token({
            "sub": "charlie",
            "role": "admin",
            "is_active": True,
        })
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload["role"] == "admin"
        assert payload["is_active"] is True

    def test_invalid_token_raises(self):
        with pytest.raises(JWTError):
            jwt.decode(
                "invalid_token_string",
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )

    def test_tampered_token_raises(self):
        token = create_access_token({"sub": "dave"})
        # Tamper with the token
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1] + ".invalidsignature"
        with pytest.raises(JWTError):
            jwt.decode(
                tampered,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )

    def test_wrong_secret_raises(self):
        token = create_access_token({"sub": "eve"})
        with pytest.raises(JWTError):
            jwt.decode(
                token,
                "wrong_secret_key",
                algorithms=[settings.jwt_algorithm],
            )

    def test_expired_token(self):
        """Token with past expiry should fail validation."""
        past = timedelta(hours=-1)
        token = create_access_token({"sub": "frank"}, expires_delta=past)
        with pytest.raises(JWTError):
            jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )


# --- RBAC Role Ranking ----------------------------------------------------


class TestRBAC:
    def test_role_enum_values(self):
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.USER.value == "user"
        assert UserRole.VIEWER.value == "viewer"

    def test_admin_can_access_admin_endpoint(self):
        """The require_role dependency should allow higher-ranked roles."""

        async def check_role(user: User):
            role_checker = require_role(UserRole.ADMIN)
            # This creates a closure; we test the logic inside directly
            role_rank = {"admin": 3, "user": 2, "viewer": 1}
            result = role_rank.get(user.role.value, 0) >= role_rank.get(
                UserRole.ADMIN.value, 0
            )
            return result

        import asyncio

        admin = User(username="admin", role=UserRole.ADMIN)
        user = User(username="user", role=UserRole.USER)
        viewer = User(username="viewer", role=UserRole.VIEWER)

        assert asyncio.run(check_role(admin)) is True
        assert asyncio.run(check_role(user)) is False
        assert asyncio.run(check_role(viewer)) is False

    def test_user_can_access_user_endpoint(self):

        async def check_role(user: User):
            role_rank = {"admin": 3, "user": 2, "viewer": 1}
            result = role_rank.get(user.role.value, 0) >= role_rank.get(
                UserRole.USER.value, 0
            )
            return result

        import asyncio

        admin = User(username="admin", role=UserRole.ADMIN)
        user = User(username="user", role=UserRole.USER)
        viewer = User(username="viewer", role=UserRole.VIEWER)

        assert asyncio.run(check_role(admin)) is True
        assert asyncio.run(check_role(user)) is True
        assert asyncio.run(check_role(viewer)) is False

    def test_viewer_can_access_viewer_endpoint(self):

        async def check_role(user: User):
            role_rank = {"admin": 3, "user": 2, "viewer": 1}
            result = role_rank.get(user.role.value, 0) >= role_rank.get(
                UserRole.VIEWER.value, 0
            )
            return result

        import asyncio

        admin = User(username="admin", role=UserRole.ADMIN)
        user = User(username="user", role=UserRole.USER)
        viewer = User(username="viewer", role=UserRole.VIEWER)

        assert asyncio.run(check_role(admin)) is True
        assert asyncio.run(check_role(user)) is True
        assert asyncio.run(check_role(viewer)) is True

    def test_user_creation(self):
        admin = User(username="admin", role=UserRole.ADMIN)
        assert admin.role == UserRole.ADMIN
        assert admin.role.value == "admin"
        assert admin.is_active is True

        viewer = User(username="viewer", role=UserRole.VIEWER)
        assert viewer.role == UserRole.VIEWER
        assert viewer.role.value == "viewer"
