import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from agent.state import (
    Tolerance,
    MetricExtraction,
    Claim,
    PaperSetting,
    Plan,
    Evidence,
    Hypothesis,
    Edit,
    PatchProposal,
    CriticReview,
    Approval,
    Attempt,
    ProjectState,
    Event,
    Status,
    Phase,
    ErrorClass,
    RiskClass,
)
from tools.paths import (
    DEFAULT_RUNS_ROOT,
    set_runs_root,
    runs_root,
    run_dir,
    workspace_dir,
    workspace_path,
    wheelhouse_dir,
    logs_dir,
    evidence_ledger_path,
)


def test_minimal_construction_of_every_model():
    tol = Tolerance()
    assert tol.type == "abs"
    assert tol.value == 0.01

    me = MetricExtraction()
    assert me.kind == "results_json"

    claim = Claim(
        id="C-1",
        statement="Accuracy 95%",
        metric="accuracy",
        reported=0.95,
        source_ref="p.2",
        source_quote="Accuracy is 95%",
    )
    assert claim.reported == 0.95

    ps = PaperSetting(
        key="lr",
        value=0.01,
        source_ref="p.3",
        source_quote="learning rate 0.01",
    )
    assert ps.value == 0.01

    plan = Plan(
        command="python train.py",
        output_file="results.json",
        seeds=[1, 2, 3],
    )
    assert len(plan.seeds) == 3

    ev = Evidence(
        id="E-001",
        type="log",
        artifact_path="logs/run.log",
        sha256="abc123456",
        excerpt="error occurred",
        created_by_tool="runner",
        tool_call_id="call_1",
        ts="2026-10-10T00:00:00Z",
    )
    assert ev.id == "E-001"

    hypo = Hypothesis(id="H-1", text="missing yaml")
    assert hypo.text == "missing yaml"
    assert hypo.statement == "missing yaml"

    hypo2 = Hypothesis(id="H-2", statement="aliased statement")
    assert hypo2.text == "aliased statement"
    assert hypo2.statement == "aliased statement"

    edit = Edit(file="model.py", op="replace_line", new="x = 1")
    assert edit.new == "x = 1"

    patch = PatchProposal(
        id="P-1",
        hypothesis_id="H-1",
        type="dependency",
        rationale="add pyyaml",
        evidence=["E-001"],
        alternatives_considered=[],
        edits=[edit],
    )
    assert patch.id == "P-1"
    assert patch.evidence == ["E-001"]

    cr = CriticReview(
        id="CR-1",
        patch_id="P-1",
        round=1,
        verdict="SUPPORTED",
        checks={"syntax": True},
        verified_evidence=[],
        objections=[],
        required_changes=[],
        confidence="high",
        model="gemini",
    )
    assert cr.verdict == "SUPPORTED"

    appr = Approval(
        id="A-1",
        patch_id="P-1",
        decision="approve",
        at="2026-10-10T00:00:00Z",
    )
    assert appr.decision == "approve"

    attempt = Attempt(
        n=1,
        started_at="2026-10-10T00:00:00Z",
    )
    assert attempt.n == 1

    state = ProjectState(
        project_id="proj_1",
        phase="INGEST",
    )
    assert state.project_id == "proj_1"
    assert state.phase == "INGEST"
    assert state.reviews == state.critic_reviews

    event = Event(
        id=1,
        ts="2026-10-10T00:00:00Z",
        project_id="proj_1",
        step=1,
        role="tool",
        type="run",
        tool="runner",
        summary="executed command",
    )
    assert event.id == 1


def test_project_state_json_roundtrip():
    claim = Claim(
        id="C-1",
        statement="Accuracy 95%",
        metric="accuracy",
        reported=0.95,
        source_ref="p.2",
        source_quote="Accuracy 95%",
    )
    attempt = Attempt(
        n=1,
        exit_code=0,
        metrics={"accuracy": 0.952},
        started_at="2026-10-10T00:00:00Z",
    )
    state = ProjectState(
        project_id="proj_full",
        benchmark_id="b1_control",
        phase="DONE",
        claims=[claim],
        attempts=[attempt],
        pending={"kind": "approval", "id": "A-1", "patch_id": "P-1", "banner": None},
    )

    serialized = state.model_dump_json()
    deserialized = ProjectState.model_validate_json(serialized)

    assert deserialized.project_id == state.project_id
    assert deserialized.phase == state.phase
    assert len(deserialized.claims) == 1
    assert deserialized.claims[0].reported == 0.95
    assert len(deserialized.attempts) == 1
    assert deserialized.attempts[0].metrics == {"accuracy": 0.952}
    assert deserialized.pending == state.pending


def test_literal_fields_reject_invalid_values():
    with pytest.raises(ValidationError):
        ProjectState(project_id="test", phase="INVALID_PHASE")  # type: ignore

    with pytest.raises(ValidationError):
        Attempt(n=1, started_at="now", error_class="not_a_valid_error_class")  # type: ignore

    with pytest.raises(ValidationError):
        CriticReview(
            id="CR-1",
            patch_id="P-1",
            round=1,
            verdict="INVALID_VERDICT",  # type: ignore
            checks={},
            verified_evidence=[],
            objections=[],
            required_changes=[],
            confidence="high",
            model="gemini",
        )

    with pytest.raises(ValidationError):
        Tolerance(type="cubic")  # type: ignore


def test_tools_paths_functions_and_redirection(tmp_path):
    assert callable(set_runs_root)
    assert callable(runs_root)
    assert callable(run_dir)
    assert callable(workspace_dir)
    assert callable(workspace_path)
    assert callable(wheelhouse_dir)
    assert callable(logs_dir)
    assert callable(evidence_ledger_path)

    custom_root = str(tmp_path / "custom_runs")
    old_root = runs_root()
    try:
        set_runs_root(custom_root)
        assert runs_root() == Path(custom_root)
        p_id = "proj_test_paths"
        assert run_dir(p_id) == Path(custom_root) / p_id
        assert workspace_dir(p_id) == Path(custom_root) / p_id / "workspace"
        assert workspace_path(p_id) == str(Path(custom_root) / p_id / "workspace")
        assert wheelhouse_dir(p_id) == Path(custom_root) / p_id / "wheelhouse"
        assert logs_dir(p_id) == Path(custom_root) / p_id / "logs"
        assert evidence_ledger_path(p_id) == Path(custom_root) / p_id / "evidence.json"
    finally:
        set_runs_root(str(old_root))


def test_conftest_scratch_runs_root_is_isolated_and_on_disk():
    current_root = runs_root()
    # It must not be default data/runs because conftest redirects it
    assert current_root != Path(DEFAULT_RUNS_ROOT)
    # It must reside in data/.pytest-runs on disk, not in /tmp
    assert ".pytest-runs" in str(current_root)
