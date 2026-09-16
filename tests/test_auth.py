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


def test_valid_configured_token_succeeds_in_production(monkeypatch):
    monkeypatch.setenv("SHADOWSPARK_ENV", "production")
    monkeypatch.setenv("SHADOWSPARK_API_TOKEN", "prod_secret_token_999")

    principal = authenticate("Bearer prod_secret_token_999", tenant_id="tenant_a")

    assert principal.environment == "production"
    assert principal.tenant_id == "tenant_a"
    assert principal.scopes == frozenset({"compliance:read", "compliance:review"})
    assert "prod_secret_token_999" not in principal.key_id
    assert principal.key_id.startswith("token:")


def test_production_missing_tenant_fails_closed(monkeypatch):
    monkeypatch.setenv("SHADOWSPARK_ENV", "production")
    monkeypatch.setenv("SHADOWSPARK_API_TOKEN", "prod_secret_token_999")

    with pytest.raises(AuthenticationError, match="tenant identifier required in production"):
        authenticate("Bearer prod_secret_token_999", tenant_id=None)

    with pytest.raises(AuthenticationError, match="tenant identifier required in production"):
        authenticate("Bearer prod_secret_token_999", tenant_id="   ")



def test_production_rejects_test_capability(monkeypatch):
    monkeypatch.setenv("SHADOWSPARK_ENV", "production")
    monkeypatch.setenv("SHADOWSPARK_API_TOKEN", "prod_secret_token_999")

    with pytest.raises(AuthenticationError) as error:
        authenticate("Bearer ss_test_redacted")

    assert "invalid capability" in str(error.value)
    assert "prod_secret_token_999" not in str(error.value)


def test_production_missing_token_fails_closed(monkeypatch):
    monkeypatch.setenv("SHADOWSPARK_ENV", "production")
    monkeypatch.delenv("SHADOWSPARK_API_TOKEN", raising=False)

    with pytest.raises(AuthenticationError, match="production authentication token not configured"):
        authenticate("Bearer prod_secret_token_999")

    with pytest.raises(AuthenticationError, match="production authentication token not configured"):
        authenticate("Bearer ss_test_redacted")

    with pytest.raises(AuthenticationError, match="production authentication token not configured"):
        authenticate(None)


def test_valid_configured_token_in_non_production(monkeypatch):
    monkeypatch.setenv("SHADOWSPARK_ENV", "development")
    monkeypatch.setenv("SHADOWSPARK_API_TOKEN", "dev_token_456")

    principal = authenticate("Bearer dev_token_456")
    assert principal.environment == "development"
    assert "dev_token_456" not in principal.key_id


def test_test_environment_remains_deterministic_without_env_vars(monkeypatch):
    monkeypatch.delenv("SHADOWSPARK_ENV", raising=False)
    monkeypatch.delenv("SHADOWSPARK_API_TOKEN", raising=False)

    principal = authenticate("Bearer ss_test_redacted")
    assert principal == Principal(
        key_id="ss_test_redacted",
        tenant_id="tenant_a",
        environment="test",
        scopes=frozenset({"compliance:read", "compliance:review"}),
    )
