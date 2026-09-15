from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import os


TEST_CAPABILITY = "ss_test_redacted"


class AuthenticationError(Exception):
    """Raised when a capability is missing, invalid, or insufficient."""


@dataclass(frozen=True)
class Principal:
    key_id: str
    tenant_id: str
    environment: str
    scopes: frozenset[str]


def _get_auth_config(
    env: str | None = None,
    api_token: str | None = None,
) -> tuple[str, str | None]:
    resolved_env = (
        env
        if env is not None
        else os.environ.get("SHADOWSPARK_ENV", "test")
    ).strip().lower()

    resolved_token = (
        api_token
        if api_token is not None
        else os.environ.get("SHADOWSPARK_API_TOKEN")
    )
    if resolved_token is not None:
        resolved_token = resolved_token.strip()
        if not resolved_token:
            resolved_token = None

    return resolved_env, resolved_token


def authenticate(
    authorization: str | None,
    *,
    env: str | None = None,
    api_token: str | None = None,
) -> Principal:
    current_env, configured_token = _get_auth_config(env=env, api_token=api_token)
    is_production = current_env == "production"

    # Production MUST have SHADOWSPARK_API_TOKEN configured.
    # Missing production token fails closed immediately.
    if is_production:
        if not configured_token:
            raise AuthenticationError("production authentication token not configured")
        expected_token = configured_token
    else:
        # In test / development:
        # If explicitly configured, require that token; otherwise default deterministically to TEST_CAPABILITY.
        expected_token = configured_token if configured_token else TEST_CAPABILITY

    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        raise AuthenticationError("invalid capability")

    token = authorization.removeprefix("Bearer ")
    if not token or not hmac.compare_digest(token, expected_token):
        raise AuthenticationError("invalid capability")

    # In production or custom configured token, derive a non-sensitive key fingerprint.
    # Never log or expose the raw secret token.
    if is_production or (configured_token and token != TEST_CAPABILITY):
        key_fingerprint = f"token:{hashlib.sha256(token.encode('utf-8')).hexdigest()[:12]}"
        env_label = "production" if is_production else current_env
    else:
        key_fingerprint = TEST_CAPABILITY
        env_label = "test"

    return Principal(
        key_id=key_fingerprint,
        tenant_id="tenant_a",
        environment=env_label,
        scopes=frozenset({"compliance:read", "compliance:review"}),
    )


def require_scope(principal: Principal, scope: str) -> None:
    if scope not in principal.scopes:
        raise AuthenticationError("required scope missing")
