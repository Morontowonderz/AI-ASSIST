from fastapi.testclient import TestClient

from shadowspark_api.app import create_app


AUTH = {"Authorization": "Bearer ss_test_redacted"}


def client(tmp_path):
    return TestClient(create_app(tmp_path / "state.db", fixture_dir="vendor"))


def test_healthz(tmp_path):
    assert client(tmp_path).get("/healthz").json() == {"status": "ok"}


def test_create_and_read_review(tmp_path):
    c = client(tmp_path)
    response = c.post("/v1/compliance-review-brief", headers={**AUTH, "Idempotency-Key": "idem-1"}, json={"exception_id": "ex_a_021"})
    assert response.status_code == 201
    brief_id = response.json()["brief_id"]
    review = c.get(f"/v1/review-queue/{brief_id}", headers=AUTH)
    assert review.status_code == 200
    assert review.json()["queue_state"] == "pending_review"


def test_cross_tenant_and_unknown_are_indistinguishable(tmp_path):
    c = client(tmp_path)
    headers = {**AUTH, "Idempotency-Key": "idem-1"}
    foreign = c.post("/v1/compliance-review-brief", headers=headers, json={"exception_id": "tenant_b:ex_009"})
    unknown = c.post("/v1/compliance-review-brief", headers={**AUTH, "Idempotency-Key": "idem-2"}, json={"exception_id": "missing"})
    assert foreign.status_code == unknown.status_code == 404
    assert foreign.json() == unknown.json() == {"detail": "exception not found"}


def test_annotation_is_operator_only(tmp_path):
    c = client(tmp_path)
    created = c.post("/v1/compliance-review-brief", headers={**AUTH, "Idempotency-Key": "idem-1"}, json={"exception_id": "ex_a_021"}).json()
    response = c.post(f"/v1/review-queue/{created['brief_id']}/annotations", headers={**AUTH, "Idempotency-Key": "idem-ann-1"}, json={"annotation": "reviewed"})
    assert response.status_code == 200
    assert response.json()["queue_state"] == "annotated"


def test_idempotency_conflict(tmp_path):
    c = client(tmp_path)
    h = {**AUTH, "Idempotency-Key": "idem-1"}
    c.post("/v1/compliance-review-brief", headers=h, json={"exception_id": "ex_a_021"})
    assert c.post("/v1/compliance-review-brief", headers=h, json={"exception_id": "ex_a_011"}).status_code == 409


def test_budget_trip_is_rate_limited(tmp_path):
    c = client(tmp_path)
    response = c.post("/v1/compliance-review-brief", headers={**AUTH, "Idempotency-Key": "idem-13"}, json={"exception_id": "ex_a_013"})
    assert response.status_code == 429
    assert response.json()["output"]["status"] == "blocked"


