import pytest
from unittest.mock import patch
import json
from pathlib import Path
from agent.state import ProjectState, PatchProposal, Hypothesis, Edit, PaperSetting
from agent.critic.review import build_review_packet, review_patch, ALL_CHECKLIST_KEYS
from tools.evidence import record_evidence

def make_critic_test_state():
    h = Hypothesis(id="H-1", text="Missing dependency PyYAML", status="confirmed")
    ps = PaperSetting(key="learning_rate", value=0.5, source_ref="p.1", source_quote="learning rate = 0.5")
    return ProjectState(
        project_id="test_critic_proj",
        benchmark_id="b2_dependency",
        repo_commit="abc1234",
        phase="CRITIC_REVIEW",
        budgets={},
        claims=[],
        paper_settings=[ps],
        repo_profile={},
        hypotheses=[h],
        evidence_ids=["E-001"]
    )

def test_critic_packet_building():
    state = make_critic_test_state()
    patch = PatchProposal(
        id="P-1",
        hypothesis_id="H-1",
        type="dependency",
        rationale="Fix missing PyYAML",
        evidence=["E-001"],
        alternatives_considered=[],
        edits=[Edit(file="requirements.txt", op="append_line", new="PyYAML==6.0.1")]
    )
    packet = build_review_packet(state, patch)
    assert packet["patch_id"] == "P-1"
    assert packet["type"] == "dependency"
    assert packet["hypothesis"] == "Missing dependency PyYAML"
    assert len(packet["paper_settings"]) == 1

@patch("agent.llm.execute_provider_request")
def test_critic_verdict_override_critical_check_failed(mock_execute):
    state = make_critic_test_state()
    patch = PatchProposal(
        id="P-1",
        hypothesis_id="H-1",
        type="config_value",
        rationale="Tune lr to boost accuracy",
        evidence=["E-001"],
        alternatives_considered=[],
        edits=[Edit(file="configs/default.yaml", op="replace_text", old="lr: 0.01", new="lr: 0.5")]
    )
    
    # Critic attempts to say SUPPORTED even though not_metric_chasing is False!
    mock_execute.side_effect = [
        json.dumps({
            "id": "R-1",
            "patch_id": "P-1",
            "round": 1,
            "verdict": "SUPPORTED",
            "checks": {
                "cause_is_cited_and_exists": True,
                "evidence_actually_supports_cause": True,
                "change_is_minimal": True,
                "files_in_scope": True,
                "not_metric_chasing": False, # Critical check fails!
                "value_has_paper_or_error_provenance": True,
                "no_change_to_evaluation_or_data_semantics": True,
                "alternative_explanations_considered": True,
                "reversible_and_smoke_testable": True
            },
            "verified_evidence": [],
            "objections": ["Metric chasing detected"],
            "required_changes": [],
            "confidence": "high",
            "model": "fake"
        }),
        json.dumps({
            "id": "R-2",
            "patch_id": "P-1",
            "round": 2,
            "verdict": "SUPPORTED",
            "checks": {
                "cause_is_cited_and_exists": True,
                "evidence_actually_supports_cause": True,
                "change_is_minimal": True,
                "files_in_scope": True,
                "not_metric_chasing": False,
                "value_has_paper_or_error_provenance": True,
                "no_change_to_evaluation_or_data_semantics": True,
                "alternative_explanations_considered": True,
                "reversible_and_smoke_testable": True
            },
            "verified_evidence": [],
            "objections": [],
            "required_changes": [],
            "confidence": "high",
            "model": "fake"
        })
    ]
    
    # Round 1: Code must override SUPPORTED to NEEDS_REVISION
    rev1 = review_patch(state, patch, round_num=1)
    assert rev1.verdict == "NEEDS_REVISION"
    
    # Round 2: Code must override to BLOCK
    rev2 = review_patch(state, patch, round_num=2)
    assert rev2.verdict == "BLOCK"

def test_critic_unavailable_fallback():
    state = make_critic_test_state()
    patch = PatchProposal(
        id="P-1",
        hypothesis_id="H-1",
        type="dependency",
        rationale="Fix PyYAML",
        evidence=["E-001"],
        alternatives_considered=[],
        edits=[Edit(file="requirements.txt", op="append_line", new="PyYAML==6.0.1")]
    )
    
    def failing_llm(*args, **kwargs):
        raise ConnectionError("Critic service down")
        
    rev = review_patch(state, patch, round_num=1, llm_call_fn=failing_llm)
    assert rev.model == "unavailable"
    assert rev.verdict == "BLOCK"
    assert any("Critic call failed" in obj for obj in rev.objections)
    assert len(rev.checks) == 9
    assert all(val is False for val in rev.checks.values())

