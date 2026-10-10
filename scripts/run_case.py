import os
import uuid
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv

load_dotenv()

from agent.state import ProjectState, Approval
from agent.loop import run_project
from agent.llm import set_fake_llm
from tests.agent.fakes import (
    FakeLLM,
    get_fake_script_b1,
    get_fake_script_b2,
    get_fake_script_b3,
    get_fake_script_b4_combined,
)

def get_headless_script_b2() -> list:
    return [
        ("solver", "extract_claims", {
            "claims": [{
                "statement": "We achieved a test accuracy of 0.956",
                "metric": "test_accuracy",
                "dataset": "digits",
                "reported": 0.956,
                "tolerance": {"type": "abs", "value": 0.01},
                "result_key": "test_accuracy_mean",
                "source_ref": "p.1",
                "source_quote": "test accuracy of 0.956"
            }],
            "paper_settings": [{
                "key": "learning_rate",
                "value": 0.5,
                "source_ref": "p.1",
                "source_quote": "learning rate = 0.5"
            }],
            "ambiguities": []
        }),
        ("solver", "plan_experiment", {
            "command": "python train.py --config configs/default.yaml",
            "config_file": "configs/default.yaml",
            "output_file": "outputs/results.json",
            "effective_config_file": "outputs/effective_config.json",
            "seeds": [0, 1, 2, 3, 4],
            "claim_result_keys": {"C-1": "test_accuracy_mean"},
            "notes": "Standard plan"
        }),
        ("solver", "diagnose_step", {
            "reason": "Run crashed. Let's inspect the error log.",
            "hypotheses": [],
            "next_action": {
                "tool": "inspect_error",
                "args": {}
            }
        }),
        ("solver", "diagnose_step", {
            "reason": "Run crashed with ModuleNotFoundError for yaml.",
            "hypotheses": [{
                "id": "H-1",
                "text": "PyYAML is missing",
                "status": "confirmed",
                "evidence": ["E-001"],
                "tested_with": ["inspect_error"],
                "error_class": "dependency_missing"
            }],
            "next_action": {
                "tool": "propose_patch",
                "args": {}
            }
        }),
        ("solver", "propose_patch", {
            "hypothesis_id": "H-1",
            "type": "dependency",
            "rationale": "ModuleNotFoundError: No module named 'yaml' requires PyYAML==6.0.1",
            "evidence": ["E-001"],
            "alternatives_considered": [],
            "edits": [{
                "file": "requirements.txt",
                "op": "append_line",
                "new": "PyYAML==6.0.1"
            }]
        }),
        ("critic", "patch_review", {
            "id": "R-1",
            "patch_id": "P-1",
            "round": 1,
            "verdict": "SUPPORTED",
            "checks": {
                "cause_is_cited_and_exists": True,
                "evidence_actually_supports_cause": True,
                "change_is_minimal": True,
                "files_in_scope": True,
                "not_metric_chasing": True,
                "value_has_paper_or_error_provenance": True,
                "no_change_to_evaluation_or_data_semantics": True,
                "alternative_explanations_considered": True,
                "reversible_and_smoke_testable": True
            },
            "verified_evidence": [{"id": "E-001", "what_i_found": "ModuleNotFoundError"}],
            "objections": [],
            "required_changes": [],
            "confidence": "high",
            "model": "fake"
        }),
        ("solver", "write_report", {
            "statements": [
                {
                    "id": "S-1",
                    "section": "findings",
                    "kind": "finding",
                    "confidence": "confirmed",
                    "text": "Reproduction succeeded after applying 1 dependency patch.",
                    "evidence": ["E-001"]
                }
            ]
        })
    ]

def run_case_headless(case_id: str, auto_approve: bool = True, use_fake_llm: bool = True):
    case_aliases = {
        "b1": "b1_control",
        "b2": "b2_dependency",
        "b3": "b3_silent_config",
        "b4": "b4_combined",
        "b5": "b5_unable",
    }
    case_id = case_aliases.get(case_id, case_id)

    if use_fake_llm:
        if case_id == "b1_control":
            set_fake_llm(FakeLLM(get_fake_script_b1()))
        elif case_id == "b2_dependency":
            set_fake_llm(FakeLLM(get_headless_script_b2()))
        elif case_id == "b3_silent_config":
            set_fake_llm(FakeLLM(get_fake_script_b3()))
        elif case_id == "b4_combined":
            set_fake_llm(FakeLLM(get_fake_script_b4_combined()))
        elif case_id == "b5_unable":
            set_fake_llm(FakeLLM(get_fake_script_b1()))

    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    state = ProjectState(
        project_id=project_id,
        benchmark_id=case_id,
        repo_commit="headless",
        phase="INGEST",
        budgets={"steps_used": 0, "max_steps": 40},
        claims=[],
        paper_settings=[],
        repo_profile={}
    )
    deps = {
        "workspace": f"data/runs/{project_id}/workspace",
        "registry_path": "benchmarks/registry.json",
        "paper_path": "benchmarks/papers/digits_softmax.pdf"
    }

    from agent.loop import get_sandbox
    sandbox_name = type(get_sandbox()).__name__
    is_real = sandbox_name == "DockerSandbox"

    print(f"\n========================================================")
    print(f"🚀 Starting headless run for case '{case_id}'")
    print(f"   Project ID: {project_id}")
    print(f"   Sandbox: {sandbox_name} ({'real container' if is_real else 'SIMULATED, not a real container'})")
    print(f"   LLM: {'scripted FakeLLM' if use_fake_llm else 'live provider'}")
    print(f"========================================================")

    step_counter = 0
    while state.phase != "DONE" and step_counter < 30:
        step_counter += 1
        run_project(state, deps)
        
        if state.pending:
            kind = state.pending.get("kind")
            if kind == "claims":
                print(f"📋 Claims extracted ({len(state.claims)} claims). Auto-confirming claims...")
                for c in state.claims:
                    c.confirmed_by_human = True
                state.command_confirmed = True
                state.pending = None
            elif kind == "approval":
                pending_patch_id = state.pending.get("patch_id")
                patch = next((pp for pp in state.patches if pp.id == pending_patch_id), state.patches[-1])
                print(f"⚖️ Patch proposed: {patch.id} ({patch.type}). Auto-approving...")
                appr = Approval(
                    id=f"appr_{uuid.uuid4().hex[:6]}",
                    patch_id=patch.id,
                    decision="approve" if auto_approve else "reject",
                    by="headless_approver",
                    at=datetime.datetime.now().isoformat()
                )
                state.approvals.append(appr)
                state.pending = None
            else:
                print(f"⚠️ Paused for pending {state.pending}. Clearing...")
                state.pending = None

    final_status = state.final.get("status") if state.final else state.phase
    print(f"\n🏁 Finished case '{case_id}' in phase '{state.phase}'.")
    print(f"📊 Final status: {final_status}")
    print(f"🔁 Attempts: {len(state.attempts)}, Patches: {len(state.patches)}")
    if state.attempts:
        for att in state.attempts:
            print(f"   - Attempt {att.n}: exit {att.exit_code}, metrics {att.metrics}")

    return state

if __name__ == "__main__":
    case = sys.argv[1] if len(sys.argv) > 1 else "b1_control"
    run_case_headless(case)
