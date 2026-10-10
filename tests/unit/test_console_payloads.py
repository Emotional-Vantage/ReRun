"""
Tests for the data the console needs but the API was not sending, and for the evidence
ledger it was silently losing.

Three defects, all of which made the UI either guess or stay quiet:

1. `budgets` carried the counters but not the limits, so the console hardcoded its own
   denominators (40 steps / 3 patches). Configure MAX_STEPS differently and the bar lied.

2. The `evidence` table's primary key was `id` alone. Evidence ids restart at E-001 in every
   project, so with INSERT OR REPLACE each new project's E-001 overwrote another project's
   E-001. Across 72 real projects only 7 rows had survived -- exactly one per distinct id.

3. `GET /{id}/evidence` preferred the database and fell back to the ledger file, so entries
   present in only one of them disappeared, and ids the state references but neither source
   can serve were omitted entirely rather than reported as missing.
"""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

import backend.app.runner as runner
from agent.state import ProjectState
from backend.app.db import get_connection, init_db, insert_evidence, save_project_state
from backend.app.main import app
from tools import paths

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_background_workers(monkeypatch):
    monkeypatch.setattr(runner, "start_project_worker", lambda pid, **kw: True)


def _project(project_id: str, **kwargs) -> ProjectState:
    # The suite runs against a scratch database (tests/conftest.py); it may not exist yet
    # when this module runs first.
    init_db("data/rerun.db")
    state = ProjectState(
        project_id=project_id, benchmark_id="b1_control", repo_commit="c1",
        phase="RUN", budgets={"steps_used": 3, "patches_used": 1},
        claims=[], paper_settings=[], repo_profile={}, **kwargs
    )
    save_project_state("data/rerun.db", project_id, "b1_control", "c1", "RUN", state)
    return state


def test_budgets_carry_the_configured_limits_not_just_the_counters():
    _project("P-BUDGET")
    try:
        budgets = client.get("/api/projects/P-BUDGET").json()["budgets"]
        assert budgets["steps_used"] == 3 and budgets["patches_used"] == 1
        # The limits come from agent.config, which is what the orchestrator enforces.
        from agent.config import MAX_PATCHES, MAX_STEPS
        assert budgets["max_steps"] == MAX_STEPS
        assert budgets["max_patches"] == MAX_PATCHES
    finally:
        client.delete("/api/projects/P-BUDGET")


def test_evidence_rows_of_different_projects_do_not_overwrite_each_other():
    """E-001 exists in nearly every project; one must not evict another."""
    init_db("data/rerun.db")
    shared = {
        "type": "log", "artifact_path": "/tmp/a.log", "line_start": None, "line_end": None,
        "sha256": "abc", "excerpt": "first", "created_by_tool": "t", "tool_call_id": "c1",
        "ts": "now",
    }
    insert_evidence("data/rerun.db", {**shared, "id": "E-001", "excerpt": "from A"}, "P-EV-A")
    insert_evidence("data/rerun.db", {**shared, "id": "E-001", "excerpt": "from B"}, "P-EV-B")

    conn = get_connection("data/rerun.db")
    rows = conn.execute(
        "SELECT project_id, excerpt FROM evidence WHERE id = 'E-001' "
        "AND project_id IN ('P-EV-A', 'P-EV-B') ORDER BY project_id"
    ).fetchall()
    conn.close()
    assert rows == [("P-EV-A", "from A"), ("P-EV-B", "from B")]


def test_legacy_evidence_table_is_migrated_without_losing_rows(tmp_path):
    """A database written before the fix keeps its rows and gains the composite key."""
    db_path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE evidence (id TEXT PRIMARY KEY, project_id TEXT, type TEXT, "
        "artifact_path TEXT, line_start INTEGER, line_end INTEGER, sha256 TEXT, "
        "excerpt TEXT, created_by_tool TEXT, tool_call_id TEXT, ts TEXT)"
    )
    conn.execute(
        "INSERT INTO evidence VALUES ('E-001','P-OLD','log','/tmp/x.log',1,2,'sha','ex','t','c','now')"
    )
    conn.commit()
    conn.close()

    init_db(db_path)

    conn = sqlite3.connect(db_path)
    schema = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'evidence'"
    ).fetchone()[0]
    rows = conn.execute("SELECT id, project_id FROM evidence").fetchall()
    leftovers = conn.execute(
        "SELECT name FROM sqlite_master WHERE name = 'evidence_legacy_pk'"
    ).fetchall()
    conn.close()

    assert "PRIMARY KEY (project_id, id)" in schema
    assert rows == [("E-001", "P-OLD")]
    assert leftovers == []


def test_evidence_listing_merges_both_stores_and_names_what_it_cannot_serve():
    state = _project("P-EV-MERGE")
    # One entry only in the ledger file, one only in the database, one referenced by the
    # state but stored nowhere -- the three cases that occur in real projects.
    ledger_path = paths.evidence_ledger_path("P-EV-MERGE")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps([{
        "id": "E-001", "type": "log", "artifact_path": "/tmp/a.log", "sha256": "a",
        "excerpt": "ledger only", "created_by_tool": "read_logs", "tool_call_id": "c1",
        "ts": "now", "line_start": None, "line_end": None,
    }]))
    insert_evidence("data/rerun.db", {
        "id": "E-002", "type": "result", "artifact_path": "/tmp/r.json", "line_start": None,
        "line_end": None, "sha256": "b", "excerpt": "db only",
        "created_by_tool": "extract_metric", "tool_call_id": "c2", "ts": "now",
    }, "P-EV-MERGE")
    state.evidence_ids = ["E-001", "E-002", "E-003"]
    save_project_state("data/rerun.db", "P-EV-MERGE", "b1_control", "c1", "RUN", state)

    try:
        items = client.get("/api/projects/P-EV-MERGE/evidence").json()
        by_id = {item["id"]: item for item in items}

        assert by_id["E-001"]["available"] is True
        assert by_id["E-001"]["excerpt"] == "ledger only"
        assert by_id["E-002"]["available"] is True
        assert by_id["E-002"]["excerpt"] == "db only"
        # Referenced by the agent, servable by nobody: reported, not quietly dropped.
        assert by_id["E-003"]["available"] is False
    finally:
        client.delete("/api/projects/P-EV-MERGE")
