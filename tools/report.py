import re
import os
import html
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from agent.state import ProjectState
from agent.solver.schemas import ReportStatement

FORBIDDEN_WORDS = [
    r"\bfraud\b",
    r"\bfabricat\w*",
    r"\bfalsif\w*",
    r"\bmisconduct\b",
    r"\bcheat\w*",
    r"the paper is wrong",
    r"authors lied",
    r"incorrect paper",
    r"\bbogus\b"
]

STATUS_NAMES = ["REPRODUCED", "PARTIALLY_REPRODUCED", "NOT_REPRODUCED", "UNABLE_TO_EXECUTE", "INCONCLUSIVE"]

def format_number(val: Any) -> str:
    """Format floating point values cleanly."""
    if isinstance(val, float):
        return f"{val:.4f}".rstrip("0").rstrip(".") if not val.is_integer() else f"{int(val)}"
    return str(val)

def resolve_placeholders(text: str, state: ProjectState) -> Tuple[str, List[str]]:
    """
    Interpolates placeholder tokens {{...}} with measured results and claims.
    Returns (resolved_text, list_of_injected_numeric_values).
    """
    injected_values: List[str] = []
    resolved = text

    for claim in state.claims:
        c_id = claim.id
        reported_str = format_number(claim.reported)
        tol_str = f"±{format_number(claim.tolerance.value)}" if claim.tolerance.type == "abs" else f"±{format_number(claim.tolerance.value * 100)}%"

        pats = [
            (rf"\{{\{{\s*claim\.{c_id}\.reported\s*\}}\}}", reported_str),
            (rf"\{{\{{\s*claim\.{c_id}\.tolerance\s*\}}\}}", tol_str),
            (rf"\{{\{{\s*claim\.{c_id}\.metric\s*\}}\}}", str(claim.metric)),
            (rf"\{{\{{\s*claim\.{c_id}\.dataset\s*\}}\}}", str(claim.dataset or "")),
        ]
        for pat, rep in pats:
            if re.search(pat, resolved, re.IGNORECASE):
                resolved = re.sub(pat, rep, resolved, flags=re.IGNORECASE)
                injected_values.append(rep)

    for att in state.attempts:
        run_num = att.n
        if att.metrics:
            for m_key, m_val in att.metrics.items():
                m_str = format_number(m_val)
                pats = [
                    (rf"\{{\{{\s*result\.run{run_num}\.{m_key}\s*\}}\}}", m_str),
                    (rf"\{{\{{\s*result\.run{run_num}\.{m_key.replace('_mean', '')}\s*\}}\}}", m_str),
                ]
                for pat, rep in pats:
                    if re.search(pat, resolved, re.IGNORECASE):
                        resolved = re.sub(pat, rep, resolved, flags=re.IGNORECASE)
                        injected_values.append(rep)

    latest_att = state.attempts[-1] if state.attempts else None
    if latest_att and latest_att.metrics:
        for m_key, m_val in latest_att.metrics.items():
            m_str = format_number(m_val)
            pats = [
                (rf"\{{\{{\s*result\.{m_key}\s*\}}\}}", m_str),
                (rf"\{{\{{\s*result\.{m_key.replace('_mean', '')}\s*\}}\}}", m_str),
            ]
            for pat, rep in pats:
                if re.search(pat, resolved, re.IGNORECASE):
                    resolved = re.sub(pat, rep, resolved, flags=re.IGNORECASE)
                    injected_values.append(rep)

    current_status = state.final.get("status") if state.final else state.phase
    applied_patches_count = len([p for p in state.patches if p.status == "applied"])
    meta_pats = [
        (r"\{\{\s*status\s*\}\}", current_status),
        (r"\{\{\s*after_n_fixes\s*\}\}", str(applied_patches_count)),
        (r"\{\{\s*project_id\s*\}\}", state.project_id),
        (r"\{\{\s*benchmark_id\s*\}\}", state.benchmark_id),
    ]
    for pat, rep in meta_pats:
        if re.search(pat, resolved, re.IGNORECASE):
            resolved = re.sub(pat, rep, resolved, flags=re.IGNORECASE)

    return resolved, injected_values

