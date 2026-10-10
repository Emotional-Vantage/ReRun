"""
Regression tests for project-state persistence durability.

Background: handle_validate assigns attempt.error_class = "metric_extraction_failed", and
tools.status.compute_status branches on that exact string, but the value was missing from the
ErrorClass literal. Pydantic does not validate on assignment, so the value persisted fine and
only failed on reload, permanently bricking that project. Worse, the approval endpoint used to
validate every project row while searching for an approval id, so one unreadable row broke
patch approval for every other project too.
"""

import json
import sqlite3
from typing import get_args

import pytest

from agent.state import ProjectState, Attempt, ErrorClass, PatchProposal, Edit
from backend.app.db import (
    CorruptProjectStateError,
    get_project_state,
    init_db,
    repair_unknown_error_classes,
    save_project_state,
)


def _make_state(project_id: str = "p_persist", phase: str = "VALIDATE") -> ProjectState:
    return ProjectState(
        project_id=project_id,
        benchmark_id="b1_control",
        repo_commit="abc1234",
        phase=phase,
        budgets={"steps_used": 0},
        claims=[],
        paper_settings=[],
        repo_profile={},
    )


def test_metric_extraction_failed_is_a_valid_error_class():
    """The value handle_validate assigns must be a member of the literal it is typed against."""
    assert "metric_extraction_failed" in get_args(ErrorClass)


@pytest.mark.parametrize("error_class", get_args(ErrorClass))
def test_every_error_class_survives_a_save_load_round_trip(tmp_path, error_class):
    """
    Any error_class the orchestrator can assign must round-trip through SQLite. This is the
    guard that stops a future error_class from bricking a project again.
    """
    db_path = str(tmp_path / "rerun.db")
    init_db(db_path)

    state = _make_state()
    state.attempts.append(
        Attempt(n=1, patches_applied=[], exit_code=1, error_class=error_class, started_at="now")
    )
    save_project_state(db_path, state.project_id, "b1_control", "abc1234", "running", state)

    loaded = get_project_state(db_path, state.project_id)
    assert loaded is not None
    assert loaded.attempts[0].error_class == error_class


def test_unreadable_row_raises_typed_error_naming_the_project(tmp_path):
    """An unparseable row must be a specific, attributable failure, not an opaque crash."""
    db_path = str(tmp_path / "rerun.db")
    init_db(db_path)

    state = _make_state(project_id="p_corrupt")
    save_project_state(db_path, "p_corrupt", "b1_control", "abc1234", "running", state)

    # Forge a row carrying an error_class outside the literal, as the old code did.
    conn = sqlite3.connect(db_path)
    raw = json.loads(conn.execute("SELECT state_json FROM projects WHERE id = 'p_corrupt'").fetchone()[0])
    raw["attempts"] = [{
        "n": 1, "patches_applied": [], "exit_code": 1,
        "error_class": "a_class_that_does_not_exist", "started_at": "now",
    }]
    conn.execute("UPDATE projects SET state_json = ? WHERE id = 'p_corrupt'", (json.dumps(raw),))
    conn.commit()
    conn.close()

    with pytest.raises(CorruptProjectStateError) as exc:
        get_project_state(db_path, "p_corrupt")
    assert exc.value.project_id == "p_corrupt"
    assert "error_class" in exc.value.detail


def test_repair_migration_rescues_rows_written_before_the_literal_was_fixed(tmp_path):
    """The migration must make an already-bricked project loadable again, and be idempotent."""
    db_path = str(tmp_path / "rerun.db")
    init_db(db_path)
    save_project_state(db_path, "p_old", "b1_control", "abc1234", "running", _make_state("p_old"))

    conn = sqlite3.connect(db_path)
    raw = json.loads(conn.execute("SELECT state_json FROM projects WHERE id = 'p_old'").fetchone()[0])
    raw["attempts"] = [{
        "n": 1, "patches_applied": [], "exit_code": 1,
        "error_class": "legacy_value_no_longer_valid", "started_at": "now",
    }]
    conn.execute("UPDATE projects SET state_json = ? WHERE id = 'p_old'", (json.dumps(raw),))
    conn.commit()
    conn.close()

    assert repair_unknown_error_classes(db_path) == 1
    loaded = get_project_state(db_path, "p_old")
    assert loaded is not None
    assert loaded.attempts[0].error_class == "unknown"

    # Idempotent: a second pass finds nothing left to repair.
    assert repair_unknown_error_classes(db_path) == 0


def test_one_unreadable_row_does_not_break_approvals_for_other_projects(tmp_path, monkeypatch):
    """
    The approval lookup must not validate unrelated projects. Previously it constructed a
    ProjectState for every row while searching, so a single bad row returned 500 for all
    pending approvals server-wide.
    """
    import backend.app.routes as routes

    db_path = str(tmp_path / "rerun.db")
    init_db(db_path)

    # A healthy project with a pending approval.
    healthy = _make_state(project_id="p_healthy", phase="APPROVAL")
    healthy.patches = [PatchProposal(
        id="P-1", hypothesis_id="H-1", type="dependency", rationale="missing module",
        evidence=["E-001"], alternatives_considered=[],
        edits=[Edit(file="requirements.txt", op="append_line", new="PyYAML==6.0.1")],
    )]
    healthy.pending = {"kind": "approval", "id": "A-OK", "patch_id": "P-1", "banner": None}
    save_project_state(db_path, "p_healthy", "b1_control", "abc1234", "APPROVAL", healthy)

    # An unreadable neighbour.
    save_project_state(db_path, "p_bad", "b1_control", "abc1234", "running", _make_state("p_bad"))
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE projects SET state_json = ? WHERE id = 'p_bad'", ('{"not_a": "project_state"}',))
    conn.commit()
    conn.close()

    monkeypatch.setattr(routes, "get_connection", lambda *_a, **_k: sqlite3.connect(db_path))

    # The lookup still finds the healthy project despite the unreadable neighbour.
    assert routes._find_project_by_pending_id("A-OK", db_path) == "p_healthy"
    assert routes._find_project_by_pending_id("A-MISSING", db_path) is None
