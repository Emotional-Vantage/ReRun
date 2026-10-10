from pydantic import BaseModel, Field
from typing import Dict, List, Literal, Optional, Any
from agent.state import CriticReview

class CriticAction(BaseModel):
    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)

class CriticPatchReviewOutput(BaseModel):
    action: Optional[CriticAction] = None
    final_review: Optional[CriticReview] = None

class CriticJudgement(BaseModel):
    """
    The judgment the Critic is actually entitled to make.

    Deliberately excludes id, patch_id, round and model. The review used to be requested as a
    full CriticReview, so the model supplied those itself -- including `model`, whose value
    "unavailable" is the arbiter's signal that no independent review happened
    (agent/arbiter.py). A reviewer must not be able to assert its own trustworthiness, so code
    sets those fields from the real provider configuration instead.
    """
    verdict: Literal["SUPPORTED", "NEEDS_REVISION", "BLOCK"]
    checks: Dict[str, bool] = Field(default_factory=dict)
    verified_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    objections: List[str] = Field(default_factory=list)
    required_changes: List[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "low"

class ReportFlag(BaseModel):
    statement_id: str
    issue: Literal["overclaims_causality", "accuses_paper", "claims_unrun_scope", "missing_limitation", "status_inconsistent"]
    suggested_fix: str

class ReportReviewOutput(BaseModel):
    verdict: Literal["CLEAN", "FLAGGED"]
    flags: List[ReportFlag] = Field(default_factory=list)
