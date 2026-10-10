import os
import json
import time
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from agent.state import ProjectState, PatchProposal, Edit, Claim
from backend.app.main import app
from backend.app.db import (
    init_db, get_connection, save_project_state, get_project_state,
    ConcurrentModificationError, get_all_evidence, get_evidence_by_id
)
from backend.app.runner import start_project_worker, is_worker_running, _RUNNING_WORKERS, _RUNNING_WORKERS_LOCK
from tools.evidence import record_evidence
from sandbox.fake import FakeSandbox
from agent.loop import set_sandbox
from tools import paths

client = TestClient(app)

@pytest.fixture(autouse=True)
def ensure_db():
    init_db("data/rerun.db")

def test_double_start_worker_prevention(monkeypatch):
    """Gate: Double-start returns same worker / prevents duplicate running threads (D15)."""
    started_count = 0
    gate_event = pytest.importorskip("threading").Event()

    def mock_run_project_thread(project_id: str):
        nonlocal started_count
        started_count += 1
        gate_event.wait(timeout=2.0)

    monkeypatch.setattr("backend.app.runner.run_project_thread", mock_run_project_thread)

    proj_id = "test_double_start"
    # First start: should spawn and return True
    first_res = start_project_worker(proj_id)
    assert first_res is True
    assert is_worker_running(proj_id) is True

    # Second start while running: should be rejected and return False
    second_res = start_project_worker(proj_id)
    assert second_res is False

    # Release worker thread
    gate_event.set()
    time.sleep(0.1)

    with _RUNNING_WORKERS_LOCK:
        t = _RUNNING_WORKERS.get(proj_id)
    if t:
        t.join(timeout=1.0)

    assert started_count == 1
    assert is_worker_running(proj_id) is False

def test_optimistic_locking_version(tmp_path):
    """Gate: Optimistic locking (version column) on state_json writes prevents lost updates (D15)."""
    db_path = str(tmp_path / "test_opt_lock.db")
    init_db(db_path)

    state = ProjectState(
        project_id="P-OPT",
        benchmark_id="b1",
        repo_commit="c1",
        phase="INGEST",
        budgets={"steps_used": 0},
        claims=[],
        paper_settings=[]
    )

    # Initial save: version becomes 1
    save_project_state(db_path, "P-OPT", "b1", "c1", "INGEST", state)
    loaded = get_project_state(db_path, "P-OPT")
    assert loaded.version == 1

    # Save with expected_version=1: succeeds and advances to version 2
    loaded.phase = "ANALYZE"
    save_project_state(db_path, "P-OPT", "b1", "c1", "ANALYZE", loaded, expected_version=1)
    
    loaded2 = get_project_state(db_path, "P-OPT")
    assert loaded2.version == 2
    assert loaded2.phase == "ANALYZE"

    # Concurrent modification attempt with stale version 1: raises ConcurrentModificationError
    with pytest.raises(ConcurrentModificationError):
        save_project_state(db_path, "P-OPT", "b1", "c1", "PLAN", loaded, expected_version=1)

def test_per_step_persistence_and_resumption(tmp_path, monkeypatch):
    """Gate: Per-step persistence in run_project + resume from mid-run state (D16)."""
    db_path = str(tmp_path / "resume.db")
    monkeypatch.setattr("backend.app.db.get_connection", lambda p=db_path: get_connection(db_path))
    init_db(db_path)

    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "train.py").write_text("print('hello')")

    state = ProjectState(
        project_id="P-RESUME",
        benchmark_id="b1",
        repo_commit="c1",
        phase="ANALYZE",
        workspace=str(ws_dir),
        budgets={"steps_used": 0, "max_steps": 10},
        claims=[Claim(statement="claim", metric="acc", reported=0.95, source_ref="p1", source_quote="quote", result_key="test_accuracy_mean")],
        paper_settings=[]
    )

    # Save to db
    save_project_state(db_path, "P-RESUME", "b1", "c1", "ANALYZE", state)

    # Run one step (ANALYZE transitions to CLAIMS_CONFIRM which sets pending and pauses)
    from agent.loop import run_project
    run_project(state, deps={"workspace": str(ws_dir)})

    # Verify per-step persistence: DB now has CLAIMS_CONFIRM state with pending confirmation
    persisted = get_project_state(db_path, "P-RESUME")
    assert persisted is not None
    assert persisted.phase == "CLAIMS_CONFIRM"
    assert persisted.pending is not None
    assert persisted.workspace == str(ws_dir)

    # Resume by confirming claims (simulated restart without original deps)
    persisted.command_confirmed = True
    persisted.pending = None
    persisted.phase = "PLAN"
    save_project_state(db_path, "P-RESUME", "b1", "c1", "PLAN", persisted)

    # Resume with fresh empty deps
    sb = FakeSandbox()
    set_sandbox(sb)
    try:
        run_project(persisted, deps={"sandbox": sb})
    finally:
        set_sandbox(None)
    
    # Verify the run resumed using persisted workspace and advanced past PLAN
    persisted_after = get_project_state(db_path, "P-RESUME")
    assert persisted_after.phase in ("PREFLIGHT", "SETUP", "RUN", "STATUS", "REPORT", "DONE")
    assert persisted_after.plan is not None

