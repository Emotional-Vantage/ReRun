import pytest
import shutil
import json
from pathlib import Path
from unittest.mock import patch

from agent.state import ProjectState, Claim, Approval
from agent.loop import run_project, set_sandbox, FakeSandbox, handle_diagnose, handle_report
from tools import paths


def test_b1_control_loop(tmp_path, monkeypatch):
    import agent.llm
    from tests.agent.fakes import FakeLLM, get_fake_script_b1
    from agent.llm import set_fake_llm

    fake_llm = FakeLLM(get_fake_script_b1())
    set_fake_llm(fake_llm)
    monkeypatch.setattr(agent.llm, "LLM_MODE", "replay")
    monkeypatch.setenv("LLM_MODE", "replay")
    ws = str(tmp_path / "workspace")
    Path(ws).mkdir(parents=True)

    # Setup template files in mock workspace
    (Path(ws) / "configs").mkdir(parents=True)
    (Path(ws) / "configs" / "default.yaml").write_text("learning_rate: 0.5\nepochs: 20\nseeds: [0, 1, 2, 3, 4]\n")
    (Path(ws) / "train.py").write_text("print('training...')\n")

    sb = FakeSandbox()
    # Run 1 succeeds with accuracy 0.956
    sb.register("b1_control", 1, 0, "run 1 ok", {
        "test_accuracy_mean": 0.956,
        "test_accuracy_per_seed": [0.955, 0.957, 0.956, 0.956, 0.956],
        "test_accuracy_std": 0.001
    })
    set_sandbox(sb)

    state = ProjectState(
        project_id="test_b1",
        benchmark_id="b1_control",
        repo_commit="abc1234",
        phase="INGEST",
        budgets={"steps_used": 0, "max_steps": 40},
        claims=[],
        paper_settings=[],
        repo_profile={}
    )

    deps = {
        "workspace": ws,
        "registry_path": "benchmarks/registry.json",
        "paper_path": "benchmarks/papers/digits_softmax.pdf",
        "sandbox": sb
    }

    # Run loop until CLAIMS_CONFIRM
    run_project(state, deps)
    assert state.phase == "CLAIMS_CONFIRM"
    assert state.pending is not None

    # Human confirms claim
    assert len(state.claims) > 0
    state.claims[0].confirmed_by_human = True
    state.command_confirmed = True

    # Resume loop to completion
    run_project(state, deps)

    assert state.phase == "DONE"
    assert state.final is not None
    assert state.final["status"] == "REPRODUCED"
    assert len(state.patches) == 0


def test_b2_dependency_loop(tmp_path, monkeypatch):
    import agent.llm
    from tests.agent.fakes import FakeLLM, get_fake_script_b2
    from agent.llm import set_fake_llm

    fake_llm = FakeLLM(get_fake_script_b2())
    set_fake_llm(fake_llm)
    monkeypatch.setattr(agent.llm, "LLM_MODE", "replay")
    monkeypatch.setenv("LLM_MODE", "replay")
    ws = str(tmp_path / "workspace")
    Path(ws).mkdir(parents=True)

    (Path(ws) / "configs").mkdir(parents=True)
    (Path(ws) / "configs" / "default.yaml").write_text("learning_rate: 0.5\n")
    (Path(ws) / "requirements.txt").write_text("numpy==1.26.4\n")
    (Path(ws) / "train.py").write_text("import yaml\n")

    sb = FakeSandbox()
    # Run 1 crashes: ModuleNotFoundError
    sb.register("b2_dependency", 1, 1, "ModuleNotFoundError: No module named 'yaml'", {})
    # Run 2 succeeds
    sb.register("b2_dependency", 2, 0, "success", {
        "test_accuracy_mean": 0.956,
        "test_accuracy_per_seed": [0.955, 0.957, 0.956, 0.956, 0.956],
        "test_accuracy_std": 0.001
    })
    set_sandbox(sb)

    state = ProjectState(
        project_id="test_b2",
        benchmark_id="b2_dependency",
        repo_commit="abc1234",
        phase="INGEST",
        budgets={"steps_used": 0, "max_steps": 40},
        claims=[],
        paper_settings=[],
        repo_profile={},
        evidence_ids=["E-001"]
    )

    ev_dir = paths.run_dir("test_b2") / "evidence"
    ev_dir.mkdir(parents=True, exist_ok=True)
    (ev_dir / "E-001_log.txt").write_text("ModuleNotFoundError: No module named 'yaml'\n")

    deps = {
        "workspace": ws,
        "registry_path": "benchmarks/registry.json",
        "paper_path": "benchmarks/papers/digits_softmax.pdf",
        "sandbox": sb
    }

    # 1. Run until CLAIMS_CONFIRM
    run_project(state, deps)
    assert state.phase == "CLAIMS_CONFIRM"
    state.claims[0].confirmed_by_human = True
    state.command_confirmed = True

    # 2. Run until APPROVAL
    run_project(state, deps)
    assert state.phase == "APPROVAL"
    assert state.pending is not None
    assert len(state.patches) == 1

    # Human approves patch
    patch_obj = state.patches[0]
    state.approvals.append(Approval(
        id="A-1",
        patch_id=patch_obj.id,
        decision="approve",
        by="human",
        at="now"
    ))

    # 3. Resume loop to completion
    run_project(state, deps)
    assert state.phase == "DONE"
    assert state.final["status"] == "REPRODUCED"
    assert len([p for p in state.patches if p.status == "applied"]) == 1


