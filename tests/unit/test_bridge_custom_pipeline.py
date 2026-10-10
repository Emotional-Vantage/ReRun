import pytest
from pathlib import Path
import subprocess

from agent.state import ProjectState, Approval
from agent.loop import run_project, set_sandbox, FakeSandbox
import agent.llm
from tests.agent.fakes import FakeLLM, get_fake_script_b3
from agent.llm import set_fake_llm

def test_bridge_custom_project_matches_b3(tmp_path, monkeypatch):
    """
    Bridge Test for Custom Repository Pipeline:
    Verifies that an external / custom project (source='custom', custom repo_url, paper_path)
    transitions cleanly through the complete 20-phase pipeline, matching b3's outcome:
    1. INGEST / ANALYZE: Extracts paper claims & paper settings.
    2. CLAIMS_CONFIRM: Confirmed by operator.
    3. RUN 1: Produces low accuracy (simulating the silent config discrepancy).
    4. DIAGNOSE / PATCH: Proposes config_value patch for learning_rate.
    5. APPROVAL: Approved by operator.
    6. PATCH_APPLY & RUN 2: Reaches target accuracy (0.956).
    7. DONE: Final status is REPRODUCED.
    """
    fake_llm = FakeLLM(get_fake_script_b3())
    set_fake_llm(fake_llm)
    monkeypatch.setattr(agent.llm, "LLM_MODE", "replay")
    monkeypatch.setenv("LLM_MODE", "replay")

    ws = str(tmp_path / "workspace")
    Path(ws).mkdir(parents=True)

    # Initialize a git repo inside the workspace directory
    subprocess.run(["git", "init"], cwd=ws, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=ws, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=ws, capture_output=True, check=True)

    (Path(ws) / "configs").mkdir(parents=True)
    (Path(ws) / "configs" / "default.yaml").write_text("learning_rate: 0.01\nepochs: 20\nseeds: [0, 1, 2, 3, 4]\n")
    (Path(ws) / "train.py").write_text("print('training...')\n")

    subprocess.run(["git", "add", "-A"], cwd=ws, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=ws, capture_output=True, check=True)

    sb = FakeSandbox()
    # Run 1 fails reproduction (accuracy 0.60 vs expected 0.956)
    sb.register("b3_lr_typo", 1, 0, "run 1 low accuracy", {
        "test_accuracy_mean": 0.60,
        "test_accuracy_per_seed": [0.60, 0.60, 0.60, 0.60, 0.60],
        "test_accuracy_std": 0.01
    })
    # Run 2 reproduces target claim (accuracy 0.956)
    sb.register("b3_lr_typo", 2, 0, "run 2 reproduced", {
        "test_accuracy_mean": 0.956,
        "test_accuracy_per_seed": [0.955, 0.957, 0.956, 0.956, 0.956],
        "test_accuracy_std": 0.001
    })
    set_sandbox(sb)

    repo_url = "https://github.com/rerun-testbed/digits-softmax"
    paper_path = "benchmarks/papers/digits_softmax.pdf"

    state = ProjectState(
        project_id="test_custom_bridge_b3",
        source="custom",
        benchmark_id="b3_lr_typo",
        repo_url=repo_url,
        repo_commit="abc1234",
        paper_path=paper_path,
        paper_sha256="dummy_sha256_hash",
        phase="INGEST",
        budgets={"steps_used": 0, "max_steps": 40},
        claims=[],
        paper_settings=[],
        repo_profile={}
    )

    deps = {
        "workspace": ws,
        "registry_path": "benchmarks/registry.json",
        "paper_path": paper_path,
        "sandbox": sb
    }

    # 1. Run loop until CLAIMS_CONFIRM
    run_project(state, deps)
    assert state.phase == "CLAIMS_CONFIRM"
    assert len(state.claims) > 0
    state.claims[0].confirmed_by_human = True
    state.command_confirmed = True

    # 2. Run loop until APPROVAL
    run_project(state, deps)
    assert state.phase == "APPROVAL"
    assert len(state.patches) == 1
    assert state.patches[0].type == "config_value"

    # Human approves the patch
    patch = state.patches[0]
    state.approvals.append(Approval(
        id="A-1",
        patch_id=patch.id,
        decision="approve",
        by="human",
        at="2026-10-08T00:00:00Z"
    ))

    # 3. Resume loop to completion
    run_project(state, deps)
    assert state.phase == "DONE"
    assert state.final["status"] == "REPRODUCED"
    assert state.source == "custom"
    assert state.repo_url == repo_url
    assert len([p for p in state.patches if p.status == "applied"]) == 1