def test_api_with_configured_production_token(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOWSPARK_ENV", "production")
    monkeypatch.setenv("SHADOWSPARK_API_TOKEN", "prod_token_live_123")
    c = client(tmp_path)
    prod_auth = {
        "Authorization": "Bearer prod_token_live_123",
        "X-Tenant-ID": "tenant_a",
        "Idempotency-Key": "idem-prod-1",
    }
    response = c.post("/v1/compliance-review-brief", headers=prod_auth, json={"exception_id": "ex_a_021"})
    assert response.status_code == 201


def test_api_production_fails_closed_when_tenant_header_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOWSPARK_ENV", "production")
    monkeypatch.setenv("SHADOWSPARK_API_TOKEN", "prod_token_live_123")
    c = client(tmp_path)

    # Missing tenant header on brief creation fails closed
    resp_create = c.post(
        "/v1/compliance-review-brief",
        headers={"Authorization": "Bearer prod_token_live_123", "Idempotency-Key": "idem-prod-notenant"},
        json={"exception_id": "ex_a_021"},
    )
    assert resp_create.status_code in {400, 401}

    # Missing tenant header on review queue get fails closed
    resp_get = c.get(
        "/v1/review-queue/some_brief_id",
        headers={"Authorization": "Bearer prod_token_live_123"},
    )
    assert resp_get.status_code in {400, 401}


def test_app_honors_shadowspark_db_path_env(tmp_path, monkeypatch):
    custom_db = tmp_path / "custom_dir" / "custom_app.db"
    monkeypatch.setenv("SHADOWSPARK_DB_PATH", str(custom_db))

    from shadowspark_api.app import create_app
    app = create_app()
    c = TestClient(app)
    resp = c.post(
        "/v1/compliance-review-brief",
        headers={**AUTH, "Idempotency-Key": "idem-custom-db"},
        json={"exception_id": "ex_a_021"},
    )
    assert resp.status_code == 201
    assert custom_db.exists()



def test_api_production_rejects_test_capability(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOWSPARK_ENV", "production")
    monkeypatch.setenv("SHADOWSPARK_API_TOKEN", "prod_token_live_123")
    c = client(tmp_path)
    response = c.post("/v1/compliance-review-brief", headers={**AUTH, "Idempotency-Key": "idem-prod-2"}, json={"exception_id": "ex_a_021"})
    assert response.status_code == 401
    assert response.json() == {"detail": "authentication failed"}


def test_api_production_fails_closed_when_token_unconfigured(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOWSPARK_ENV", "production")
    monkeypatch.delenv("SHADOWSPARK_API_TOKEN", raising=False)
    c = client(tmp_path)
    response = c.post("/v1/compliance-review-brief", headers={"Authorization": "Bearer any_token", "Idempotency-Key": "idem-prod-3"}, json={"exception_id": "ex_a_021"})
    assert response.status_code == 401
    assert response.json() == {"detail": "authentication failed"}


def test_api_unauthorized_without_header(tmp_path):
    c = client(tmp_path)
    response = c.post("/v1/compliance-review-brief", headers={"Idempotency-Key": "idem-prod-4"}, json={"exception_id": "ex_a_021"})
    assert response.status_code == 401
    assert response.json() == {"detail": "authentication failed"}


def test_annotation_requires_idempotency_key(tmp_path):
    c = client(tmp_path)
    created = c.post("/v1/compliance-review-brief", headers={**AUTH, "Idempotency-Key": "idem-ann-req"}, json={"exception_id": "ex_a_021"}).json()
    response = c.post(f"/v1/review-queue/{created['brief_id']}/annotations", headers=AUTH, json={"annotation": "missing key"})
    assert response.status_code == 400
    assert response.json() == {"detail": "Idempotency-Key required"}


def test_annotation_idempotency_replay_and_conflict(tmp_path):
    c = client(tmp_path)
    created = c.post("/v1/compliance-review-brief", headers={**AUTH, "Idempotency-Key": "idem-ann-test"}, json={"exception_id": "ex_a_021"}).json()
    brief_id = created["brief_id"]

    # First attempt: succeeds
    resp1 = c.post(f"/v1/review-queue/{brief_id}/annotations", headers={**AUTH, "Idempotency-Key": "idem-ann-key-1"}, json={"annotation": "initial review"})
    assert resp1.status_code == 200
    assert resp1.json()["queue_state"] == "annotated"
    assert len(resp1.json()["annotations"]) == 1

    # Replay with same key and same payload: succeeds (idempotent replay)
    resp2 = c.post(f"/v1/review-queue/{brief_id}/annotations", headers={**AUTH, "Idempotency-Key": "idem-ann-key-1"}, json={"annotation": "initial review"})
    assert resp2.status_code == 200
    assert len(resp2.json()["annotations"]) == 1

    # Conflict with same key and different payload: 409
    resp3 = c.post(f"/v1/review-queue/{brief_id}/annotations", headers={**AUTH, "Idempotency-Key": "idem-ann-key-1"}, json={"annotation": "conflicting review"})
    assert resp3.status_code == 409
    assert resp3.json() == {"detail": "idempotency key conflict"}


def test_multitenant_isolation_and_x_tenant_slug(tmp_path):
    c = client(tmp_path)

    # Tenant B creates a brief
    tenant_b_headers = {**AUTH, "X-Tenant-Slug": "tenant_b", "Idempotency-Key": "idem-b-1"}
    resp_b = c.post("/v1/compliance-review-brief", headers=tenant_b_headers, json={"exception_id": "ex_a_021"})
    assert resp_b.status_code == 201
    brief_b_id = resp_b.json()["brief_id"]
    assert brief_b_id is not None

    # Tenant A cannot read Tenant B's brief (404 - cross-tenant access returns 404 indistinguishable from missing)
    resp_a_read = c.get(f"/v1/review-queue/{brief_b_id}", headers={**AUTH, "X-Tenant-Slug": "tenant_a"})
    assert resp_a_read.status_code == 404
    assert resp_a_read.json() == {"detail": "review not found"}

    # Tenant B can read its own brief
    resp_b_read = c.get(f"/v1/review-queue/{brief_b_id}", headers=tenant_b_headers)
    assert resp_b_read.status_code == 200
    assert resp_b_read.json()["tenant_id"] == "tenant_b"

    # Tenant A cannot annotate Tenant B's brief
    resp_a_ann = c.post(f"/v1/review-queue/{brief_b_id}/annotations", headers={**AUTH, "X-Tenant-Slug": "tenant_a", "Idempotency-Key": "idem-a-cross"}, json={"annotation": "cross note"})
    assert resp_a_ann.status_code == 404

    # Tenant B can annotate its own brief
    resp_b_ann = c.post(f"/v1/review-queue/{brief_b_id}/annotations", headers={**tenant_b_headers, "Idempotency-Key": "idem-b-ann"}, json={"annotation": "tenant b note"})
    assert resp_b_ann.status_code == 200
    assert resp_b_ann.json()["queue_state"] == "annotated"


def test_x_tenant_slug_is_never_authorization(tmp_path):
    c = client(tmp_path)
    # Header present but no Authorization -> 401
    resp1 = c.post("/v1/compliance-review-brief", headers={"X-Tenant-Slug": "tenant_a", "Idempotency-Key": "idem-no-auth"}, json={"exception_id": "ex_a_021"})
    assert resp1.status_code == 401
    assert resp1.json() == {"detail": "authentication failed"}

    # Header present with invalid token -> 401
    resp2 = c.post("/v1/compliance-review-brief", headers={"Authorization": "Bearer bad-token", "X-Tenant-Slug": "tenant_a", "Idempotency-Key": "idem-bad-auth"}, json={"exception_id": "ex_a_021"})
    assert resp2.status_code == 401
    assert resp2.json() == {"detail": "authentication failed"}


def test_invalid_tenant_slug_format_rejected(tmp_path):
    c = client(tmp_path)
    resp = c.post("/v1/compliance-review-brief", headers={**AUTH, "X-Tenant-Slug": "invalid/slug!", "Idempotency-Key": "idem-slug"}, json={"exception_id": "ex_a_021"})
    assert resp.status_code == 400
    assert resp.json() == {"detail": "invalid tenant identifier"}


def test_body_tenant_id_mismatch_rejected(tmp_path):
    c = client(tmp_path)
    resp = c.post("/v1/compliance-review-brief", headers={**AUTH, "X-Tenant-Slug": "tenant_a", "Idempotency-Key": "idem-mismatch"}, json={"exception_id": "ex_a_021", "tenant_id": "tenant_b"})
    assert resp.status_code == 400
    assert resp.json() == {"detail": "tenant mismatch between header and body"}


def test_stable_request_id_tracing(tmp_path):
    c = client(tmp_path)
    # Client passes X-Request-ID: echoed back
    resp = c.get("/healthz", headers={"X-Request-ID": "trace-client-id-456"})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == "trace-client-id-456"

    # Client omits X-Request-ID: generated and returned
    resp2 = c.get("/healthz")
    assert resp2.status_code == 200
    assert len(resp2.headers.get("X-Request-ID", "")) > 0


def test_idempotency_is_tenant_scoped(tmp_path):
    c = client(tmp_path)
    shared_key = "shared-idem-key"

    # Tenant A creates brief with shared_key
    resp_a = c.post("/v1/compliance-review-brief", headers={**AUTH, "X-Tenant-Slug": "tenant_a", "Idempotency-Key": shared_key}, json={"exception_id": "ex_a_021"})
    assert resp_a.status_code == 201

    # Tenant B creates brief with same shared_key and same exception_id: succeeds without conflict because idempotency is tenant-scoped
    resp_b = c.post("/v1/compliance-review-brief", headers={**AUTH, "X-Tenant-Slug": "tenant_b", "Idempotency-Key": shared_key}, json={"exception_id": "ex_a_021"})
    assert resp_b.status_code == 201
    assert resp_b.json()["brief_id"] is not None
    assert resp_a.json()["brief_id"] != resp_b.json()["brief_id"]
