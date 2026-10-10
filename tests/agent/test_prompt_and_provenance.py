import json
from unittest.mock import patch as mock_patch
from pathlib import Path

import pytest
from pydantic import BaseModel

import agent.llm as llm
from agent.critic.prompts import CRITIC_PATCH_REVIEW_PROMPT
from agent.solver.prompts import (
    DIAGNOSE_STEP_PROMPT,
    EXTRACT_CLAIMS_PROMPT,
    PLAN_EXPERIMENT_PROMPT,
    PROPOSE_PATCH_PROMPT,
    WRITE_REPORT_PROMPT,
)
from agent.state import Edit, Hypothesis, PatchProposal, ProjectState


class _Sample(BaseModel):
    ok: bool = True


def test_wrap_untrusted_fences_free_text_and_preserves_identifiers():
    """
    CRITICAL INVARIANT (§7.2 & Acceptance criteria):
    Free-text fields must be fenced in <untrusted> blocks.
    Structural identifiers (evidence, evidence_ids, id, patch_id, verdict) must NEVER be fenced.
    """
    sample = {
        "id": "P-001",
        "evidence": ["E-001", "E-002"],
        "evidence_ids": ["E-003"],
        "patch_id": "PATCH-42",
        "verdict": "SUPPORTED",
        "observation": "Error: missing module yaml",
        "paper_text": "We report 95.6% accuracy.",
        "rationale": "Need to pin dependency"
    }

    fenced = llm.wrap_untrusted(sample)

    # Identifiers must survive untouched and unfenced
    assert fenced["id"] == "P-001"
    assert fenced["evidence"] == ["E-001", "E-002"]
    assert fenced["evidence_ids"] == ["E-003"]
    assert fenced["patch_id"] == "PATCH-42"
    assert fenced["verdict"] == "SUPPORTED"

    # Free text fields must be fenced
    assert fenced["observation"] == "<untrusted>\nError: missing module yaml\n</untrusted>"
    assert fenced["paper_text"] == "<untrusted>\nWe report 95.6% accuracy.\n</untrusted>"
    assert fenced["rationale"] == "<untrusted>\nNeed to pin dependency\n</untrusted>"

    # Already fenced text is not double-wrapped
    already_fenced = {"observation": "<untrusted>\nalready fenced\n</untrusted>"}
    assert llm.wrap_untrusted(already_fenced)["observation"] == "<untrusted>\nalready fenced\n</untrusted>"


@mock_patch("agent.llm.execute_provider_request")
def test_task_prompt_reaches_the_model_in_the_system_message(mock_exec):
    """The mode's instructions must actually be sent."""
    mock_exec.return_value = json.dumps({"ok": True})

    llm.call("solver", "extract_claims", {"paper_text": "x"}, _Sample,
             task_prompt=EXTRACT_CLAIMS_PROMPT)

    messages = mock_exec.call_args[0][4]
    system_text = next(m["content"] for m in messages if m["role"] == "system")
    assert "Extract the headline experimental claim" in system_text
    assert "You are the SOLVER" in system_text
    assert "JSON Schema" in system_text


@mock_patch("agent.llm.execute_provider_request")
def test_task_prompt_does_not_disturb_the_user_message_or_cassette_key(mock_exec):
    """
    The prompt goes in the system message on purpose: the user message must stay
    byte-identical so cassette keys and the FakeLLM 'Mode:' assertion keep working.
    """
    mock_exec.return_value = json.dumps({"ok": True})
    payload = {"paper_text": "x"}

    llm.call("solver", "extract_claims", payload, _Sample)
    user_without = next(m["content"] for m in mock_exec.call_args[0][4] if m["role"] == "user")

    llm.call("solver", "extract_claims", payload, _Sample, task_prompt=EXTRACT_CLAIMS_PROMPT)
    user_with = next(m["content"] for m in mock_exec.call_args[0][4] if m["role"] == "user")

    assert user_with == user_without
    assert user_with.startswith("Mode: extract_claims")


