from typing import Dict, Any, Optional
from pathlib import Path

from agent.state import ProjectState, PatchProposal, CriticReview
from agent.llm import call as default_llm_call
from tools.evidence import load_evidence_artifact
from .schemas import CriticJudgement
from .prompts import CRITIC_PATCH_REVIEW_PROMPT

ALL_CHECKLIST_KEYS = [
    "cause_is_cited_and_exists",
    "evidence_actually_supports_cause",
    "change_is_minimal",
    "files_in_scope",
    "not_metric_chasing",
    "value_has_paper_or_error_provenance",
    "no_change_to_evaluation_or_data_semantics",
    "alternative_explanations_considered",
    "reversible_and_smoke_testable"
]

CRITICAL_CHECKS = [
    "cause_is_cited_and_exists",
    "evidence_actually_supports_cause",
    "not_metric_chasing",
    "no_change_to_evaluation_or_data_semantics",
    "value_has_paper_or_error_provenance"
]

def _active_critic_model() -> str:
    """
    Identifies the model that actually produced the review, for the record. "unavailable" is
    reserved for the failure path below and is never supplied by the model itself.
    """
    import agent.llm as llm
    if getattr(llm, "_ACTIVE_FAKE_LLM", None) is not None:
        return "fake"
    from agent.config import CRITIC_MODEL
    return CRITIC_MODEL or "unknown"

def build_review_packet(state: ProjectState, patch: PatchProposal, workspace: Optional[str] = None) -> Dict[str, Any]:
    """Constructs the raw review packet for the Critic."""
    raw_evidence_slices = []
    for eid in patch.evidence:
        # Resolve through the ledger so the id maps to exactly one artifact.
        text = load_evidence_artifact(state.project_id, eid)
        raw_evidence_slices.append({
            "id": eid,
            "raw_text": text[:2000] if text else "(evidence artifact not found on disk)"
        })

    hypo_text = ""
    for h in state.hypotheses:
        if h.id == patch.hypothesis_id:
            hypo_text = h.text
            break

    return {
        "patch_id": patch.id,
        "type": patch.type,
        "rationale": patch.rationale,
        "hypothesis": hypo_text,
        "edits": [e.model_dump() for e in patch.edits],
        "diff": patch.diff,
        "alternatives_considered": patch.alternatives_considered,
        "paper_settings": [ps.model_dump() for ps in state.paper_settings],
        "raw_evidence_slices": raw_evidence_slices,
        "config_diff": state.config_diff
    }

def review_patch(
    state: ProjectState,
    patch: PatchProposal,
    round_num: int = 1,
    llm_call_fn = None
) -> CriticReview:
    """
    Executes the Critic review process.
    Permits up to 3 extra read-only fetches, checks quotes, and enforces verdict overrides.
    """
    call_fn = llm_call_fn or default_llm_call
    packet = build_review_packet(state, patch)

    try:
        # The model returns only its judgment; identity and provenance are set here so a
        # reviewer cannot report its own round number or claim to be "unavailable".
        judgement = call_fn(
            "critic", "patch_review", packet, CriticJudgement,
            task_prompt=CRITIC_PATCH_REVIEW_PROMPT
        )
        review = CriticReview(
            id=f"R-{len(state.critic_reviews) + 1}",
            patch_id=patch.id,
            round=round_num,
            verdict=judgement.verdict,
            checks=dict(judgement.checks),
            verified_evidence=list(judgement.verified_evidence),
            objections=list(judgement.objections),
            required_changes=list(judgement.required_changes),
            confidence=judgement.confidence,
            model=_active_critic_model(),
        )
        # An omitted check is a failed check.
        for k in ALL_CHECKLIST_KEYS:
            if k not in review.checks:
                review.checks[k] = False
    except Exception as e:
        # Critic unavailable
        return CriticReview(
            id=f"R-{len(state.critic_reviews) + 1}",
            patch_id=patch.id,
            round=round_num,
            verdict="BLOCK",
            checks={k: False for k in ALL_CHECKLIST_KEYS},
            verified_evidence=[],
            objections=[f"Critic call failed: {str(e)}"],
            required_changes=[],
            confidence="low",
            model="unavailable"
        )

    # Code-level verification of raw quotes in verified_evidence. The quote must appear in the
    # one artifact the ledger records for that id, not in any file sharing the id prefix.
    for item in review.verified_evidence:
        eid = item.get("id")
        found_quote = item.get("what_i_found", "")
        if not found_quote:
            continue
        content = load_evidence_artifact(state.project_id, eid) or ""
        if found_quote.strip() not in content:
            # Quote was not actually in the artifact!
            review.checks["evidence_actually_supports_cause"] = False

    # Code-enforced verdict override (§9.3)
    critical_failed = any(not review.checks.get(chk, False) for chk in CRITICAL_CHECKS)
    other_failed = any(not val for k, val in review.checks.items() if k not in CRITICAL_CHECKS)

    if critical_failed:
        if round_num == 1 and review.verdict == "SUPPORTED":
            review.verdict = "NEEDS_REVISION"
        else:
            review.verdict = "BLOCK"
    elif other_failed:
        review.verdict = "NEEDS_REVISION"
    else:
        review.verdict = "SUPPORTED"

    return review