def test_critic_quote_verification_against_real_artifact(tmp_path):
    state = make_critic_test_state()
    # Create real evidence artifact
    src_file = tmp_path / "error.log"
    src_file.write_text("Traceback: ModuleNotFoundError: No module named 'yaml'\n", encoding="utf-8")
    ev = record_evidence(state, "log", str(src_file), 1, 1, "test_tool", "call_1")
    eid = ev.id
    
    patch = PatchProposal(
        id="P-1",
        hypothesis_id="H-1",
        type="dependency",
        rationale="Fix PyYAML",
        evidence=[eid],
        alternatives_considered=[],
        edits=[Edit(file="requirements.txt", op="append_line", new="PyYAML==6.0.1")]
    )

    # 1. Honest verbatim quote from the real artifact
    honest_canned = {
        "verdict": "SUPPORTED",
        "checks": {k: True for k in ALL_CHECKLIST_KEYS},
        "verified_evidence": [{"id": eid, "what_i_found": "ModuleNotFoundError: No module named 'yaml'"}],
        "objections": [],
        "required_changes": [],
        "confidence": "high"
    }
    rev_honest = review_patch(state, patch, round_num=1, llm_call_fn=lambda *a, **kw: type('J', (), honest_canned)())
    assert rev_honest.checks["evidence_actually_supports_cause"] is True
    assert rev_honest.verdict == "SUPPORTED"

    # 2. Fabricated quote that does NOT exist in the artifact
    bogus_canned = {
        "verdict": "SUPPORTED",
        "checks": {k: True for k in ALL_CHECKLIST_KEYS},
        "verified_evidence": [{"id": eid, "what_i_found": "This line does not exist in any log"}],
        "objections": [],
        "required_changes": [],
        "confidence": "high"
    }
    rev_bogus = review_patch(state, patch, round_num=1, llm_call_fn=lambda *a, **kw: type('J', (), bogus_canned)())
    # Code must catch the mismatch and flip evidence_actually_supports_cause to False
    assert rev_bogus.checks["evidence_actually_supports_cause"] is False
    assert rev_bogus.verdict == "NEEDS_REVISION"

ALL_CHECKS_PASSING = {
    "cause_is_cited_and_exists": True,
    "evidence_actually_supports_cause": True,
    "change_is_minimal": True,
    "files_in_scope": True,
    "not_metric_chasing": True,
    "value_has_paper_or_error_provenance": True,
    "no_change_to_evaluation_or_data_semantics": True,
    "alternative_explanations_considered": True,
    "reversible_and_smoke_testable": True,
}

def test_persistent_needs_revision_terminates(monkeypatch):
    """A critic that always asks for revisions must stop, not spin."""
    loop = pytest.importorskip("agent.loop")
    from agent.config import CRITIC_ROUNDS_MAX
    from agent.state import CriticReview

    state = make_critic_test_state()
    state.phase = "PATCH_PROPOSE"
    state.budgets = {"steps_used": 0, "max_steps": 40}

    class StubPatchOutput:
        hypothesis_id = "H-1"
        type = "dependency"
        rationale = "ModuleNotFoundError: No module named 'yaml'"
        evidence = ["E-001"]
        alternatives_considered = []
        edits = [Edit(file="requirements.txt", op="append_line", new="PyYAML==6.0.1")]

    def stub_llm(role, mode, payload, out_model, benchmark_id=None, **kwargs):
        assert mode == "propose_patch", f"unexpected LLM mode {mode}"
        return StubPatchOutput()

    def always_needs_revision(st, patch, round_num=1, llm_call_fn=None):
        checks = dict(ALL_CHECKS_PASSING)
        checks["change_is_minimal"] = False  # non-critical failure -> NEEDS_REVISION
        return CriticReview(
            id=f"R-{len(st.critic_reviews) + 1}", patch_id=patch.id, round=round_num,
            verdict="NEEDS_REVISION", checks=checks, verified_evidence=[],
            objections=["patch is larger than necessary"], required_changes=["reduce scope"],
            confidence="medium", model="stub",
        )

    monkeypatch.setattr(loop, "llm_call", stub_llm)
    monkeypatch.setattr(loop, "review_patch", always_needs_revision)

    deps = {"workspace": "benchmarks/cases/b1_control"}
    iterations = 0
    max_iterations = 40
    while state.phase not in ("DONE", "STATUS", "APPROVAL") and iterations < max_iterations:
        if loop.guard_budgets(state):
            break
        loop.PHASE_HANDLERS[state.phase](state, deps)
        iterations += 1

    assert iterations < max_iterations
    assert state.phase == "APPROVAL"
    assert len(state.patches) <= CRITIC_ROUNDS_MAX + 1
    assert [p.status for p in state.patches].count("proposed") <= 1
    assert state.budgets["steps_used"] >= len(state.patches)