def test_abort_stops_worker_and_container(monkeypatch, tmp_path):
    """Gate: Abort sets abort_requested, calls container kill, stops worker, and marks DONE (D17)."""
    killed_containers = []
    monkeypatch.setattr("sandbox.manager.kill_project_containers", lambda pid: killed_containers.append(pid))

    proj_id = "P-ABORT"
    state = ProjectState(
        project_id=proj_id,
        benchmark_id="b1",
        repo_commit="c1",
        phase="RUN",
        budgets={"steps_used": 1},
        claims=[],
        paper_settings=[]
    )
    save_project_state("data/rerun.db", proj_id, "b1", "c1", "RUN", state)

    res = client.post(f"/api/projects/{proj_id}/abort")
    assert res.status_code == 200
    assert res.json() == {"status": "aborted"}

    # Assert container kill was triggered
    assert proj_id in killed_containers

    # Assert state is marked DONE with INCONCLUSIVE and abort_requested is True
    updated = get_project_state("data/rerun.db", proj_id)
    assert updated.phase == "DONE"
    assert updated.abort_requested is True
    assert updated.final["status"] == "INCONCLUSIVE"
    assert "aborted" in updated.final["reason"]

def test_evidence_persistence_and_retrieval(tmp_path):
    """Gate: Evidence persistence writes ledger and SQLite table so /evidence/{id} works (D12)."""
    data_dir = str(tmp_path / "data")
    src = tmp_path / "log.txt"
    src.write_text("Epoch 10 loss 0.042 accuracy 0.9556\n")

    proj_id = "P-EVID"
    state = ProjectState(
        project_id=proj_id,
        benchmark_id="b2",
        repo_commit="c2",
        phase="RUN",
        budgets={},
        claims=[],
        paper_settings=[]
    )
    save_project_state("data/rerun.db", proj_id, "b2", "c2", "RUN", state)

    ev = record_evidence(state, "log", str(src), 1, 1, "run_experiment", "call_42", data_dir=data_dir)
    assert ev.id == "E-001"

    # 1. Verify written to data/runs/<id>/evidence.json
    ledger_path = Path(data_dir) / "runs" / proj_id / "evidence.json"
    assert ledger_path.exists()
    ledger_items = json.loads(ledger_path.read_text())
    assert len(ledger_items) == 1
    assert ledger_items[0]["id"] == "E-001"

    # 2. Verify written to SQLite evidence table
    db_items = get_all_evidence("data/rerun.db", proj_id)
    assert len(db_items) == 1
    assert db_items[0]["id"] == "E-001"
    assert "accuracy 0.9556" in db_items[0]["excerpt"]

    # 3. Verify API retrieval
    res_single = client.get(f"/api/projects/{proj_id}/evidence/E-001")
    assert res_single.status_code == 200
    assert res_single.json()["id"] == "E-001"

    res_all = client.get(f"/api/projects/{proj_id}/evidence")
    assert res_all.status_code == 200
    assert len(res_all.json()) == 1

def test_aligned_log_routes_contract(tmp_path):
    """Gate: Contract test between /runs/{n}/log and /logs/{n} returning {log: ...} (D13)."""
    proj_id = "P-LOGS"
    log_dir = paths.logs_dir(proj_id)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "run_1.log"
    log_content = "Line 1: init\nLine 2: train\nLine 3: done\n"
    log_file.write_text(log_content)

    state = ProjectState(
        project_id=proj_id,
        benchmark_id="b1",
        repo_commit="c1",
        phase="STATUS",
        budgets={},
        claims=[],
        paper_settings=[]
    )
    save_project_state("data/rerun.db", proj_id, "b1", "c1", "STATUS", state)

    # Test backend primary route
    res_runs = client.get(f"/api/projects/{proj_id}/runs/1/log")
    assert res_runs.status_code == 200
    assert res_runs.json() == {"log": log_content}

    # Test frontend alias route
    res_logs = client.get(f"/api/projects/{proj_id}/logs/1")
    assert res_logs.status_code == 200
    assert res_logs.json() == {"log": log_content}

