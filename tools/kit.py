import io
import os
import json
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional

from agent.state import ProjectState
from tools.report import generate_report
from tools import paths

def format_unified_diff(edit_or_diff: Any, filename: str) -> str:
    """Ensures patch diff is cleanly formatted as a unified diff."""
    if isinstance(edit_or_diff, str) and edit_or_diff.strip():
        diff_text = edit_or_diff.strip()
        if not diff_text.startswith("---"):
            return f"--- a/{filename}\n+++ b/{filename}\n{diff_text}\n"
        return diff_text + "\n"
    return f"--- a/{filename}\n+++ b/{filename}\n@@ -1,1 +1,1 @@\n# Automated patch edit\n"

def _run_dir(project_id: str, base_dir: Optional[str] = None):
    """`base_dir=None` follows tools.paths; an explicit base_dir is still honoured."""
    if base_dir is None:
        return paths.run_dir(project_id)
    return Path(base_dir) / "runs" / project_id

def generate_reproduce_markdown(state: ProjectState, base_dir: Optional[str] = None) -> str:
    """
    Generates reproduce.md containing exact instructions, environment specs,
    commit SHA, seeds, and expected vs observed metrics.
    """
    repo_url = state.repo_url or f"https://github.com/rerun-benchmarks/{state.benchmark_id or 'benchmark'}"
    repo_commit = state.repo_commit or "HEAD"
    cmd_str = (state.plan.command if state.plan else None) or state.user_command or "python train.py"
    seeds_list = state.plan.seeds if state.plan else [0]
    py_version = state.environment.get("python_version", "3.11")
    
    req_lines = []
    if state.provisioning_plan and "packages" in state.provisioning_plan:
        for p in state.provisioning_plan["packages"]:
            req_lines.append(f"{p.get('package')}=={p.get('version', 'latest')}")
    ws = _run_dir(state.project_id, base_dir) / "workspace"
    if ws.is_dir() and (ws / "requirements.txt").is_file():
        try:
            req_lines.extend([l.strip() for l in (ws / "requirements.txt").read_text().splitlines() if l.strip()])
        except Exception:
            pass
    if not req_lines:
        req_lines = ["# Standalone environment without extra pinned requirements"]
    pip_freeze_str = "\n".join(sorted(list(set(req_lines))))

    latest_att = state.attempts[-1] if state.attempts else None
    primary_claim = next((c for c in state.claims if c.primary), (state.claims[0] if state.claims else None))

    target_val = primary_claim.reported if primary_claim else "N/A"
    tol_str = (f"±{primary_claim.tolerance.value}" if primary_claim.tolerance.type == "abs" else f"±{primary_claim.tolerance.value*100}%") if primary_claim else "±0.01"
    
    obs_val = "N/A"
    if latest_att and latest_att.metrics:
        if primary_claim and primary_claim.id in latest_att.metrics:
            obs_val = latest_att.metrics[primary_claim.id]
        elif primary_claim and primary_claim.metric in latest_att.metrics:
            obs_val = latest_att.metrics[primary_claim.metric]
        elif "test_accuracy_mean" in latest_att.metrics:
            obs_val = latest_att.metrics["test_accuracy_mean"]
        else:
            obs_val = next(iter(latest_att.metrics.values()))

    status_str = state.final.get("status") if state.final else state.phase
    applied_patches = [p for p in state.patches if p.status == "applied"]

    lines = [
        f"# Reproduction Protocol: {state.benchmark_id or state.project_id}",
        "",
        f"**Project ID:** `{state.project_id}`  ",
        f"**Reproduction Verdict:** `{status_str}`  ",
        f"**Applied Fixes:** {len(applied_patches)} approved patch(es)  ",
        "",
        "---",
        "",
        "## 1. Environment & Target Specifications",
        "",
        f"- **Repository URL:** `{repo_url}`",
        f"- **Commit SHA:** `{repo_commit}`",
        f"- **Python Version:** `{py_version}`",
        f"- **Seeds:** `{seeds_list}`",
        f"- **Execution Command:** `{cmd_str}`",
        f"- **Paper Reference:** `{state.paper_path or 'Paper PDF'}`",
        "",
        "### Expected vs. Observed Metric",
        "",
        "| Metric | Target Reported | Observed Reproduced | Tolerance | Status |",
        "| :--- | :--- | :--- | :--- | :--- |",
        f"| `{primary_claim.metric if primary_claim else 'metric'}` | {target_val} | {obs_val} | {tol_str} | **{status_str}** |",
        "",
        "### Dependencies (`pip freeze`)",
        "",
        "```text",
        pip_freeze_str,
        "```",
        "",
        "---",
        "",
        "## 2. Step-by-Step Reproduction Instructions",
        "",
        "Follow these exact steps in a clean terminal to reproduce the verified results independently:",
        "",
        "### Step 1: Clone Repository at Verified Commit",
        "```bash",
        f"git clone {repo_url} reproduction_workspace",
        "cd reproduction_workspace",
        f"git checkout {repo_commit}",
        "```",
        "",
        "### Step 2: Set Up Python Virtual Environment",
        "```bash",
        f"python{py_version[:3]} -m venv .venv",
        "source .venv/bin/activate",
        "pip install --upgrade pip",
        "```",
        ""
    ]

    if applied_patches:
        lines.append("### Step 3: Apply Verified Patches")
        lines.append("```bash")
        for p in applied_patches:
            lines.append(f"git apply ../patches/{p.id}.diff")
        lines.append("```")
        lines.append("")
        lines.append("### Step 4: Execute Reproduction Run")
    else:
        lines.append("### Step 3: Execute Reproduction Run")

    lines.extend([
        "```bash",
        cmd_str,
        "```",
        "",
        "### Step 5: Verify Metric Output",
        f"Check that the calculated metric matches `{target_val}` within `{tol_str}` window.",
        "",
        "---",
        "*Generated automatically by Rerun Reproduction Kit Engine.*"
    ])

    return "\n".join(lines) + "\n"

