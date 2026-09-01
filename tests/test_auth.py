import pytest

from shadowspark_api.auth import AuthenticationError, Principal, authenticate, require_scope


@pytest.mark.parametrize(
    "header",
    [None, "Basic ss_test_redacted", "Bearer", "Bearer wrong-token"],
)
def test_rejects_invalid_capability_without_echoing_secret(header):
    with pytest.raises(AuthenticationError) as error:
        authenticate(header)

    assert "ss_test_redacted" not in str(error.value)
    assert "wrong-token" not in str(error.value)


def test_accepts_only_test_capability_and_returns_tenant_scope():
    principal = authenticate("Bearer ss_test_redacted")

    assert principal == Principal(
        key_id="ss_test_redacted",
        tenant_id="tenant_a",
        environment="test",
        scopes=frozenset({"compliance:read", "compliance:review"}),
    )


def test_rejects_missing_scope_without_exposing_token():
    principal = authenticate("Bearer ss_test_redacted")

    with pytest.raises(AuthenticationError, match="scope"):
        require_scope(principal, "compliance:execute")
