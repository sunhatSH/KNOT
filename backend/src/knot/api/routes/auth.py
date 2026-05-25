"""Authentication API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from knot.api.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from knot.core.database import get_session
from knot.core.models import User, UserRole
from knot.core.repository import UserRepository

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
_user_repo = UserRepository()


@router.post("/register")
async def register(
    username: str,
    password: str,
    email: str = "",
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Register a new user."""
    # Check if user exists
    existing = await _user_repo.get_by_username(session, username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(username=username, email=email, role=UserRole.USER)
    password_hash = hash_password(password)
    await _user_repo.save(session, user, password_hash)
    return {"id": user.id, "username": user.username, "message": "User registered"}


@router.post("/login")
async def login(
    username: str,
    password: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Login and get JWT token."""
    user_data = await _user_repo.get_by_username(session, username)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user, password_hash = user_data
    if not verify_password(password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    token = create_access_token({"sub": user.username, "role": user.role.value})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.model_dump(),
    }


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Get current user info."""
    return current_user
