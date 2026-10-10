"""
Regression tests for five defects found by manual UI testing.

1. A refused tool call was re-proposed every diagnose step. "pip install PyYAML" was refused
   six times because nothing told the Solver it had been refused.
2. The report claimed a successful reproduction for a run that crashed. The backend reported
   UNABLE_TO_EXECUTE, but a crashed attempt was recorded as within_tolerance=False rather than
   "never measured", and the console filled the missing metric with the literal 0.956.
3. An UNSUPPORTED_FORMAT repository still offered an active launch button.
4. The report was withheld until an optional LLM enrichment call finished, so nothing was
   saved or shown for minutes.
5. A GPU repository was always blocked because preflight received hardcoded GPU flags.
"""

import json
from pathlib import Path

import pytest

import agent.loop as loop
from agent.solver.schemas import NextAction
from agent.state import Attempt, Claim, Hypothesis, ProjectState, Tolerance
from tools.preflight import preflight_check
from tools.report import generate_report
from tools.status import compute_status


# ---------------------------------------------------------------------------
# 1. Refused actions must not be re-proposed forever
# ---------------------------------------------------------------------------

def _diagnose_state(pid="t_reject"):
    return ProjectState(
        project_id=pid, benchmark_id="b2_dependency", repo_commit="c", phase="DIAGNOSE",
        budgets={"steps_used": 0, "max_steps": 40}, claims=[], paper_settings=[],
        repo_profile={},
    )


class _RunCommandAction:
    reason = "need PyYAML installed"
    hypotheses: list = []
    next_action = NextAction(tool="run_command", args={"command": "pip install PyYAML"})


def test_refused_command_is_not_reproposed_indefinitely(monkeypatch):
    """The six-times-refused loop from the trace ledger must be bounded."""
    state = _diagnose_state()
    calls = {"n": 0}

    def stub(role, mode, payload, out_model, benchmark_id=None, **kwargs):
        calls["n"] += 1
        return _RunCommandAction()

    monkeypatch.setattr(loop, "llm_call", stub)

    for _ in range(8):
        if state.phase != "DIAGNOSE":
            break
        loop.handle_diagnose(state, {"workspace": "benchmarks/cases/b2_dependency"})

    assert calls["n"] <= loop.MAX_IDENTICAL_REJECTIONS, (
        f"refused command was re-proposed {calls['n']} times"
    )
    assert state.phase != "DIAGNOSE", "run never moved on from the refused action"


def test_refusal_is_reported_back_to_the_solver(monkeypatch):
    """The Solver cannot change course unless it is told the call was refused."""
    state = _diagnose_state("t_reject_feedback")
    seen_payloads = []

    def stub(role, mode, payload, out_model, benchmark_id=None, **kwargs):
        seen_payloads.append(payload)
        return _RunCommandAction()

    monkeypatch.setattr(loop, "llm_call", stub)

    loop.handle_diagnose(state, {"workspace": "benchmarks/cases/b2_dependency"})
    loop.handle_diagnose(state, {"workspace": "benchmarks/cases/b2_dependency"})

    assert len(seen_payloads) >= 2
    refused = seen_payloads[-1].get("refused_actions")
    assert refused, "second diagnose call carried no record of the first refusal"
    assert refused[0]["tool"] == "run_command"
    # The guidance must point at the supported route, not just say "not allowed".
    assert "dependency" in refused[0]["do_this_instead"].lower()
    assert "requirements.txt" in refused[0]["do_this_instead"]


def test_install_refusal_explains_the_supported_route():
    state = _diagnose_state("t_guidance")
    count = loop.record_rejected_action(
        state, "run_command", "Command not allowed: pip install PyYAML", "use a dependency patch"
    )
    assert count == 1
    assert loop.record_rejected_action(
        state, "run_command", "Command not allowed: pip install PyYAML", "use a dependency patch"
    ) == 2
    assert len(state.rejected_actions) == 1, "identical refusals must collapse into one record"


# ---------------------------------------------------------------------------
# 2. A crashed run must never be reported as reproduced
# ---------------------------------------------------------------------------

def _crashed_run_state():
    state = ProjectState(
        project_id="t_crashed", benchmark_id="b2_dependency", repo_commit="c",
        phase="STATUS", budgets={"steps_used": 4}, paper_settings=[], repo_profile={},
        claims=[Claim(
            id="C-1", statement="test accuracy of 0.956", metric="test_accuracy",
            reported=0.956, tolerance=Tolerance(type="abs", value=0.01),
            result_key="test_accuracy_mean", source_ref="p.1", source_quote="0.956",
            primary=True, confirmed_by_human=True,
        )],
    )
    state.attempts = [Attempt(
        n=1, patches_applied=[], exit_code=1, error_class="dependency_missing", started_at="now",
    )]
    return state


