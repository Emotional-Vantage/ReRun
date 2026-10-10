"""
Deterministic diagnosis.

The repair loop used to depend entirely on the Solver choosing the right tool, confirming a
hypothesis and writing an exact patch within DIAGNOSE_STEPS_MAX steps. For faults the system
already classifies that is unnecessary and unreliable: the same benchmark passed on one run
and ran out of steps on the next, even though the evidence needed for the fix was recorded
in both. A missing module named in a traceback, or a configuration key that disagrees with a
value the paper states verbatim, is derivable from evidence rather than a matter of
judgement.

So those two cases are derived here, in code. Everything else still goes to the Solver.

This removes no safeguard. A patch produced here is an ordinary proposal: it carries real
evidence ids, and it still has to pass the policy engine, the Critic, and human approval
before it is applied. What it removes is the chance that a mechanical fix is missed because
the model took a different path.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent.state import Edit, Hypothesis, PatchProposal, ProjectState

# Modules whose import name differs from the package that provides them.
MODULE_TO_PACKAGE = {
    "yaml": "PyYAML",
    "sklearn": "scikit-learn",
    "cv2": "opencv-python",
    "PIL": "pillow",
    "bs4": "beautifulsoup4",
    "dateutil": "python-dateutil",
    "attr": "attrs",
    "skimage": "scikit-image",
}

MISSING_MODULE_RE = re.compile(r"ModuleNotFoundError: No module named ['\"]([\w\.]+)['\"]")


def _wheelhouse_version(package: str, project_id: Optional[str] = None) -> Optional[str]:
    """The exact version available offline, so the pin is real rather than invented."""
    from tools.exec_tools import query_package_index

    versions = query_package_index(package, project_id=project_id)
    return sorted(versions)[-1] if versions else None


def diagnose_missing_dependency(
    state: ProjectState, workspace: str, log_text: str
) -> Optional[Tuple[Hypothesis, List[Edit], str, str]]:
    """
    Declare the dependencies the experiment imports, pinned to versions available offline.

    The named module is the one that stopped the run, but fixing only that module means the
    next run stops on the next one. A repository that declares nothing needs every import it
    actually uses declared, and the patch budget is small, so this proposes one edit
    covering all of them rather than one patch per module.
    """
    match = MISSING_MODULE_RE.search(log_text or "")
    if not match:
        return None

    project_id = getattr(state, "project_id", None)
    failing_module = match.group(1).split(".")[0]

    req = Path(workspace) / "requirements.txt"
    existing = req.read_text(encoding="utf-8") if req.exists() else ""

    # Everything the planned command actually imports, so another experiment's dependencies
    # are not dragged in.
    modules = [failing_module]
    entry_script = None
    if state.plan and state.plan.command:
        import shlex
        entry_script = next(
            (t for t in shlex.split(state.plan.command) if t.endswith(".py")), None
        )
    if entry_script:
        try:
            from tools.provisioning import reachable_third_party_imports
            reachable = reachable_third_party_imports(workspace, entry_script) or set()
            modules.extend(sorted(reachable))
        except Exception:
            pass

    pins, covered = [], []
    for module in dict.fromkeys(modules):
        package = MODULE_TO_PACKAGE.get(module, module)
        if re.search(rf"(?im)^\s*{re.escape(package)}\s*==", existing):
            continue
        version = _wheelhouse_version(package, project_id)
        if not version:
            continue
        line = f"{package}=={version}"
        if line not in pins:
            pins.append(line)
            covered.append(module)

    if not pins:
        return None
    # The module that actually stopped the run must be among them, or this is not the fix.
    failing_package = MODULE_TO_PACKAGE.get(failing_module, failing_module)
    if not any(p.lower().startswith(failing_package.lower() + "==") for p in pins):
        return None

    hypothesis = Hypothesis(
        id=f"H-{len(state.hypotheses) + 1}",
        text=(
            f"The run failed with ModuleNotFoundError for '{failing_module}'. The repository "
            f"does not declare its dependencies, so {', '.join(covered)} are undeclared."
        ),
        status="confirmed",
        evidence=[],           # filled by the caller with the recorded log evidence
        tested_with=["inspect_error"],
        error_class="dependency_missing",
    )
    edits = [Edit(file="requirements.txt", op="append_line", new="\n".join(pins))]
    rationale = (
        f"ModuleNotFoundError: No module named '{failing_module}'. The experiment imports "
        f"{', '.join(covered)}, none of which are declared. Pinned to the versions present "
        f"in the offline wheelhouse: {', '.join(pins)}."
    )
    return hypothesis, edits, rationale, "dependency"


def _find_config_assignment(text: str, key: str) -> Optional[str]:
    """The exact line assigning `key`, so replace_text matches once and only once."""
    for line in text.splitlines():
        if re.match(rf"^\s*{re.escape(key)}\s*:", line):
            return line
    return None


def diagnose_config_mismatch(
    state: ProjectState, workspace: str
) -> Optional[Tuple[Hypothesis, List[Edit], str, str]]:
    """A configuration value that disagrees with a value the paper states verbatim."""
    mismatches = [
        d for d in (state.config_diff or [])
        if d.get("status") == "mismatch" and d.get("effective_value") is not None
    ]
    if not mismatches:
        return None

    ws = Path(workspace)
    config_rel = state.plan.config_file if state.plan and state.plan.config_file else None
    candidates = [config_rel] if config_rel else []
    candidates += ["configs/default.yaml", "config.yaml", "configs/config.yaml"]

    for diff in mismatches:
        paper_key = str(diff.get("key"))
        paper_value = diff.get("paper_value")
        if paper_value is None:
            continue
        setting = next((ps for ps in state.paper_settings if ps.key == paper_key), None)
        if setting is None:
            continue

        for rel in candidates:
            if not rel:
                continue
            path = ws / rel
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for key_variant in {paper_key, paper_key.replace(" ", "_"), setting.repo_key or paper_key}:
                line = _find_config_assignment(text, key_variant)
                if not line:
                    continue
                if text.count(line) != 1:
                    continue
                new_line = f"{key_variant}: {paper_value}"
                if line.strip() == new_line.strip():
                    continue
                hypothesis = Hypothesis(
                    id=f"H-{len(state.hypotheses) + 1}",
                    text=(
                        f"The run completed but missed the reported value. {rel} sets "
                        f"{key_variant} to {diff.get('effective_value')}, while the paper "
                        f"states {paper_value}."
                    ),
                    status="confirmed",
                    evidence=[],
                    tested_with=["compare_configuration"],
                    error_class="config_mismatch",
                )
                edits = [Edit(file=rel, op="replace_text", old=line, new=new_line)]
                rationale = (
                    f"The paper states {paper_key} = {paper_value} "
                    f'("{setting.source_quote[:120]}", {setting.source_ref}). '
                    f"{rel} uses {diff.get('effective_value')}. Aligning the configuration "
                    f"with the paper-stated value."
                )
                return hypothesis, edits, rationale, "config_value"
    return None


def derive_patch(
    state: ProjectState, workspace: str, log_text: str = ""
) -> Optional[Dict[str, Any]]:
    """
    The mechanical fix for this failure, or None when judgement is required.

    Returns a dict with hypothesis, edits, rationale and patch type. The caller records the
    supporting evidence and builds the proposal, so the patch cites real evidence ids.
    """
    for rule in (
        lambda: diagnose_missing_dependency(state, workspace, log_text),
        lambda: diagnose_config_mismatch(state, workspace),
    ):
        result = rule()
        if result is None:
            continue
        hypothesis, edits, rationale, patch_type = result
        return {
            "hypothesis": hypothesis,
            "edits": edits,
            "rationale": rationale,
            "type": patch_type,
        }
    return None
