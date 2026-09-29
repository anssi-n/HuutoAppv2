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


async def _user_from_token(
    token: str,
    db: AsyncSession,
) -> user_model.User | None:
    user_id = verify_access_token(token)
    if user_id is None:
        return None

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        return None

    result = await db.execute(
        select(user_model.User).where(user_model.User.id == user_id_int),
    )
    return result.scalars().first()


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

    user = await _user_from_token(token, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
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


class PageAuthRedirect(Exception):
    """Signalled by the guard on the admin-only HTML pages.

    Those routes are reached by plain browser navigations, which would render
    the API's JSON 401/403 body as-is. An app-level handler turns this into a
    redirect back to the UI, which then shows a sign-in prompt.
    """

    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(url)


def require_admin_page(expired_url: str = "/?auth=expired"):
    """Dependency for admin-only HTML pages; redirects instead of returning JSON."""

    async def page_guard(
        token: Annotated[str | None, Depends(get_access_token)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> user_model.User:
        user = await _user_from_token(token, db) if token else None
        if user is None:
            raise PageAuthRedirect(expired_url)
        if user.role != common_types.UserRole.admin:
            raise PageAuthRedirect("/?auth=forbidden")
        return user

    return page_guard


PageAdminUser = Annotated[user_model.User, Depends(require_admin_page())]