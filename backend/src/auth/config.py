"""Runtime configuration for Azure Entra access-token validation."""

from __future__ import annotations

from dataclasses import dataclass
import os


_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AuthSettings:
    """Configuration values required to validate Entra-issued JWTs."""

    enabled: bool
    tenant_id: str | None
    client_id: str | None
    audience: str | None
    required_scope: str | None
    allowed_issuers: tuple[str, ...]

    @property
    def issuer(self) -> str | None:
        if self.tenant_id is None:
            return None
        return f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"

    @property
    def jwks_url(self) -> str | None:
        if self.tenant_id is None:
            return None
        return f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE_VALUES


def load_auth_settings() -> AuthSettings:
    """Load and validate auth settings from environment variables."""

    enabled = _read_bool_env("WSAA_AUTH_ENABLED", default=True)
    tenant_id = os.getenv("WSAA_AUTH_TENANT_ID")
    client_id = os.getenv("WSAA_AUTH_CLIENT_ID")
    audience = os.getenv("WSAA_AUTH_AUDIENCE")
    required_scope = os.getenv("WSAA_AUTH_REQUIRED_SCOPE")
    allowed_issuers_raw = os.getenv("WSAA_AUTH_ALLOWED_ISSUERS", "")

    # Fallback to client_id when audience is not supplied explicitly.
    effective_audience = audience or client_id
    default_allowed_issuers: tuple[str, ...] = ()
    if tenant_id:
        default_allowed_issuers = (
            f"https://login.microsoftonline.com/{tenant_id}/v2.0",
            f"https://sts.windows.net/{tenant_id}/",
        )

    configured_allowed_issuers = tuple(
        issuer.strip() for issuer in allowed_issuers_raw.split(",") if issuer.strip()
    )
    effective_allowed_issuers = configured_allowed_issuers or default_allowed_issuers

    settings = AuthSettings(
        enabled=enabled,
        tenant_id=tenant_id,
        client_id=client_id,
        audience=effective_audience,
        required_scope=required_scope,
        allowed_issuers=effective_allowed_issuers,
    )

    if not settings.enabled:
        return settings

    missing = []
    if settings.tenant_id is None:
        missing.append("WSAA_AUTH_TENANT_ID")
    if settings.client_id is None:
        missing.append("WSAA_AUTH_CLIENT_ID")
    if settings.audience is None:
        missing.append("WSAA_AUTH_AUDIENCE or WSAA_AUTH_CLIENT_ID")
    if not settings.allowed_issuers:
        missing.append("WSAA_AUTH_ALLOWED_ISSUERS or WSAA_AUTH_TENANT_ID")

    if missing:
        missing_names = ", ".join(missing)
        raise ValueError(f"Missing required Entra auth settings: {missing_names}")

    return settings

