from dataclasses import dataclass
import hmac


TEST_CAPABILITY = "ss_test_redacted"


class AuthenticationError(Exception):
    """Raised when a capability is missing, invalid, or insufficient."""


@dataclass(frozen=True)
class Principal:
    key_id: str
    tenant_id: str
    environment: str
    scopes: frozenset[str]


def authenticate(authorization: str | None) -> Principal:
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        raise AuthenticationError("invalid capability")
    token = authorization.removeprefix("Bearer ")
    if not token or not hmac.compare_digest(token, TEST_CAPABILITY):
        raise AuthenticationError("invalid capability")
    return Principal(
        key_id=TEST_CAPABILITY,
        tenant_id="tenant_a",
        environment="test",
        scopes=frozenset({"compliance:read", "compliance:review"}),
    )


def require_scope(principal: Principal, scope: str) -> None:
    if scope not in principal.scopes:
        raise AuthenticationError("required scope missing")
