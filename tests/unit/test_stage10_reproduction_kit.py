import io
import os
import json
import zipfile
import pytest
from pathlib import Path

from agent.state import (
    ProjectState, Claim, Tolerance, PatchProposal, Edit, Attempt, Plan
)
from tools.kit import build_reproduction_kit, generate_reproduce_markdown
from tools.report import generate_report
from tools import paths

def create_mock_completed_state(project_id: str = "proj_stage10_test", simulated: bool = False) -> ProjectState:
    state = ProjectState(
        project_id=project_id,
        source="custom",
        benchmark_id="b3_silent_config",
        repo_url="https://github.com/rerun-benchmarks/digits-softmax",
        repo_commit="a1b2c3d4e5f60718293a4b5c6d7e8f90",
        paper_path="benchmarks/papers/digits_softmax.pdf",
        user_command="python train.py --config configs/default.yaml",
        simulated=simulated,
        phase="DONE",
        budgets={"steps_used": 3, "patches_used": 1},
        claims=[
            Claim(
                id="C-1",
                statement="Achieves 0.956 test accuracy on digits",
                metric="test_accuracy",
                reported=0.956,
                tolerance=Tolerance(type="abs", value=0.01),
                source_ref="p.4, Table 1",
                source_quote="accuracy of 0.956",
                primary=True,
                selected=True
            ),
            Claim(
                id="C-2",
                statement="Secondary unselected claim on extrapolation",
                metric="extrapolation_loss",
                reported=0.05,
                tolerance=Tolerance(type="abs", value=0.005),
                source_ref="p.7, Figure 3",
                source_quote="extrapolation loss 0.05",
                primary=False,
                selected=False
            )
        ],
        paper_settings=[],
        plan=Plan(
            command="python train.py --config configs/default.yaml",
            config_file="configs/default.yaml",
            output_file="outputs/results.json",
            seeds=[0, 1, 2, 3, 4]
        ),
        environment={"python_version": "3.11.8"},
        attempts=[
            Attempt(
                n=1,
                patches_applied=[],
                exit_code=0,
                metrics={"test_accuracy": 0.820},
                comparison=[{"claim_id": "C-1", "within_tolerance": False}],
                started_at="2026-10-08T10:00:00Z"
            ),
            Attempt(
                n=2,
                patches_applied=["P-001"],
                exit_code=0,
                metrics={"test_accuracy": 0.9556},
                comparison=[{"claim_id": "C-1", "within_tolerance": True}],
                started_at="2026-10-08T10:05:00Z"
            )
        ],
        patches=[
            PatchProposal(
                id="P-001",
                hypothesis_id="H-1",
                type="config_value",
                rationale="Align learning_rate with paper value 0.5",
                evidence=["E-001"],
                alternatives_considered=[],
                edits=[
                    Edit(file="configs/default.yaml", op="replace_text", old="learning_rate: 0.01", new="learning_rate: 0.5")
                ],
                diff="--- a/configs/default.yaml\n+++ b/configs/default.yaml\n@@ -1,1 +1,1 @@\n-learning_rate: 0.01\n+learning_rate: 0.5\n",
                status="applied"
            )
        ],
        provisioning_plan={
            "packages": [{"package": "pyyaml", "version": "6.0.1"}]
        },
        repo_profile={
            "triage": {
                "verdict": "FEASIBLE_WITH_PROVISIONING",
                "reason": "Standard PyTorch repository requiring PyYAML wheel provisioning."
            }
        },
        final={
            "status": "REPRODUCED",
            "reason": "Test accuracy matches paper within ±0.01",
            "after_n_fixes": 1
        },
        evidence_ids=["E-001"]
    )
    return state

def test_build_reproduction_kit_contains_all_required_files(tmp_path):
    state = create_mock_completed_state("proj_kit_struct", simulated=False)
    
    run_dir = tmp_path / "runs" / state.project_id
    run_dir.mkdir(parents=True)
    (run_dir / "logs").mkdir()
    (run_dir / "logs" / "run_1.log").write_text("Run 1 logs: accuracy 0.820\n", encoding="utf-8")
    (run_dir / "logs" / "run_2.log").write_text("Run 2 logs: accuracy 0.9556\n", encoding="utf-8")
    (run_dir / "outputs").mkdir()
    (run_dir / "outputs" / "results.json").write_text(json.dumps({"test_accuracy": 0.9556}), encoding="utf-8")
    (run_dir / "evidence.json").write_text(json.dumps([{"id": "E-001", "kind": "log", "citation": "Log excerpt"}]), encoding="utf-8")

    zip_bytes = build_reproduction_kit(state, base_dir=str(tmp_path))
    assert len(zip_bytes) > 0

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()
        assert "patches/P-001.diff" in namelist
        assert "reproduce.md" in namelist
        assert "results/results.json" in namelist
        assert "logs/run_1.log" in namelist
        assert "logs/run_2.log" in namelist
        assert "report.md" in namelist
        assert "report.html" in namelist
        assert "evidence_index.json" in namelist

        reproduce_text = zf.read("reproduce.md").decode("utf-8")
        assert state.repo_url in reproduce_text
        assert state.repo_commit in reproduce_text
        assert "3.11" in reproduce_text
        assert "python train.py --config configs/default.yaml" in reproduce_text
        assert "git checkout" in reproduce_text
        assert "git apply ../patches/P-001.diff" in reproduce_text
        assert "0.956" in reproduce_text
        assert "0.9556" in reproduce_text
        assert "REPRODUCED" in reproduce_text

        diff_text = zf.read("patches/P-001.diff").decode("utf-8")
        assert "--- a/configs/default.yaml" in diff_text
        assert "+learning_rate: 0.5" in diff_text

        ev_data = json.loads(zf.read("evidence_index.json").decode("utf-8"))
        assert len(ev_data) == 1
        assert ev_data[0]["id"] == "E-001"