def test_crashed_attempt_is_not_measured_rather_than_outside_tolerance():
    """
    within_tolerance must be None, not False. False reads as "measured and missed", which is
    what let the console render a comparison for a run that never produced a number.
    """
    state = _crashed_run_state()
    state.final = compute_status(state)

    report = generate_report(state)
    point = report["runs_summary"]["comparison_chart"][0]

    assert point["observed"] is None
    assert point["within_tolerance"] is None, "crashed run reported as a measured miss"
    assert report["runs_summary"]["final_run"]["within_tolerance"] is None


def test_report_for_a_crashed_run_claims_no_reproduction():
    state = _crashed_run_state()
    state.final = compute_status(state)

    report = generate_report(state)
    assert report["status"] == "UNABLE_TO_EXECUTE"
    assert report["after_n_fixes"] == 0
    assert report["patches_summary"] == []

    # The exported markdown must not present the crash as a pass.
    md = report["markdown"]
    assert "Not measured" in md
    assert "N/A (crashed)" in md
    assert "REPRODUCED`" not in md.split("**Final Verdict:**")[1].split("\n")[0]


def test_successful_run_still_reports_within_tolerance():
    """The honesty fix must not suppress a genuine pass."""
    state = _crashed_run_state()
    state.attempts = [Attempt(
        n=1, patches_applied=[], exit_code=0, started_at="now",
        metrics={"C-1": 0.9555, "test_accuracy_mean": 0.9555},
        comparison=[{
            "claim_id": "C-1", "reported": 0.956, "observed": 0.9555,
            "abs_gap": 0.0005, "rel_gap": 0.0005,
            "tolerance": {"type": "abs", "value": 0.01}, "within_tolerance": True,
        }],
    )]
    state.final = compute_status(state)

    report = generate_report(state)
    assert report["status"] == "REPRODUCED"
    assert report["runs_summary"]["comparison_chart"][0]["within_tolerance"] is True


# ---------------------------------------------------------------------------
# 5. GPU availability must come from the host, not a hardcoded False
# ---------------------------------------------------------------------------

GPU_REPO_PROFILE = {
    "triage": {
        "verdict": "NEEDS_GPU",
        "reason": "Hard GPU requirement detected.",
        "blockers": ["gpu_required"],
        "warnings": [],
    },
    "hints": {"gpu": [], "network": [], "data_refs": []},
}


def test_usable_gpu_turns_the_blocker_into_a_warning(tmp_path):
    """With GPU mode on and a usable GPU, a GPU repository must be runnable."""
    res = preflight_check(str(tmp_path), GPU_REPO_PROFILE, gpu_enabled=True, gpu_usable=True)
    assert "gpu_required" not in res["blockers"]
    assert any("GPU" in w for w in res["warnings"])


@pytest.mark.parametrize("enabled,usable", [(False, False), (True, False), (False, True)])
def test_gpu_blocked_only_when_it_is_genuinely_unavailable(tmp_path, enabled, usable):
    res = preflight_check(
        str(tmp_path), GPU_REPO_PROFILE,
        gpu_enabled=enabled, gpu_usable=usable, gpu_detail="No nvidia runtime found",
    )
    assert "gpu_required" in res["blockers"]
    # The blocker must say why, so a missing driver is distinguishable from a disabled flag.
    assert res["gpu_detail"]


def test_gpu_status_reason_names_the_actual_cause(tmp_path):
    """"NEEDS_GPU" alone is not actionable; the probe's reason must reach the verdict."""
    state = ProjectState(
        project_id="t_gpu", benchmark_id="b5_unable", repo_commit="c", phase="STATUS",
        budgets={}, claims=[], paper_settings=[], repo_profile={},
    )
    state.preflight = preflight_check(
        str(tmp_path), GPU_REPO_PROFILE,
        gpu_enabled=True, gpu_usable=False, gpu_detail="No nvidia runtime found in Docker daemon",
    )
    final = compute_status(state)
    assert final["status"] == "UNABLE_TO_EXECUTE"
    assert "nvidia runtime" in final["reason"]
    assert "gpu_required" in final["blockers"]


def test_orchestrator_does_not_hardcode_gpu_flags():
    """Guard against the flags being pinned to False again."""
    source = Path("agent/loop.py").read_text(encoding="utf-8")
    assert "gpu_enabled=False, gpu_usable=False" not in source
    assert "probe_gpu" in source
