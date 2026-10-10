import json
from typing import List, Tuple, Any, Dict, Union

class FakeLLM:
    """
    Fake LLM provider for tests.
    Takes a script of (role, mode, response) and pops them by mode.
    """
    def __init__(self, script: List[Tuple[str, str, Union[Dict[str, Any], str]]]):
        self.script = list(script)
        self.history = []

    def respond(self, messages: List[Dict[str, str]]) -> str:
        if not self.script:
            raise RuntimeError("FakeLLM script exhausted: no more responses configured.")

        user_msg = messages[-1]["content"]

        # Match the next response by MODE rather than strictly by position.
        index = 0
        if "Your response was invalid" not in user_msg:
            index = next(
                (i for i, (_r, mode, _resp) in enumerate(self.script)
                 if f"Mode: {mode}" in user_msg),
                -1,
            )
            if index == -1:
                requested = user_msg.split("\n", 1)[0]
                raise AssertionError(
                    f"FakeLLM has no scripted response for {requested!r}. "
                    f"Remaining modes: {[m for _r, m, _x in self.script]}"
                )

        expected_role, expected_mode, canned_resp = self.script.pop(index)
        
        self.history.append({
            "expected_role": expected_role,
            "expected_mode": expected_mode,
            "messages": messages,
            "response": canned_resp
        })
        
        if isinstance(canned_resp, str):
            return canned_resp
        return json.dumps(canned_resp)


def get_fake_script_b1() -> list:
    """Script for B1 Control Case: extracts claims, plans experiment, write report."""
    return [
        # 1. extract_claims
        ("solver", "extract_claims", {
            "claims": [{
                "statement": "We achieved a test accuracy of 0.956",
                "metric": "test_accuracy",
                "dataset": "digits",
                "reported": 0.956,
                "tolerance": {"type": "abs", "value": 0.01},
                "result_key": "test_accuracy_mean",
                "source_ref": "p.1, lines 58-59",
                "source_quote": "test accuracy of 0.956"
            }],
            "paper_settings": [{
                "key": "learning_rate",
                "value": 0.5,
                "source_ref": "p.1, line 38",
                "source_quote": "learning rate = 0.5"
            }],
            "ambiguities": []
        }),
        # 2. plan_experiment
        ("solver", "plan_experiment", {
            "command": "python train.py --config configs/default.yaml",
            "config_file": "configs/default.yaml",
            "output_file": "outputs/results.json",
            "effective_config_file": "outputs/effective_config.json",
            "seeds": [0, 1, 2, 3, 4],
            "claim_result_keys": {"C-1": "test_accuracy_mean"},
            "notes": "Plan from README"
        }),
        # 3. write_report
        ("solver", "write_report", {
            "statements": [
                {
                    "id": "S-1",
                    "section": "findings",
                    "kind": "finding",
                    "confidence": "confirmed",
                    "text": "The experiment reproduced the reported accuracy of {{claim.C-1.reported}} with observed {{result.run1.test_accuracy}} within tolerance {{claim.C-1.tolerance}}.",
                    "evidence": ["E-001"]
                }
            ]
        })
    ]

def get_fake_script_b2() -> list:
    """Script for B2 Dependency Case: missing PyYAML."""
    return [
        # 1. extract_claims
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
        # 2. plan_experiment
        ("solver", "plan_experiment", {
            "command": "python train.py --config configs/default.yaml",
            "config_file": "configs/default.yaml",
            "output_file": "outputs/results.json",
            "effective_config_file": "outputs/effective_config.json",
            "seeds": [0, 1, 2, 3, 4],
            "claim_result_keys": {"C-1": "test_accuracy_mean"},
            "notes": "Standard plan"
        }),
        # 3. diagnose_step: inspect requirements.txt
        ("solver", "diagnose_step", {
            "reason": "Run crashed with ModuleNotFoundError for yaml. Let's inspect requirements.txt.",
            "hypotheses": [{
                "id": "H-1",
                "text": "PyYAML is missing from requirements.txt",
                "status": "confirmed",
                "evidence": ["E-001"],
                "tested_with": ["inspect_file"],
                "error_class": "dependency_missing"
            }],
            "next_action": {
                "tool": "propose_patch",
                "args": {}
            }
        }),
        # 4. propose_patch: add PyYAML==6.0.1
        ("solver", "propose_patch", {
            "hypothesis_id": "H-1",
            "type": "dependency",
            "rationale": "ModuleNotFoundError: No module named 'yaml' requires PyYAML==6.0.1",
            "evidence": ["E-001"],
            "alternatives_considered": [{"option": "yaml", "why_not": "PyYAML is the standard PyPI package"}],
            "edits": [{
                "file": "requirements.txt",
                "op": "append_line",
                "new": "PyYAML==6.0.1"
            }]
        }),
        # 5. Critic patch_review
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
            "verified_evidence": [{"id": "E-001", "what_i_found": "ModuleNotFoundError: No module named 'yaml'"}],
            "objections": [],
            "required_changes": [],
            "confidence": "high",
            "model": "fake"
        }),
        # 6. write_report
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


