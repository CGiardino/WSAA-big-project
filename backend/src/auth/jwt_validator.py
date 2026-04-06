"""JWT validation utilities for Azure Entra bearer tokens."""

from __future__ import annotations

from typing import Any

import jwt
from jwt import PyJWKClient

from src.auth.config import AuthSettings


class JwtValidator:
    """Validates Azure Entra JWT access tokens with JWKS-backed signatures."""

    def __init__(self, settings: AuthSettings) -> None:
        self._settings = settings
        self._jwks_client = PyJWKClient(settings.jwks_url or "")
        self._allowed_issuers = {
            issuer.strip().rstrip("/")
            for issuer in settings.allowed_issuers
            if issuer.strip()
        }

    def validate_access_token(self, token: str) -> dict[str, Any]:
        """Validate signature/claims and return decoded JWT payload."""

        signing_key = self._jwks_client.get_signing_key_from_jwt(token)

        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self._settings.audience,
            options={"require": ["exp", "iat", "iss", "aud"], "verify_iss": False},
        )

        token_issuer = str(claims.get("iss", "")).strip().rstrip("/")
        if token_issuer not in self._allowed_issuers:
            raise jwt.InvalidIssuerError(
                f"Invalid issuer '{token_issuer}'. Allowed issuers: {sorted(self._allowed_issuers)}"
            )

        required_scope = self._settings.required_scope
        if required_scope:
            scopes = str(claims.get("scp", "")).split()
            roles = claims.get("roles", [])
            if required_scope not in scopes and required_scope not in roles:
                raise jwt.InvalidTokenError(
                    f"Token does not contain required scope/role '{required_scope}'"
                )

        return claims

