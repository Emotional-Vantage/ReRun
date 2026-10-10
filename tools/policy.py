import re
import ast
import json
import yaml
import hashlib
from typing import List, Dict, Any
from pathlib import Path

from agent.config import (
    MAX_FILES, MAX_CHANGED_LINES, LARGE_PATCH_FILES, LARGE_PATCH_LINES
)

DENY_LIST = [
    r"(?i)(?:^|/)eval.*",
    r"(?i)(?:^|/)metric.*",
    r"(?i)(?:^|/)test_.*",
    r"(?i)(?:^|/)tests/.*",
    r"(?i)(?:^|/)split.*",
    r"(?i)(?:^|/)data\.py",
    r"(?i)(?:^|/)dataset.*",
    r"(?i)(?:^|/)data/.*"
]

SENSITIVE_KEYS = [
    "seed", "seeds", "random_seed", "epochs", "n_epochs", "num_epochs",
    "n_samples", "test_size", "split_seed", "train_size", "batch_size", "bs", "dataset_size"
]

METRIC_CHASING_PATTERN = re.compile(
    r"(?i)\b(improv\w*|increas\w*|boost\w*|rais\w*|get(?:ting)?\s+closer|match(?:ing)?\s+the\s+(?:paper|reported)|reach(?:ing)?\s+[0-9.]+|hit\s+the\s+target)\b.*?\b(accuracy|score|metric|number|result)\b"
)

def compute_fix_signature(file: str, op: str, new_val: str) -> str:
    norm_new = new_val.strip().lower() if "==" in new_val else new_val.strip()
    src = f"{file}|{op}|{norm_new}"
    return hashlib.sha1(src.encode("utf-8")).hexdigest()

def get_canonical_key_for_policy(key: str) -> str:
    from tools.config_audit import get_canonical_key
    return get_canonical_key(key)

def parse_config_assignment(text: str) -> tuple:
    if not text:
        return (None, None)
    line = text.strip().splitlines()[0].strip() if text.strip() else ""
    for sep in (":", "="):
        if sep in line:
            key, _, raw_value = line.partition(sep)
            key = key.strip().strip("\"'")
            raw_value = raw_value.strip()
            if key:
                return (key, raw_value)
    return (None, None)

def values_match(paper_value: Any, proposed_raw: str) -> bool:
    """
    True only when the proposed value genuinely equals the paper-stated value.
    Parses both sides numerically or semantically.
    """
    from tools.config_audit import _parse_val

    if proposed_raw is None:
        return False

    cleaned = str(proposed_raw).split("#", 1)[0].strip().strip("\"'")
    if cleaned == "":
        return False

    parsed = _parse_val(cleaned)

    if isinstance(paper_value, bool) or isinstance(parsed, bool):
        if isinstance(paper_value, bool) and isinstance(parsed, bool):
            return paper_value is parsed
        return False

    if isinstance(paper_value, (int, float)):
        if isinstance(parsed, (int, float)):
            return abs(float(paper_value) - float(parsed)) <= 1e-9
        return False

    return str(paper_value).strip().casefold() == str(parsed).strip().casefold()

def find_paper_setting(state, key_name: str):
    from tools.config_audit import get_canonical_key

    for ps in state.paper_settings:
        if ps.key == key_name:
            return ps
    canonical = get_canonical_key(key_name)
    for ps in state.paper_settings:
        if get_canonical_key(ps.key) == canonical:
            return ps
        if getattr(ps, "repo_key", None) and ps.repo_key == key_name:
            return ps
    return None