def get_fake_script_b3() -> list:
    """Script for B3 Silent Config Case: bad learning rate."""
    return [
        # 1. extract_claims
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
        # 2. plan_experiment
        ("solver", "plan_experiment", {
            "command": "python train.py --config configs/default.yaml",
            "config_file": "configs/default.yaml",
            "output_file": "outputs/results.json",
            "effective_config_file": "outputs/effective_config.json",
            "seeds": [0, 1, 2, 3, 4],
            "claim_result_keys": {"C-1": "test_accuracy_mean"},
            "notes": "Standard plan"
        }),
        # 3. diagnose_step: inspect_file
        ("solver", "diagnose_step", {
            "reason": "Accuracy is too low. Let's inspect the config file.",
            "hypotheses": [],
            "next_action": {
                "tool": "inspect_file",
                "args": {"file": "configs/default.yaml"}
            }
        }),
        # 4. diagnose_step: propose_patch
        ("solver", "diagnose_step", {
            "reason": "Config has lr=0.01 but paper says 0.5.",
            "hypotheses": [{
                "id": "H-1",
                "text": "Learning rate mismatch",
                "status": "confirmed",
                "evidence": ["E-002"],
                "tested_with": ["inspect_file"],
                "error_class": "config_mismatch"
            }],
            "next_action": {
                "tool": "propose_patch",
                "args": {}
            }
        }),
        # 5. propose_patch
        ("solver", "propose_patch", {
            "hypothesis_id": "H-1",
            "type": "config_value",
            "rationale": "Paper specifies lr=0.5 but config uses 0.01",
            "evidence": ["E-002"],
            "alternatives_considered": [],
            "edits": [{
                "file": "configs/default.yaml",
                "op": "replace_text",
                "old": "learning_rate: 0.01",
                "new": "learning_rate: 0.5"
            }]
        }),
        # 6. Critic patch_review
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
            "verified_evidence": [{"id": "E-002", "what_i_found": "learning_rate: 0.01"}],
            "objections": [],
            "required_changes": [],
            "confidence": "high",
            "model": "fake"
        }),
        # 7. write_report
        ("solver", "write_report", {
            "statements": [
                {
                    "id": "S-1",
                    "section": "findings",
                    "kind": "finding",
                    "confidence": "confirmed",
                    "text": "Reproduction succeeded after applying 1 config patch.",
                    "evidence": ["E-002"]
                }
            ]
        })
    ]

def get_fake_script_b4_combined() -> list:
    """Script for B4 Combined Case: missing PyYAML AND bad learning rate."""
    return [
        # 1. extract_claims
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
        # 2. plan_experiment
        ("solver", "plan_experiment", {
            "command": "python train.py --config configs/default.yaml",
            "config_file": "configs/default.yaml",
            "output_file": "outputs/results.json",
            "effective_config_file": "outputs/effective_config.json",
            "seeds": [0, 1, 2, 3, 4],
            "claim_result_keys": {"C-1": "test_accuracy_mean"},
            "notes": "Standard plan"
        }),
        # 3. diagnose_step: inspect_error (to record E-001)
        ("solver", "diagnose_step", {
            "reason": "Run crashed. Let's inspect the error log.",
            "hypotheses": [],
            "next_action": {
                "tool": "inspect_error",
                "args": {}
            }
        }),
        # 4. diagnose_step: propose_patch (Patch 1)
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
        # 5. propose_patch (Patch 1)
        ("solver", "propose_patch", {
            "hypothesis_id": "H-1",
            "type": "dependency",
            "rationale": "Missing yaml module",
            "evidence": ["E-001"],
            "alternatives_considered": [],
            "edits": [{
                "file": "requirements.txt",
                "op": "append_line",
                "new": "PyYAML==6.0.1"
            }]
        }),
        # 6. Critic patch_review (Patch 1)
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
        # 7. diagnose_step: inspect_file (to record E-003)
        ("solver", "diagnose_step", {
            "reason": "Accuracy is too low. Let's inspect the config file.",
            "hypotheses": [],
            "next_action": {
                "tool": "inspect_file",
                "args": {"file": "configs/default.yaml"}
            }
        }),
        # 8. diagnose_step: propose_patch (Patch 2)
        ("solver", "diagnose_step", {
            "reason": "Config has lr=0.01 but paper says 0.5.",
            "hypotheses": [{
                "id": "H-2",
                "text": "Learning rate mismatch",
                "status": "confirmed",
                "evidence": ["E-003"],
                "tested_with": ["inspect_file"],
                "error_class": "config_mismatch"
            }],
            "next_action": {
                "tool": "propose_patch",
                "args": {}
            }
        }),
        # 9. propose_patch (Patch 2)
        ("solver", "propose_patch", {
            "hypothesis_id": "H-2",
            "type": "config_value",
            "rationale": "Paper specifies lr=0.5 but config uses 0.01",
            "evidence": ["E-003"],
            "alternatives_considered": [],
            "edits": [{
                "file": "configs/default.yaml",
                "op": "replace_text",
                "old": "learning_rate: 0.01",
                "new": "learning_rate: 0.5"
            }]
        }),
        # 10. Critic patch_review (Patch 2)
        ("critic", "patch_review", {
            "id": "R-2",
            "patch_id": "P-2",
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
            "verified_evidence": [{"id": "E-003", "what_i_found": "learning_rate: 0.01"}],
            "objections": [],
            "required_changes": [],
            "confidence": "high",
            "model": "fake"
        }),
        # 11. write_report
        ("solver", "write_report", {
            "statements": [
                {
                    "id": "S-1",
                    "section": "findings",
                    "kind": "finding",
                    "confidence": "confirmed",
                    "text": "Reproduction succeeded after applying 2 patches.",
                    "evidence": ["E-003"]
                }
            ]
        })
    ]
