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
    response = c.post(f"/v1/review-queue/{created['brief_id']}/annotations", headers=AUTH, json={"annotation": "reviewed"})
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