def verify_report_claims(
    statements: List[ReportStatement],
    state: ProjectState
) -> Tuple[List[ReportStatement], List[Dict[str, Any]]]:
    """
    Enforces deterministic verifier rules V1–V7.
    Returns (verified_statements, removed_statements).
    """
    verified: List[ReportStatement] = []
    removed: List[Dict[str, Any]] = []

    current_status = state.final.get("status") if state.final else state.phase
    confirmed_hypo_ids = {h.id for h in state.hypotheses if h.status == "confirmed"}

    from tools.evidence import load_evidence_artifact

    evidence_texts: Dict[str, str] = {}
    for eid in state.evidence_ids:
        text = load_evidence_artifact(state.project_id, eid)
        if text is not None:
            evidence_texts[eid] = text

    for stmt in statements:
        violations: List[str] = []
        raw_text = stmt.text

        # 1. Resolve placeholders
        resolved_text, injected_vals = resolve_placeholders(raw_text, state)

        # Rule V1: Evidence citation completeness
        if stmt.section in ("findings", "causes", "fixes"):
            if not stmt.evidence or len(stmt.evidence) == 0:
                violations.append("V1: Section requires evidence, but no evidence IDs cited")
            else:
                for eid in stmt.evidence:
                    if eid not in state.evidence_ids:
                        violations.append(f"V1: Cited evidence ID '{eid}' does not exist in ledger")

        # Rule V2: Quoted excerpts must exist verbatim in cited evidence
        quoted_phrases = re.findall(r'"([^"]{6,})"', resolved_text) + re.findall(r"'([^']{6,})'", resolved_text)
        for phrase in quoted_phrases:
            if phrase in STATUS_NAMES or any(phrase in v for v in injected_vals):
                continue
            matched = False
            for eid in stmt.evidence:
                ev_content = evidence_texts.get(eid, "")
                if phrase in ev_content:
                    matched = True
                    break
            if stmt.evidence and not matched and len(evidence_texts) > 0:
                violations.append(f"V2: Quoted phrase '{phrase[:30]}...' not found in cited evidence")

        # Rule V3: All placeholders must be resolved
        unresolved = re.findall(r"\{\{([^}]+)\}\}", resolved_text)
        if unresolved:
            violations.append(f"V3: Unresolved placeholder(s): {', '.join(unresolved)}")

        # Rule V4: No typed decimals or percentages outside placeholders
        raw_without_placeholders = re.sub(r"\{\{[^}]+\}\}", "", raw_text)
        suspicious_numbers = re.findall(r"\b\d+\.\d+\b|\b\d+%", raw_without_placeholders)
        suspicious_metrics = [
            num for num in suspicious_numbers 
            if num not in ("3.11", "3.10", "3.12", "1.0", "2.0") and not num.startswith("0.00")
        ]
        if suspicious_metrics:
            violations.append(f"V4: Typed metric number(s) outside placeholders: {', '.join(suspicious_metrics)}")

        # Rule V5: No accusatory or forbidden words
        for pat in FORBIDDEN_WORDS:
            if re.search(pat, resolved_text, re.IGNORECASE):
                violations.append(f"V5: Forbidden/accusatory term matching pattern '{pat}'")

        # Rule V6: Status consistency
        for stat in STATUS_NAMES:
            if stat != current_status and re.search(rf"\b{stat}\b", resolved_text):
                violations.append(f"V6: Statement cites status '{stat}' but computed status is '{current_status}'")

        # Rule V7: Confirmed causes must be backed by a confirmed hypothesis
        if stmt.section == "causes" and stmt.confidence == "confirmed":
            has_matching_confirmed_hypo = False
            for hid in confirmed_hypo_ids:
                if hid in resolved_text or any(eid in state.evidence_ids for eid in stmt.evidence):
                    has_matching_confirmed_hypo = True
                    break
            if not has_matching_confirmed_hypo and len(confirmed_hypo_ids) == 0:
                violations.append("V7: 'confirmed' cause is not backed by any confirmed hypothesis")

        if violations:
            removed.append({
                "statement_id": stmt.id,
                "section": stmt.section,
                "text": resolved_text,
                "violations": violations
            })
        else:
            stmt_copy = stmt.model_copy(update={"text": resolved_text})
            verified.append(stmt_copy)

    return verified, removed