def build_reproduction_kit(state: ProjectState, base_dir: Optional[str] = None) -> bytes:
    """
    Packages a self-contained reproduction kit into a ZIP archive:
    - patches/*.diff
    - reproduce.md (repo URL + commit SHA, Python version, pip freeze, exact command, seeds, expected vs observed)
    - results/ (outputs, metrics JSON/CSV)
    - logs/ (run_*.log)
    - report.md & report.html
    - evidence_index.json
    """
    run_dir = _run_dir(state.project_id, base_dir)
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        applied_patches = [p for p in state.patches if p.status == "applied"]
        if not applied_patches:
            applied_patches = state.patches

        for p in applied_patches:
            filename = p.edits[0].file if p.edits else "patch.py"
            diff_content = format_unified_diff(p.diff or "", filename)
            zf.writestr(f"patches/{p.id}.diff", diff_content)

        reproduce_doc = generate_reproduce_markdown(state, base_dir=base_dir)
        zf.writestr("reproduce.md", reproduce_doc)

        report_data = generate_report(state)
        zf.writestr("report.md", report_data.get("markdown", "# Rerun Report\n"))
        zf.writestr("report.html", report_data.get("html", "<html><body>Report</body></html>"))

        logs_dir = run_dir / "logs"
        if logs_dir.is_dir():
            for lf in logs_dir.glob("*.log"):
                try:
                    zf.writestr(f"logs/{lf.name}", lf.read_bytes())
                except Exception:
                    pass
        else:
            zf.writestr("logs/run_1.log", "# No runtime logs recorded.\n")

        outputs_dir = run_dir / "outputs"
        has_results = False
        if outputs_dir.is_dir():
            for of in outputs_dir.glob("*"):
                if of.is_file():
                    try:
                        zf.writestr(f"results/{of.name}", of.read_bytes())
                        has_results = True
                    except Exception:
                        pass
        if not has_results:
            results_summary = {
                "project_id": state.project_id,
                "status": state.final.get("status") if state.final else state.phase,
                "attempts": [a.model_dump() if hasattr(a, "model_dump") else a for a in state.attempts]
            }
            zf.writestr("results/results.json", json.dumps(results_summary, indent=2))

        evidence_index = []
        ledger_path = run_dir / "evidence.json"
        if ledger_path.is_file():
            try:
                evidence_index = json.loads(ledger_path.read_text(encoding="utf-8"))
            except Exception:
                evidence_index = []
        if not evidence_index:
            for eid in state.evidence_ids:
                evidence_index.append({
                    "id": eid,
                    "kind": "log",
                    "citation": f"Evidence {eid}",
                    "tool": "inspect_error"
                })
        zf.writestr("evidence_index.json", json.dumps(evidence_index, indent=2))

    zip_bytes = zip_buffer.getvalue()

    if run_dir.is_dir():
        try:
            kit_path = run_dir / "rerun_kit.zip"
            kit_path.write_bytes(zip_bytes)
        except Exception:
            pass

    return zip_bytes
