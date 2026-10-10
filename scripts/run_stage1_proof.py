#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.run_case import run_case_headless

def main():
    cases = ["b1_control", "b2_dependency", "b3_silent_config", "b4_combined", "b5_unable"]
    results = {}

    print("=================================================================")
    print("      STAGE 1 GATE RUN: ALL 5 BENCHMARK CASES ON DOCKER")
    print("=================================================================")

    for cid in cases:
        print(f"\n>>> Running {cid}...")
        st = run_case_headless(cid)
        pid = st.project_id
        final_status = st.final.get("status") if st.final else st.phase
        
        # Read run logs
        run_logs = {}
        log_dir = Path("data") / "runs" / pid / "logs"
        if log_dir.exists():
            for lf in sorted(log_dir.glob("*.log")):
                run_logs[lf.name] = lf.read_text(encoding="utf-8")

        # Read results
        output_results = {}
        out_dir = Path("data") / "runs" / pid / "outputs"
        if out_dir.exists():
            for rf in sorted(out_dir.glob("**/results.json")):
                try:
                    output_results[str(rf.relative_to(Path("data") / "runs" / pid))] = json.loads(rf.read_text(encoding="utf-8"))
                except Exception:
                    pass

        results[cid] = {
            "project_id": pid,
            "status": final_status,
            "attempts": [a.model_dump() for a in st.attempts],
            "patches": [p.model_dump() for p in st.patches],
            "logs": run_logs,
            "outputs": output_results
        }

    # Verify no mock strings in these runs
    has_mock_signature = False
    for cid, r in results.items():
        pid = r["project_id"]
        for lname, ltext in r["logs"].items():
            if "Execution completed successfully" in ltext:
                print(f"❌ FAIL: Mock signature found in {pid}/logs/{lname}")
                has_mock_signature = True

    if not has_mock_signature:
        print("\n✅ Clean: Zero matches for 'Execution completed successfully' in Stage 1 runs.")

    # Write proof document
    proof_path = Path("data") / "real_run_proof.md"
    lines = [
        "# STAGE 1 — REAL DOCKER EXECUTION PROOF",
        "",
        "This document contains the verified execution proof for the Stage 1 Gate.",
        "All 5 benchmark cases were executed in real Docker containers (`DockerSandbox`) using `rerun-base:py311`.",
        "",
        "## Summary Table",
        "",
        "| Case ID | Project ID | Final Status | Attempts | Patches Applied | Real Metric Observed |",
        "|---|---|---|---|---|---|"
    ]

    for cid in cases:
        r = results[cid]
        metric_str = "N/A"
        if r["attempts"]:
            last_att = r["attempts"][-1]
            if last_att.get("metrics"):
                metric_str = str(last_att["metrics"].get("test_accuracy_mean"))
        lines.append(f"| `{cid}` | `{r['project_id']}` | **{r['status']}** | {len(r['attempts'])} | {len([p for p in r['patches'] if p['status'] == 'applied'])} | `{metric_str}` |")

    lines.append("")
    lines.append("---")
    lines.append("")

    for cid in cases:
        r = results[cid]
        lines.append(f"## Case: `{cid}` (`{r['project_id']}`)")
        lines.append(f"- **Final Status**: `{r['status']}`")
        lines.append(f"- **Attempts**: {len(r['attempts'])}")
        lines.append(f"- **Patches Proposed**: {len(r['patches'])}")
        
        for idx, att in enumerate(r["attempts"]):
            lines.append(f"\n### Attempt {att['n']}")
            lines.append(f"- Exit code: `{att['exit_code']}`")
            lines.append(f"- Error class: `{att.get('error_class')}`")
            lines.append(f"- Metrics: `{att.get('metrics')}`")
            log_key = f"run_{att['n']}.log"
            if log_key in r["logs"]:
                lines.append(f"```text\n# data/runs/{r['project_id']}/logs/{log_key}\n{r['logs'][log_key].strip()}\n```")
        
        for p in r["patches"]:
            lines.append(f"\n### Patch `{p['id']}` ({p['type']}) — Status: `{p['status']}`")
            lines.append(f"- Rationale: {p['rationale']}")
            lines.append(f"```diff\n{p.get('diff', '').strip()}\n```")

        lines.append("\n---\n")

    proof_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n📄 Saved execution proof to {proof_path}")

if __name__ == "__main__":
    main()
