from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common import common_types
from models import user_model
from config import settings
from db import get_db

password_hash = PasswordHash.recommended()
AUTH_COOKIE_NAME = "huutoapp-token"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/users/token", auto_error=False)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.access_token_expire_minutes,
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )
    return encoded_jwt


def verify_access_token(token: str) -> str | None:
    """Verify a JWT access token and return the subject (user id) if valid."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    else:
        return payload.get("sub")


async def get_access_token(
    request: Request,
    header_token: Annotated[str | None, Depends(oauth2_scheme)],
) -> str | None:
    """Resolve the JWT from the Authorization header, falling back to the cookie.

    The header is what fetch() callers (auth.js apiFetch) send. The cookie is
    what browser page navigations send, since a navigation cannot attach an
    Authorization header. Login sets both.
    """
    if header_token:
        return header_token
    return request.cookies.get(AUTH_COOKIE_NAME)


async def get_current_user(
    token: Annotated[str | None, Depends(get_access_token)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> user_model.User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = verify_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(user_model.User).where(user_model.User.id == user_id_int),
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def require_roles(*allowed_roles: str):
    """Factory that returns a dependency requiring one of the given roles."""
    async def role_checker(
        current_user: Annotated[user_model.User, Depends(get_current_user)]
    ) -> user_model.User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user
    return role_checker

require_admin = require_roles(common_types.UserRole.admin)
CurrentUser = Annotated[user_model.User, Depends(get_current_user)]
AdminUser = Annotated[CurrentUser, Depends(require_admin)]