def test_reproduce_markdown_generator_formatting():
    state = create_mock_completed_state("proj_reproduce_md", simulated=False)
    md = generate_reproduce_markdown(state)

    assert "## 1. Environment & Target Specifications" in md
    assert "## 2. Step-by-Step Reproduction Instructions" in md
    assert state.repo_commit in md
    assert "Expected vs. Observed Metric" in md
    assert "0.956" in md
    assert "0.9556" in md
    assert "±0.01" in md

def test_report_upgrades_metadata_and_simulated_banner():
    state_real = create_mock_completed_state("proj_rep_real", simulated=False)
    rep_real = generate_report(state_real)
    md_real = rep_real["markdown"]

    assert state_real.repo_url in md_real
    assert state_real.repo_commit in md_real
    assert "digits_softmax.pdf" in md_real
    assert "FEASIBLE_WITH_PROVISIONING" in md_real
    assert "pyyaml" in md_real
    assert "SIMULATED RUN" not in md_real

    assert any("Hardware and non-determinism limitation" in lim for lim in rep_real["limitations"])
    assert any("Claim C-2" in nc for nc in rep_real["not_checked"])
    assert "Unselected Claims (Not Checked)" in md_real

    state_sim = create_mock_completed_state("proj_rep_sim", simulated=True)
    rep_sim = generate_report(state_sim)
    md_sim = rep_sim["markdown"]
    html_sim = rep_sim["html"]

    assert "⚠️ **SIMULATED RUN**" in md_sim
    assert "SIMULATED RUN" in html_sim
    assert rep_sim["simulated"] is True

def test_api_download_reproduction_kit(tmp_path, monkeypatch):
    pytest.importorskip("backend.app.routes")
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.db import init_db, save_project_state, get_project_state

    db_file = tmp_path / "rerun.db"
    init_db(str(db_file))

    state = create_mock_completed_state("proj_api_kit", simulated=False)
    save_project_state(str(db_file), state.project_id, state.benchmark_id, state.repo_commit, state.phase, state)

    monkeypatch.setattr("backend.app.routes.get_project_state", lambda db, pid: get_project_state(str(db_file), pid))

    client = TestClient(app)

    resp = client.get(f"/api/projects/{state.project_id}/kit")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert 'attachment; filename="rerun_kit_proj_api_kit.zip"' in resp.headers["content-disposition"]

    zip_bytes = resp.content
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()
        assert "reproduce.md" in namelist
        assert "report.md" in namelist
        assert "patches/P-001.diff" in namelist

    resp_404 = client.get("/api/projects/nonexistent_proj/kit")
    assert resp_404.status_code == 404

def test_api_evidence_ledger_endpoints_and_drawer(tmp_path, monkeypatch):
    pytest.importorskip("backend.app.routes")
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.db import init_db, save_project_state, insert_evidence, get_project_state, get_all_evidence, get_evidence_by_id

    db_file = tmp_path / "rerun.db"
    init_db(str(db_file))

    state = create_mock_completed_state("proj_ev_test", simulated=False)
    save_project_state(str(db_file), state.project_id, state.benchmark_id, state.repo_commit, state.phase, state)

    insert_evidence(
        str(db_file),
        {
            "id": "E-001",
            "type": "log",
            "artifact_path": str(paths.logs_dir("proj_ev_test") / "run_1.log"),
            "line_start": 10,
            "line_end": 15,
            "sha256": "abc123sha",
            "excerpt": "ModuleNotFoundError: No module named 'yaml'",
            "created_by_tool": "inspect_error",
            "tool_call_id": "call_inspect_error_1",
            "ts": "2026-10-08T10:00:00Z"
        },
        project_id=state.project_id
    )

    monkeypatch.setattr("backend.app.routes.get_project_state", lambda db, pid: get_project_state(str(db_file), pid))
    monkeypatch.setattr("backend.app.db.get_all_evidence", lambda db, pid: get_all_evidence(str(db_file), pid))
    monkeypatch.setattr("backend.app.db.get_evidence_by_id", lambda db, pid, eid: get_evidence_by_id(str(db_file), pid, eid))

    client = TestClient(app)

    resp_list = client.get(f"/api/projects/{state.project_id}/evidence")
    assert resp_list.status_code == 200
    ev_items = resp_list.json()
    assert len(ev_items) >= 1
    assert ev_items[0]["id"] == "E-001"
    assert ev_items[0]["type"] == "log"

    resp_item = client.get(f"/api/projects/{state.project_id}/evidence/E-001")
    assert resp_item.status_code == 200
    item = resp_item.json()
    assert item["id"] == "E-001"
    assert "ModuleNotFoundError" in item["excerpt"]
    assert item["line_start"] == 10

    resp_missing = client.get(f"/api/projects/{state.project_id}/evidence/E-999")
    assert resp_missing.status_code == 404
