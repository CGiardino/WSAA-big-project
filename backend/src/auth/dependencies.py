"""FastAPI auth dependencies for protecting API endpoints."""

from __future__ import annotations

from typing import Any

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.config import load_auth_settings
from src.auth.jwt_validator import JwtValidator

_settings = load_auth_settings()
_bearer = HTTPBearer(auto_error=False)
_validator = JwtValidator(_settings) if _settings.enabled else None


def auth_is_enabled() -> bool:
    """Return whether bearer-token auth is enabled for this runtime."""

    return _settings.enabled


def require_access_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> dict[str, Any] | None:
    """Validate bearer token and return claims when auth is enabled."""

    if not _settings.enabled:
        return None

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        assert _validator is not None
        token = str(credentials.credentials)
        return _validator.validate_access_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid access token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


