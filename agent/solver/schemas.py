from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal, Any
from agent.state import Claim, PaperSetting, Hypothesis, Edit

class ExtractClaimsOutput(BaseModel):
    claims: List[Claim]
    paper_settings: List[PaperSetting]
    ambiguities: List[str] = Field(default_factory=list)

class PlanExperimentOutput(BaseModel):
    command: str
    config_file: Optional[str] = None
    output_file: str = "outputs/results.json"
    effective_config_file: Optional[str] = "outputs/effective_config.json"
    seeds: List[int]
    claim_result_keys: Dict[str, str] = Field(default_factory=dict)
    notes: str = ""

class NextAction(BaseModel):
    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)

class DiagnoseStepOutput(BaseModel):
    reason: str
    hypotheses: List[Hypothesis]
    next_action: NextAction

class ProposePatchOutput(BaseModel):
    hypothesis_id: str
    type: Literal["dependency", "config_value", "path_string", "code_typo", "code_api_compat"]
    rationale: str
    evidence: List[str]
    alternatives_considered: List[Dict[str, Any]] = Field(default_factory=list)
    edits: List[Edit]

class ReportStatement(BaseModel):
    id: str
    section: Literal["findings", "causes", "fixes", "limitations", "not_checked"]
    kind: str
    confidence: Literal["confirmed", "likely", "unverified"]
    text: str
    evidence: List[str] = Field(default_factory=list)

class WriteReportOutput(BaseModel):
    statements: List[ReportStatement]
