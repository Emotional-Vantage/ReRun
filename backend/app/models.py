from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal

from agent.state import Claim

class ProjectCreateRequest(BaseModel):
    benchmark_id: str
    allow_high_risk: bool = False

class ProjectCreateResponse(BaseModel):
    project_id: str

class ClaimsConfirmRequest(BaseModel):
    claims: List[Claim]
    command: Optional[str] = None
    allow_high_risk: bool = False
    run_timeout_s: Optional[int] = None

class ApprovalRequest(BaseModel):
    decision: Literal["approve", "reject", "edit"]
    comment: Optional[str] = None
    edits: Optional[Any] = None
    confirm_extra: bool = False
    # Approval ids are only unique inside one project ("A-1" in every project that reaches
    # its first patch), so the owning project must be named explicitly.
    project_id: Optional[str] = None

class HealthResponse(BaseModel):
    ok: bool
    docker: bool
    image_present: bool = True
    wheelhouse_ready: bool = True
    sandbox_type: str = "docker"
    llm_primary: bool
    llm_fallback: bool

class ProvisioningApproveRequest(BaseModel):
    packages: Optional[List[str]] = None
    confirm: bool = True
