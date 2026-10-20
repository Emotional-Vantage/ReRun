import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app import routes


def test_operator_actions_remain_available_without_configured_token(monkeypatch):
    monkeypatch.delenv("RERUN_OPERATOR_TOKEN", raising=False)

    routes.require_operator()


def test_operator_token_is_required_when_configured(monkeypatch):
    monkeypatch.setenv("RERUN_OPERATOR_TOKEN", "test-operator-token")

    with pytest.raises(HTTPException) as exc_info:
        routes.require_operator(authorization="Bearer wrong-token")
    assert exc_info.value.status_code == 401

    routes.require_operator(authorization="Bearer test-operator-token")


def test_benchmark_validation_reads_registry(tmp_path, monkeypatch):
    benchmark_dir = tmp_path / "benchmarks"
    benchmark_dir.mkdir()
    (benchmark_dir / "registry.json").write_text(
        json.dumps({"cases": [{"id": "b1_control"}]}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert routes._benchmark_exists("b1_control") is True
    assert routes._benchmark_exists("unknown") is False


def test_start_rejects_completed_project(monkeypatch):
    state = SimpleNamespace(phase="DONE", abort_requested=False)
    monkeypatch.setattr(routes, "get_project_state", lambda *_args: state)

    with pytest.raises(HTTPException) as exc_info:
        routes.start_project("proj_123")
    assert exc_info.value.status_code == 409


def test_start_rejects_aborted_project(monkeypatch):
    state = SimpleNamespace(phase="DONE", abort_requested=True)
    monkeypatch.setattr(routes, "get_project_state", lambda *_args: state)

    with pytest.raises(HTTPException) as exc_info:
        routes.start_project("proj_123")
    assert exc_info.value.status_code == 409
