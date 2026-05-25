"""JWT authentication and authorization for KNOT API."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from knot.core.config import settings
from knot.core.database import get_session
from knot.core.models import User, UserRole
from knot.core.repository import UserRepository

logger = logging.getLogger(__name__)

security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_user_repo = UserRepository()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> User:
    """FastAPI dependency: extract and validate the current user from JWT."""
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_data = await _user_repo.get_by_username(session, username)
    if user_data is None:
        raise HTTPException(status_code=401, detail="User not found")
    user, _ = user_data
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User inactive")
    return user


async def require_role(required_role: UserRole):
    """Dependency factory: require a specific role to access an endpoint."""

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        role_rank = {"admin": 3, "user": 2, "viewer": 1}
        if role_rank.get(current_user.role.value, 0) < role_rank.get(required_role.value, 0):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return role_checker


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Like get_current_user but returns None instead of 401 if no token."""
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, session)  # type: ignore
    except HTTPException:
        return None