def test_budget_exhaustion(tmp_path, monkeypatch):
    import agent.llm
    monkeypatch.setattr(agent.llm, "LLM_MODE", "replay")
    monkeypatch.setenv("LLM_MODE", "replay")
    ws = str(tmp_path / "workspace")
    Path(ws).mkdir(parents=True)

    state = ProjectState(
        project_id="test_budget",
        benchmark_id="b1_control",
        repo_commit="abc1234",
        phase="RUN",
        budgets={"steps_used": 40, "max_steps": 40},
        claims=[],
        paper_settings=[],
        repo_profile={}
    )

    deps = {"workspace": ws}
    run_project(state, deps)

    assert any("budget exhausted" in issue for issue in state.unresolved_issues)
    assert state.phase == "DONE"


@patch("agent.llm.execute_provider_request")
def test_hypothesis_unrecorded_evidence_rejected(mock_execute, tmp_path):
    mock_execute.return_value = json.dumps({
        "reason": "Test diagnosis",
        "hypotheses": [{
            "id": "H-1",
            "text": "Hypothesis citing non-existent evidence",
            "status": "confirmed",
            "evidence": ["E-999"],
            "tested_with": [],
            "error_class": "runtime_error"
        }],
        "next_action": {
            "tool": "conclude_no_cause",
            "args": {}
        }
    })
    ws = str(tmp_path / "workspace")
    Path(ws).mkdir(parents=True)

    state = ProjectState(
        project_id="test_hypo_ev",
        benchmark_id="b1_control",
        repo_commit="abc1234",
        phase="DIAGNOSE",
        budgets={"steps_used": 0, "max_steps": 40},
        claims=[],
        paper_settings=[],
        repo_profile={},
        hypotheses=[],
        evidence_ids=["E-001"]
    )

    deps = {"workspace": ws}
    handle_diagnose(state, deps)

    assert len(state.hypotheses) == 0
    assert state.phase == "STATUS"


def test_report_persisted_before_llm_enrichment_fails(tmp_path, monkeypatch):
    ws = str(tmp_path / "workspace")
    Path(ws).mkdir(parents=True)
    state = ProjectState(
        project_id="test_report_enrichment_fail",
        benchmark_id="b1_control",
        phase="REPORT",
        budgets={"steps_used": 0, "max_steps": 40},
        claims=[],
        paper_settings=[],
        repo_profile={},
        evidence_ids=[],
    )
    deps = {"workspace": ws}

    def broken_llm(*args, **kwargs):
        raise RuntimeError("Simulated LLM service failure")

    monkeypatch.setattr("agent.llm.execute_provider_request", broken_llm)

    handle_report(state, deps)
    assert state.final is not None
    assert "report" in state.final
    assert state.phase == "REPORT_REVIEW"
