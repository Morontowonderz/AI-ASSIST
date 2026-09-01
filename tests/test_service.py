import pytest

from shadowspark_api.database import Database, IdempotencyConflict
from shadowspark_api.service import ComplianceService


def test_run_is_idempotent_and_replays_without_second_runner(tmp_path):
    service = ComplianceService(Database(tmp_path / "db.sqlite"), fixture_dir="vendor")
    first = service.create_brief("tenant_a", "ex_a_021", "idem-1", "req-1", "ss_test_redacted")
    second = service.create_brief("tenant_a", "ex_a_021", "idem-1", "req-2", "ss_test_redacted")
    assert first["brief_id"] == second["brief_id"]
    assert second["replayed"] is True


def test_different_body_same_key_conflicts(tmp_path):
    service = ComplianceService(Database(tmp_path / "db.sqlite"), fixture_dir="vendor")
    service.create_brief("tenant_a", "ex_a_021", "idem-1", "req-1", "ss_test_redacted")
    with pytest.raises(IdempotencyConflict):
        service.create_brief("tenant_a", "ex_a_022", "idem-1", "req-2", "ss_test_redacted")


def test_foreign_reference_is_blocked_without_runner(tmp_path):
    service = ComplianceService(Database(tmp_path / "db.sqlite"), fixture_dir="vendor")
    result = service.create_brief("tenant_a", "tenant_b:ex_009", "idem-1", "req-1", "ss_test_redacted")
    assert result["output"]["status"] == "blocked"
    assert result["tool_trace"] == []
    assert result["output"]["exception_id"] == "redacted"


def test_annotation_does_not_reinvoke_runner(tmp_path):
    service = ComplianceService(Database(tmp_path / "db.sqlite"), fixture_dir="vendor")
    created = service.create_brief("tenant_a", "ex_a_021", "idem-1", "req-1", "ss_test_redacted")
    review = service.annotate("tenant_a", created["brief_id"], "operator-1", "reviewed", "req-2", "ss_test_redacted")
    assert review["queue_state"] == "annotated"
    assert review["output"]["sor_status_unchanged"] is True