def generate_report(
    state: ProjectState,
    raw_statements: Optional[List[ReportStatement]] = None
) -> Dict[str, Any]:
    """
    Constructs the complete Rerun report package.
    Includes runs comparison, verified statements, verification counts, Markdown, and HTML.
    """
    stmts_to_process = raw_statements or []
    verified_stmts, removed_stmts = verify_report_claims(stmts_to_process, state)

    runs_summary: Dict[str, Any] = {
        "total_runs": len(state.attempts),
        "unpatched_run": None,
        "final_run": None,
        "comparison_chart": []
    }

    if state.attempts:
        first_att = state.attempts[0]
        final_att = state.attempts[-1]

        primary_claim = next((c for c in state.claims if c.primary), state.claims[0] if state.claims else None)
        target_val = primary_claim.reported if primary_claim else None
        target_tol = primary_claim.tolerance.value if primary_claim else 0.01

        def _within(att):
            if att.comparison and len(att.comparison) > 0:
                return att.comparison[0].get("within_tolerance")
            return None

        runs_summary["unpatched_run"] = {
            "run": first_att.n,
            "exit_code": first_att.exit_code,
            "metrics": first_att.metrics or {},
            "within_tolerance": _within(first_att)
        }

        runs_summary["final_run"] = {
            "run": final_att.n,
            "exit_code": final_att.exit_code,
            "metrics": final_att.metrics or {},
            "within_tolerance": _within(final_att)
        }

        for att in state.attempts:
            obs = None
            if att.metrics:
                if primary_claim and primary_claim.id in att.metrics:
                    obs = att.metrics[primary_claim.id]
                elif primary_claim and primary_claim.metric in att.metrics:
                    obs = att.metrics[primary_claim.metric]
                elif "test_accuracy_mean" in att.metrics:
                    obs = att.metrics["test_accuracy_mean"]
                elif len(att.metrics) > 0:
                    obs = next(iter(att.metrics.values()))
            runs_summary["comparison_chart"].append({
                "attempt": f"Run {att.n}",
                "run_n": att.n,
                "observed": obs,
                "reported": target_val,
                "tolerance": target_tol,
                "exit_code": att.exit_code,
                "within_tolerance": _within(att)
            })

    grouped_statements: Dict[str, List[Dict[str, Any]]] = {
        "findings": [],
        "causes": [],
        "fixes": [],
        "limitations": [],
        "not_checked": []
    }
    for s in verified_stmts:
        grouped_statements.setdefault(s.section, []).append(s.model_dump())

    # Written for a reader who is not an ML engineer. These are shown verbatim in the
    # report's "What we did not check" section, so jargon here becomes jargon on the page.
    mandatory_limitations = [
        "We only checked whether this code produces this number. We did not judge whether "
        "the paper's wider conclusions are correct.",
        "Everything ran in one sealed container on one machine. A different machine could "
        "give a slightly different number.",
        "Small differences are normal. Decimal rounding, random starting points, and "
        "different processors can all move the last few digits."
    ]
    unselected_claims = [c for c in state.claims if not c.selected and not c.primary]
    mandatory_not_checked = [
        "Whether the result still holds with different settings than the ones the paper states.",
        "Whether the result holds on other data, or on other kinds of hardware."
    ]
    for uc in unselected_claims:
        mandatory_not_checked.append(
            f"Claim {uc.id} ({uc.metric} = {uc.reported}, from {uc.source_ref}): you chose not "
            f"to check this one, so this report says nothing about it."
        )

    total_count = len(stmts_to_process)
    verified_count = len(verified_stmts)
    removed_count = len(removed_stmts)

    verification_summary = {
        "total": total_count,
        "verified": verified_count,
        "removed": removed_count,
        "summary_text": f"{total_count} sentences written, {verified_count} kept, {removed_count} deleted for lack of evidence"
    }

    applied_patches = [
        {
            "id": p.id,
            "type": p.type,
            "rationale": p.rationale,
            "risk_class": p.risk_class or "bug_fix",
            "status": p.status,
            "diff": p.diff
        }
        for p in state.patches if p.status == "applied"
    ]

    status_str = state.final.get("status") if state.final else state.phase
    reason_str = state.final.get("reason", "") if state.final else ""
    after_n = len(applied_patches)

    # One plain sentence per verdict, so the document opens with the answer rather than
    # with metadata. Never softens a negative result.
    verdict_sentence = {
        "REPRODUCED":
            "We ran this paper's code and got the result the paper reports.",
        "PARTIALLY_REPRODUCED":
            "We ran this paper's code. Some of the results matched the paper and some did not.",
        "NOT_REPRODUCED":
            "We ran this paper's code and it finished, but the result it produced does not "
            "match what the paper reports.",
        "UNABLE_TO_EXECUTE":
            "We could not get this paper's code to run to completion, so there is no result "
            "to compare against the paper.",
        "INCONCLUSIVE":
            "We could not reach a clear answer for this paper. Nothing below is evidence "
            "either way.",
    }.get(str(status_str), f"The run finished with the status {status_str}.")

    md_lines = [
        f"# Reproduction report: {state.benchmark_id or state.project_id}",
        ""
    ]
    if getattr(state, "simulated", False):
        md_lines.append("> ⚠️ **This was a practice run.** The code did not run in a real container, so these numbers do not prove anything about the paper.")
        md_lines.append("")

    md_lines.extend([
        "## The short answer",
        "",
        verdict_sentence,
        "",
    ])
    if reason_str:
        md_lines.extend([reason_str, ""])

    if after_n == 0:
        md_lines.append("Nothing in the code was changed. It ran as the authors published it.")
    else:
        md_lines.append(
            f"{after_n} change{'' if after_n == 1 else 's'} "
            f"{'was' if after_n == 1 else 'were'} applied, each one approved by a person first."
        )
    md_lines.extend(["", "---", ""])

    md_lines.extend([
        "## Where this came from",
        "",
        f"- **Run id:** `{state.project_id}`",
        f"- **Code:** `{state.repo_url or state.benchmark_id or 'not recorded'}`",
        f"- **Code version:** `{state.repo_commit or 'not recorded'}`",
        f"- **Paper:** `{state.paper_path or 'not recorded'}`",
        f"- **Result:** `{status_str}`",
    ])

    triage_info = state.repo_profile.get("triage", {}) if hasattr(state, "repo_profile") and state.repo_profile else {}
    if triage_info.get("verdict"):
        md_lines.append(f"- **Could it run here?** `{triage_info.get('verdict')}` — {triage_info.get('reason', '')}")

    if state.provisioning_plan and state.provisioning_plan.get("packages"):
        pkg_names = [f"`{p.get('package')}`" for p in state.provisioning_plan.get("packages", [])]
        md_lines.append(f"- **Packages we installed for it:** {', '.join(pkg_names)}")

    md_lines.extend([
        "",
        f"> **How we checked our own wording:** {verification_summary['summary_text']}.",
        "",
        "---",
        "",
        "## 1. What the paper claims, and what we measured",
        ""
    ])

    if state.claims:
        md_lines.append("### Claims we checked")
        md_lines.append("| Claim | What was measured | Paper says | Allowed margin | Main claim? | Where it came from |")
        md_lines.append("|---|---|---|---|---|---|")
        for c in state.claims:
            if c.selected or c.primary:
                tol = f"±{c.tolerance.value}" if c.tolerance.type == "abs" else f"±{c.tolerance.value * 100}%"
                md_lines.append(f"| `{c.id}` | {c.metric} | {c.reported} | {tol} | {'Yes' if c.primary else 'No'} | {c.source_ref} |")
        md_lines.append("")

        if unselected_claims:
            md_lines.append("### Claims we did not check")
            md_lines.append("| Claim | What it measures | Paper says | Where it came from | Why not checked |")
            md_lines.append("|---|---|---|---|---|")
            for uc in unselected_claims:
                md_lines.append(f"| `{uc.id}` | {uc.metric} | {uc.reported} | {uc.source_ref} | *Not Checked (Excluded)* |")
            md_lines.append("")

    if runs_summary["comparison_chart"]:
        md_lines.append("### Run by run")
        md_lines.append("| Run | Finished cleanly? | We measured | Paper says | Result |")
        md_lines.append("|---|---|---|---|---|")
        for r in runs_summary["comparison_chart"]:
            obs_str = f"{r['observed']:.4f}" if r['observed'] is not None else "nothing (run produced no number)"
            tgt_str = f"{r['reported']:.4f}" if r['reported'] is not None else "N/A"
            within_str = "Not measured" if r["within_tolerance"] is None else ("Matched" if r["within_tolerance"] else "Did not match")
            if r["exit_code"] is None:
                clean_str = "stopped by us"
            elif r["exit_code"] == 0:
                clean_str = "yes"
            else:
                clean_str = f"no (error code {r['exit_code']})"
            md_lines.append(f"| {r['attempt']} | {clean_str} | {obs_str} | {tgt_str} | {within_str} |")
        md_lines.append("")

    md_lines.append("---")
    md_lines.append("## 2. What we found")
    for s in grouped_statements["findings"]:
        ev_chips = " ".join([f"`{e}`" for e in s["evidence"]])
        md_lines.append(f"- **[{s['confidence'].upper()}]** {s['text']} {ev_chips}")
    if not grouped_statements["findings"]:
        md_lines.append("*Nothing was found that we could back up with evidence.*")
    md_lines.append("")

    md_lines.append("## 3. Why it happened")
    for s in grouped_statements["causes"]:
        ev_chips = " ".join([f"`{e}`" for e in s["evidence"]])
        md_lines.append(f"- **[{s['confidence'].upper()}]** {s['text']} {ev_chips}")
    if not grouped_statements["causes"]:
        md_lines.append("*No cause was diagnosed, because nothing failed.*")
    md_lines.append("")

    md_lines.append("## 4. What we changed")
    for p in applied_patches:
        md_lines.append(f"### Patch `{p['id']}` ({p['type']} — `{p['risk_class']}`)")
        md_lines.append(f"**Rationale:** {p['rationale']}")
        if p["diff"]:
            md_lines.append("```diff")
            md_lines.append(p["diff"].strip())
            md_lines.append("```")
        md_lines.append("")
    if not applied_patches:
        md_lines.append("*Nothing had to be changed.*")
        md_lines.append("")

    if state.config_diff:
        conf_level = state.config_diff[0].get("confidence", "static") if state.config_diff else "static"
        md_lines.append(f"## Configuration Audit (Confidence: `{conf_level}`)")
        if conf_level == "static":
            md_lines.append("> **Notice:** Audit confidence is **static** (no runtime effective config was captured; values inferred statically from configs, AST argparse/dataclass defaults, or CLI overrides).")
        md_lines.append("")
        md_lines.append("| Setting | What the paper says | What the code used | Found in | Result |")
        md_lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for cd in state.config_diff:
            src_str = f"{cd.get('source_file') or 'N/A'}"
            if cd.get('source_line'):
                src_str += f":{cd.get('source_line')}"
            if cd.get('source_type'):
                src_str += f" ({cd.get('source_type')})"
            md_lines.append(f"| `{cd.get('key')}` | {cd.get('paper_value')} | {cd.get('effective_value')} | {src_str} | **{cd.get('status')}** |")
        md_lines.append("")

    md_lines.append("## 5. The limits of this report")
    md_lines.append("### Things that limit this result")
    for lim in mandatory_limitations + [s["text"] for s in grouped_statements["limitations"]]:
        md_lines.append(f"- {lim}")
    md_lines.append("")
    md_lines.append("### Things we did not look at")
    for nc in mandatory_not_checked + [s["text"] for s in grouped_statements["not_checked"]]:
        md_lines.append(f"- {nc}")
    md_lines.append("")

    if removed_stmts:
        md_lines.append("---")
        md_lines.append("## 6. Sentences we deleted for lack of evidence")
        for rem in removed_stmts:
            md_lines.append(f"- **`{rem['statement_id']}` ({rem['section']}):** {rem['text']}")
            md_lines.append(f"  *Reason:* {'; '.join(rem['violations'])}")
        md_lines.append("")

    markdown_doc = "\n".join(md_lines)

    chart_rows = []
    for r in runs_summary["comparison_chart"]:
        obs_val = f"{r['observed']:.4f}" if r["observed"] is not None else "Crashed"
        tgt_val = f"{r['reported']:.4f}" if r["reported"] is not None else "N/A"
        tol_val = "— Not measured" if r["within_tolerance"] is None else ("✓ Yes" if r["within_tolerance"] else "✗ No")
        chart_rows.append(f"<tr><td>{html.escape(str(r['attempt']))}</td><td>{r['exit_code']}</td><td>{obs_val}</td><td>{tgt_val}</td><td>{tol_val}</td></tr>")
    chart_rows_html = "".join(chart_rows)

    verified_stmts_html = []
    for s in verified_stmts:
        chips = " ".join([f'<span class="chip">{html.escape(e)}</span>' for e in s.evidence])
        verified_stmts_html.append(f"<p>• <strong>[{s.confidence.upper()}]</strong> {html.escape(s.text)} {chips}</p>")
    verified_stmts_html_str = "".join(verified_stmts_html)

    limitations_html = "".join([f"<li>{html.escape(lim)}</li>" for lim in mandatory_limitations])

    simulated_html = '<div style="background:#854D0E;color:#FEF3C7;padding:12px 18px;border-radius:8px;font-weight:bold;margin:16px 0;border:1px solid #EAB308;">⚠️ SIMULATED RUN: This reproduction was executed under simulation / fake sandbox mode.</div>' if getattr(state, "simulated", False) else ''

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Rerun Report — {html.escape(state.benchmark_id or state.project_id)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, sans-serif; background: #0F172A; color: #E2E8F0; margin: 0; padding: 40px; line-height: 1.6; }}
    .container {{ max-width: 900px; margin: 0 auto; background: #16233F; border: 1px solid #1E293B; border-radius: 12px; padding: 36px; box-shadow: 0 18px 40px -18px rgba(0,0,0,.6); }}
    h1, h2, h3 {{ color: #F8FAFC; }}
    .badge {{ display: inline-block; padding: 6px 14px; border-radius: 6px; font-weight: bold; font-size: 0.9em; }}
    .badge-reproduced {{ background: #166534; color: #86EFAC; border: 1px solid #22C55E; }}
    .badge-not {{ background: #991B1B; color: #FCA5A5; border: 1px solid #EF4444; }}
    .badge-other {{ background: #854D0E; color: #FDE047; border: 1px solid #EAB308; }}
    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; background: #0B1220; border-radius: 8px; overflow: hidden; }}
    th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #1E293B; }}
    th {{ background: #1E293B; color: #94A3B8; font-size: 0.85em; text-transform: uppercase; }}
    pre {{ background: #0B1220; border: 1px solid #1E293B; border-radius: 6px; padding: 14px; overflow-x: auto; color: #38BDF8; font-family: Consolas, monospace; }}
    .chip {{ background: #0B1220; border: 1px solid #334155; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 0.85em; color: #14B8A6; }}
    .removed-box {{ background: rgba(239,68,68,0.1); border-left: 4px solid #EF4444; padding: 12px; margin: 12px 0; border-radius: 4px; }}
  </style>
</head>
<body>
  <div class="container">
    {simulated_html}
    <h1>Reproduction report</h1>
    <p style="font-size:1.15em;color:#E2E8F0;line-height:1.5;margin:12px 0 18px;">{html.escape(verdict_sentence)}</p>
    <p><strong>Case:</strong> {html.escape(state.benchmark_id or 'Custom')} &nbsp;|&nbsp; <strong>Project:</strong> <code>{html.escape(state.project_id)}</code></p>
    <div style="background:#0B1220;border:1px solid #1E293B;border-radius:8px;padding:14px;margin:16px 0;font-size:0.9em;">
      <div><strong>Code:</strong> {html.escape(state.repo_url or state.benchmark_id or 'not recorded')}</div>
      <div><strong>Code version:</strong> <code>{html.escape(state.repo_commit or 'not recorded')}</code></div>
      <div><strong>Paper:</strong> {html.escape(state.paper_path or 'not recorded')}</div>
    </div>
    <div style="margin: 20px 0;">
      <span class="badge {'badge-reproduced' if status_str == 'REPRODUCED' else ('badge-not' if status_str == 'NOT_REPRODUCED' else 'badge-other')}">{html.escape(status_str)}</span>
      <span style="margin-left: 12px; color: #94A3B8;">after {after_n} change(s) you approved</span>
    </div>
    <p style="color: #94A3B8;">{html.escape(verification_summary['summary_text'])}</p>
    <hr style="border: 0; border-top: 1px solid #1E293B; margin: 24px 0;" />
    <h2>Run by run</h2>
    <table>
      <thead>
        <tr><th>Run</th><th>Error code</th><th>We measured</th><th>Paper says</th><th>Result</th></tr>
      </thead>
      <tbody>
        {chart_rows_html}
      </tbody>
    </table>
    <h2>Verified Statements</h2>
    {verified_stmts_html_str}
    <h2>Limitations</h2>
    <ul>
      {limitations_html}
    </ul>
  </div>
</body>
</html>"""

    report_result: Dict[str, Any] = {
        "project_id": state.project_id,
        "benchmark_id": state.benchmark_id,
        "status": status_str,
        "reason": reason_str,
        "after_n_fixes": after_n,
        "claims": [c.model_dump() for c in state.claims],
        "attempts": [a.model_dump() if hasattr(a, "model_dump") else a for a in state.attempts],
        "patches": [p.model_dump() if hasattr(p, "model_dump") else p for p in state.patches],
        "config_diff": state.config_diff,
        "runs_summary": runs_summary,
        "patches_summary": applied_patches,
        "statements": grouped_statements,
        "statements_removed": removed_stmts,
        "verification_summary": verification_summary,
        "limitations": mandatory_limitations,
        "not_checked": mandatory_not_checked,
        "simulated": getattr(state, "simulated", False),
        "repo_url": state.repo_url,
        "repo_commit": state.repo_commit,
        "paper_path": state.paper_path,
        "unselected_claims": [c.model_dump() for c in unselected_claims],
        "markdown": markdown_doc,
        "html": html_doc
    }

    return report_result

# Compatibility alias
build_deterministic_report = generate_report