def check(state, proposal, workspace: str = None) -> Dict[str, Any]:
    # Allow (proposal, state) argument order as well
    if hasattr(state, "edits") and not hasattr(proposal, "edits"):
        state, proposal = proposal, state

    violations = []
    flags = []
    risk_class = "bug_fix"
    requires_extra_confirm = False
    
    # P9: Fix signature not in failed_fixes
    for edit in proposal.edits:
        sig = compute_fix_signature(edit.file, edit.op, edit.new)
        if sig in state.failed_fixes:
            violations.append(f"P9: Fix signature {sig} already failed or was rejected previously")

    # P3: Hard limits and soft thresholds
    files_modified = list({e.file for e in proposal.edits})
    if len(files_modified) > MAX_FILES:
        violations.append(f"P3: Too many files modified ({len(files_modified)} > {MAX_FILES})")
        
    total_changed_lines = 0
    for edit in proposal.edits:
        new_lines = len(edit.new.splitlines()) if edit.new else 1
        old_lines = len(edit.old.splitlines()) if edit.old else 0
        total_changed_lines += (new_lines + old_lines)
        
    if total_changed_lines > MAX_CHANGED_LINES:
        violations.append(f"P3: Too many lines changed ({total_changed_lines} > {MAX_CHANGED_LINES})")
        
    if len(files_modified) > LARGE_PATCH_FILES or total_changed_lines > LARGE_PATCH_LINES:
        flags.append("large_patch")
        requires_extra_confirm = True

    # P7: Cause citation
    if not proposal.evidence:
        violations.append("P7: No evidence IDs cited in proposal")
    for eid in proposal.evidence:
        if eid not in state.evidence_ids:
            violations.append(f"P7: Cited evidence ID {eid} does not exist in ledger")
            
    # Check hypothesis exists and is confirmed
    matching_hypo = next((h for h in state.hypotheses if h.id == proposal.hypothesis_id), None)
    if not matching_hypo or matching_hypo.status != "confirmed":
        violations.append("P7: Hypothesis must exist with status='confirmed'")

    # P8: Metric language heuristic
    if METRIC_CHASING_PATTERN.search(proposal.rationale):
        flags.append("metric_language")
        violations.append("P8: Rationale indicates metric chasing without citing a concrete error cause")

    # Determine risk_class from type
    if proposal.type == "dependency":
        risk_class = "environment_fix"
    elif proposal.type == "config_value":
        risk_class = "config_alignment"
    elif proposal.type in ["code_typo", "code_api_compat"]:
        risk_class = "bug_fix"

    # P1 & P2: Path allow-list & deny-list
    for edit in proposal.edits:
        f = edit.file.replace("\\", "/")
        
        allowed_ext = f.endswith((".txt", ".yaml", ".yml", ".toml", ".json", ".py"))
        if not allowed_ext:
            violations.append(f"P1: File {f} does not match allowed config/dependency/code extensions")
        if f.endswith(".py") and proposal.type not in ["path_string", "code_typo", "code_api_compat"]:
            violations.append(f"P1: Python file {f} cannot be edited for type {proposal.type}")
        if proposal.type == "code_api_compat" and not f.endswith(".py"):
            violations.append(f"P1: Patch type code_api_compat is only permitted for Python files, not {f}")
            
        if proposal.type == "code_api_compat" and f.endswith(".py"):
            target_base = Path(f).name
            has_traceback_prov = False
            for eid in proposal.evidence:
                from tools.evidence import load_evidence_artifact
                ev_txt = load_evidence_artifact(getattr(state, "project_id", ""), eid)
                if ev_txt:
                    if target_base in ev_txt or "traceback" in ev_txt.lower() or "error" in ev_txt.lower():
                        has_traceback_prov = True
                        break
                if target_base in proposal.rationale and any(w in proposal.rationale.lower() for w in ["traceback", "error", "exception"]):
                    has_traceback_prov = True
                    break
                if matching_hypo and target_base in matching_hypo.text and any(w in matching_hypo.text.lower() for w in ["traceback", "error", "exception"]):
                    has_traceback_prov = True
                    break
            if not has_traceback_prov and not state.allow_high_risk:
                violations.append(f"P5: Patch type code_api_compat requires traceback provenance citing {f}")
            
        is_denied = False
        for pat in DENY_LIST:
            if re.search(pat, f):
                is_denied = True
                break
        if is_denied:
            risk_class = "deviation"
            if not state.allow_high_risk:
                violations.append(f"P2: Edits to {f} are blocked by deny list")
            else:
                requires_extra_confirm = True

    # P4: Guarded sensitive keys & P6: Value provenance
    for edit in proposal.edits:
        f = edit.file.replace("\\", "/")
        
        if f.endswith(".py"):
            for sk in SENSITIVE_KEYS:
                if re.search(rf"\b{sk}\b\s*=", edit.new) or (edit.old and re.search(rf"\b{sk}\b\s*=", edit.old)):
                    violations.append(f"P4: Sensitive key '{sk}' cannot be modified inside Python code literals (sensitive_key_locked)")

        if proposal.type == "config_value":
            key_name, proposed_raw = parse_config_assignment(edit.new)

            if key_name:
                is_sensitive = get_canonical_key_for_policy(key_name) in SENSITIVE_KEYS or key_name in SENSITIVE_KEYS
                paper_setting = find_paper_setting(state, key_name)

                if is_sensitive:
                    if not paper_setting:
                        violations.append(f"P4: Sensitive key '{key_name}' is not stated in paper settings (sensitive_key_locked)")
                    else:
                        expected_val = paper_setting.value
                        if not values_match(expected_val, proposed_raw):
                            violations.append(
                                f"P4: Sensitive key '{key_name}' can only be modified to match paper value "
                                f"{expected_val} (got {proposed_raw!r}) (sensitive_key_locked)"
                            )
                        else:
                            flags.append("sensitive_key")
                            requires_extra_confirm = True
                else:
                    if paper_setting:
                        expected_val = paper_setting.value
                        if not values_match(expected_val, proposed_raw):
                            violations.append(
                                f"P6: Parameter '{key_name}' does not match paper-stated value "
                                f"{expected_val} (got {proposed_raw!r})"
                            )
                    else:
                        # Non-paper parameter: allowed only if error-driven (§10.7, P6)
                        has_error_provenance = False
                        if matching_hypo and matching_hypo.error_class != "config_mismatch":
                            if matching_hypo.evidence:
                                has_error_provenance = True

                        if has_error_provenance:
                            flags.append("non_paper_param")
                            risk_class = "bug_fix"
                            requires_extra_confirm = True
                        else:
                            violations.append(f"P6: Non-paper key '{key_name}' has no error-driven traceback provenance (no_provenance)")

    # P5: Dependency rule
    if proposal.type == "dependency":
        for edit in proposal.edits:
            for line in edit.new.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if any(bad in line for bad in ["http://", "https://", "git+", "-e", "--index-url", "curl", "|"]):
                    violations.append(f"P5: Dependency edit contains prohibited package URL/option: {line}")
                if "==" not in line and not line.startswith("-r"):
                    violations.append(f"P5: Dependency '{line}' must be pinned with exact '==' version")

    # P10: Dry run syntax parsing
    if workspace:
        for edit in proposal.edits:
            if edit.file.endswith(".py"):
                try:
                    ast.parse(edit.new)
                except Exception as e:
                    violations.append(f"P10: Python syntax error in edit: {e}")
            elif edit.file.endswith(".yaml") or edit.file.endswith(".yml"):
                try:
                    yaml.safe_load(edit.new)
                except Exception as e:
                    violations.append(f"P10: YAML syntax error in edit: {e}")
            elif edit.file.endswith(".json"):
                try:
                    json.loads(edit.new)
                except Exception as e:
                    violations.append(f"P10: JSON syntax error in edit: {e}")

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "risk_class": risk_class,
        "flags": flags,
        "requires_extra_confirm": requires_extra_confirm or (risk_class == "deviation")
    }

def check_patch(arg1, arg2, workspace=None):
    if isinstance(arg1, ProjectState):
        return check(arg1, arg2, workspace)
    return check(arg2, arg1, workspace)