def test_approval_edit_policy_violation_rejected(tmp_path):
    """Gate: Edited patch that violates policy is rejected with reasons (D14)."""
    proj_id = "P-APPR-VIOL"
    ws_dir = tmp_path / "workspace_viol"
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "forbidden.py").write_text("secret = 123\n")

    state = ProjectState(
        project_id=proj_id,
        benchmark_id="b1",
        repo_commit="c1",
        phase="APPROVAL",
        workspace=str(ws_dir),
        budgets={},
        claims=[],
        paper_settings=[],
        pending={"kind": "approval", "id": "A-VIOL", "patch_id": "P-1"},
        patches=[PatchProposal(
            id="P-1",
            hypothesis_id="H-1",
            type="code_typo",
            rationale="test",
            evidence=[],
            alternatives_considered=[],
            edits=[Edit(file="forbidden.py", op="replace_text", old="123", new="456")]
        )]
    )
    save_project_state("data/rerun.db", proj_id, "b1", "c1", "APPROVAL", state)

    # Submit edit with a policy violation (e.g. attempting to modify denied security / env file or huge lines)
    invalid_edits = [
        {"file": ".env", "op": "append_line", "new": "MALICIOUS=1"}
    ]
    res = client.post("/api/approvals/A-VIOL", json={
        "decision": "edit",
        "edits": invalid_edits,
        "comment": "trying to edit forbidden file"
    })
    # Must reject with 400
    assert res.status_code == 400
    assert "Policy violation" in res.json()["detail"] or "does not exist" in res.json()["detail"]

    # Assert state remains in APPROVAL
    current_state = get_project_state("data/rerun.db", proj_id)
    assert current_state.phase == "APPROVAL"
    assert current_state.pending is not None

def test_approval_edit_valid_applied(tmp_path, monkeypatch):
    """Gate: Valid edited patch passes policy, re-runs Critic review, and applies (D14)."""
    monkeypatch.setattr("backend.app.runner.start_project_worker", lambda pid, **kw: True)

    proj_id = "P-APPR-VALID"
    ws_dir = tmp_path / "workspace_valid"
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "train.py").write_text("learning_rate = 0.01\n")

    from agent.state import Hypothesis
    h = Hypothesis(id="H-1", text="fix dimension typo", status="confirmed", error_class="unknown", evidence=["E-001"])

    state = ProjectState(
        project_id=proj_id,
        benchmark_id="b1",
        repo_commit="c1",
        phase="APPROVAL",
        workspace=str(ws_dir),
        budgets={},
        claims=[],
        paper_settings=[],
        evidence_ids=["E-001"],
        hypotheses=[h],
        pending={"kind": "approval", "id": "A-VALID", "patch_id": "P-1"},
        patches=[PatchProposal(
            id="P-1",
            hypothesis_id="H-1",
            type="code_typo",
            rationale="fix typo",
            evidence=["E-001"],
            alternatives_considered=[],
            edits=[Edit(file="train.py", op="replace_text", old="0.01", new="0.1")]
        )]
    )
    save_project_state("data/rerun.db", proj_id, "b1", "c1", "APPROVAL", state)

    valid_edits = [
        {"file": "train.py", "op": "replace_text", "old": "learning_rate = 0.01", "new": "learning_rate = 0.05"}
    ]
    res = client.post("/api/approvals/A-VALID", json={
        "decision": "edit",
        "edits": valid_edits,
        "comment": "operator adjusted lr to 0.05"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "applied_and_approved"
    assert len(data["patch"]["edits"]) == 1
    assert data["patch"]["edits"][0]["new"] == "learning_rate = 0.05"

    # State updated to PATCH_APPLY and pending cleared
    current_state = get_project_state("data/rerun.db", proj_id)
    assert current_state.phase == "PATCH_APPLY"
    assert current_state.pending is None
    assert current_state.patches[0].status == "approved"