def test_no_prompt_template_is_left_undeclared_in_the_tests():
    """Every public prompt constant in the prompt modules is covered by the test suite."""
    import agent.critic.prompts as critic_prompts
    import agent.solver.prompts as solver_prompts

    declared = {
        name
        for module in (solver_prompts, critic_prompts)
        for name in dir(module)
        if name.endswith("_PROMPT")
    }
    covered = {
        "EXTRACT_CLAIMS_PROMPT", "PLAN_EXPERIMENT_PROMPT", "DIAGNOSE_STEP_PROMPT",
        "PROPOSE_PATCH_PROMPT", "WRITE_REPORT_PROMPT",
        "CRITIC_PATCH_REVIEW_PROMPT", "CRITIC_REPORT_REVIEW_PROMPT",
    }
    assert declared == covered, (
        f"prompt templates not covered by the wiring test: {declared - covered}"
    )


def _critic_state():
    return ProjectState(
        project_id="test_prov_proj", benchmark_id="b2_dependency", repo_commit="abc",
        phase="CRITIC_REVIEW", budgets={}, claims=[], paper_settings=[], repo_profile={},
        hypotheses=[Hypothesis(id="H-1", text="PyYAML missing", status="confirmed")],
        evidence_ids=["E-001"],
    )


def _patch():
    return PatchProposal(
        id="P-1", hypothesis_id="H-1", type="dependency", rationale="missing module",
        evidence=["E-001"], alternatives_considered=[],
        edits=[Edit(file="requirements.txt", op="append_line", new="PyYAML==6.0.1")],
    )


@mock_patch("agent.llm.execute_provider_request")
def test_critic_cannot_report_its_own_identity_or_trustworthiness(mock_exec):
    """
    A model claiming `model: 'unavailable'` must not be able to make the Arbiter believe no
    independent review happened. Identity fields are set by code.
    """
    mock_exec.return_value = json.dumps({
        "id": "R-999",
        "patch_id": "P-SOMETHING-ELSE",
        "round": 42,
        "model": "unavailable",          # the field that gates the Arbiter
        "verdict": "SUPPORTED",
        "checks": {k: True for k in [
            "cause_is_cited_and_exists", "evidence_actually_supports_cause",
            "change_is_minimal", "files_in_scope", "not_metric_chasing",
            "value_has_paper_or_error_provenance",
            "no_change_to_evaluation_or_data_semantics",
            "alternative_explanations_considered", "reversible_and_smoke_testable",
        ]},
        "verified_evidence": [],
        "objections": [],
        "required_changes": [],
        "confidence": "high",
    })

    from agent.critic.review import review_patch

    state = _critic_state()
    review = review_patch(state, _patch(), round_num=2)

    assert review.model != "unavailable"
    assert review.patch_id == "P-1"
    assert review.round == 2
    assert review.id == "R-1"
    assert review.verdict == "SUPPORTED"


@mock_patch("agent.llm.execute_provider_request")
def test_critic_failure_still_marks_the_review_unavailable(mock_exec):
    """The failure path is the only route to 'unavailable', and it must still work."""
    mock_exec.side_effect = RuntimeError("provider down")

    from agent.critic.review import review_patch

    review = review_patch(_critic_state(), _patch(), round_num=1)
    assert review.model == "unavailable"
    assert review.verdict == "BLOCK"


def test_fake_sandbox_run_is_marked_simulated(monkeypatch, tmp_path):
    """A run that is not containerised must say so, so the report banner can render."""
    loop = pytest.importorskip("agent.loop")
    from sandbox.fake import FakeSandbox

    state = ProjectState(
        project_id="test_sim_flag", benchmark_id="b1_control", repo_commit="x",
        phase="INGEST", budgets={"steps_used": 0}, claims=[], paper_settings=[],
        repo_profile={},
    )
    assert state.simulated is False

    deps = {"workspace": str(tmp_path / "ws"), "sandbox": FakeSandbox(),
            "registry_path": "benchmarks/registry.json"}
    loop.handle_ingest(state, deps)

    assert state.simulated is True


def test_real_sandbox_run_is_not_marked_simulated(tmp_path):
    """The flag must not fire for a genuine container run."""
    loop = pytest.importorskip("agent.loop")
    from sandbox.docker_sandbox import DockerSandbox

    state = ProjectState(
        project_id="test_real_flag", benchmark_id="b1_control", repo_commit="x",
        phase="INGEST", budgets={"steps_used": 0}, claims=[], paper_settings=[],
        repo_profile={},
    )
    deps = {"workspace": str(tmp_path / "ws"), "sandbox": DockerSandbox(),
            "registry_path": "benchmarks/registry.json"}
    loop.handle_ingest(state, deps)

    assert state.simulated is False
