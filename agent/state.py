from pydantic import BaseModel, Field, model_validator
from typing import Literal, Any

Status = Literal["REPRODUCED", "PARTIALLY_REPRODUCED", "NOT_REPRODUCED", "UNABLE_TO_EXECUTE", "INCONCLUSIVE"]
Phase = Literal[
    "INGEST", "ANALYZE", "CLAIMS_CONFIRM", "PLAN", "PREFLIGHT", "SETUP", "RUN", "OBSERVE",
    "VALIDATE", "COMPARE", "DIAGNOSE", "PATCH_PROPOSE", "POLICY_CHECK", "CRITIC_REVIEW",
    "APPROVAL", "PATCH_APPLY", "STATUS", "REPORT", "REPORT_REVIEW", "DONE"
]
ErrorClass = Literal[
    "dependency_missing", "dependency_conflict", "path_error", "gpu_required", "network_required",
    "resource_oom", "resource_timeout", "sandbox_permission", "config_error", "numerical_invalid",
    "config_mismatch", "python_version_mismatch", "api_deprecation", "dataset_missing", "device_unavailable",
    "metric_extraction_failed", "unknown"
]
RiskClass = Literal["environment_fix", "bug_fix", "config_alignment", "deviation"]
ProvisioningStatus = Literal["NOT_REQUIRED", "PROPOSED", "APPROVED", "PARTIAL", "FAILED", "COMPLETED"]


class Tolerance(BaseModel):
    type: Literal["abs", "rel"] = "abs"
    value: float = 0.01


class MetricExtraction(BaseModel):
    kind: Literal["results_json", "json_file", "csv_file", "regex_log", "txt_file"] = "results_json"
    path: str | None = None
    key: str | None = None
    regex: str | None = None
    column: str | None = None
    aggregation: Literal["last", "mean_over_seeds", "max", "min", "first"] = "last"


class Claim(BaseModel):
    id: str = "C-1"
    statement: str
    metric: str
    dataset: str | None = None
    reported: float
    tolerance: Tolerance = Field(default_factory=Tolerance)
    result_key: str | None = None
    metric_extraction: MetricExtraction | None = None
    source_ref: str
    source_quote: str
    source_kind: Literal["text", "table"] = "text"
    table_ref: str | None = None
    cell_ref: str | None = None
    quote_verified: bool = True
    verified_in_paper: bool = True
    selected: bool = False
    primary: bool = True
    confirmed_by_human: bool = False


class PaperSetting(BaseModel):
    key: str
    value: Any
    source_ref: str
    source_quote: str
    repo_key: str | None = None
    alias_validated: bool = False


class Plan(BaseModel):
    command: str
    config_file: str | None = None
    output_file: str
    effective_config_file: str | None = None
    seeds: list[int] = Field(default_factory=list)
    notes: str = ""


class Evidence(BaseModel):
    id: str
    type: Literal["log", "file", "config", "package_query", "result", "paper"]
    artifact_path: str
    line_start: int | None = None
    line_end: int | None = None
    sha256: str
    excerpt: str
    created_by_tool: str
    tool_call_id: str
    ts: str


class Hypothesis(BaseModel):
    id: str
    text: str = ""
    status: Literal["open", "confirmed", "refuted"] = "open"
    evidence: list[str] = Field(default_factory=list)
    tested_with: list[str] = Field(default_factory=list)
    error_class: ErrorClass | None = None

    @model_validator(mode="before")
    @classmethod
    def handle_statement_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "statement" in data and "text" not in data:
                data["text"] = data["statement"]
            elif "text" in data and "statement" not in data:
                data["statement"] = data["text"]
        return data

    @property
    def statement(self) -> str:
        return self.text


class Edit(BaseModel):
    file: str
    op: Literal["replace_text", "replace_line", "append_line"]
    old: str | None = None
    new: str
    line: int | None = None
    target: str | None = None


class PatchProposal(BaseModel):
    id: str
    hypothesis_id: str
    type: Literal["dependency", "config_value", "path_string", "code_typo", "code_api_compat"]
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    alternatives_considered: list[dict] = Field(default_factory=list)
    edits: list[Edit] = Field(default_factory=list)
    diff: str | None = None
    risk_class: RiskClass | None = None
    policy_result: dict | None = None
    critic_status: Literal["pending", "supported", "needs_revision", "block", "unavailable"] = "pending"
    status: Literal["proposed", "approved", "rejected", "applied", "reverted", "dropped"] = "proposed"
    approval: str | None = None
    worked: bool | None = None
    fix_signature: str | None = None


class CriticReview(BaseModel):
    id: str
    patch_id: str
    round: int
    verdict: Literal["SUPPORTED", "NEEDS_REVISION", "BLOCK"]
    checks: dict[str, bool] = Field(default_factory=dict)
    verified_evidence: list[dict] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    required_changes: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "high"
    model: str = "gemini"


class Approval(BaseModel):
    id: str
    patch_id: str
    decision: Literal["approve", "reject", "edit"]
    by: str = "user"
    at: str
    comment: str | None = None
    over_critic_objection: bool = False


class Attempt(BaseModel):
    n: int
    patches_applied: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    error_class: ErrorClass | None = None
    metrics: dict[str, Any] | None = None
    comparison: list[dict] | None = None
    evidence: list[str] = Field(default_factory=list)
    outcome: str | None = None
    started_at: str
    ended_at: str | None = None
    duration_s: float | None = None
    timed_out: bool = False
    oom: bool = False
    log_path: str | None = None


class ProjectState(BaseModel):
    project_id: str
    source: Literal["benchmark", "custom"] = "benchmark"
    benchmark_id: str | None = None
    repo_url: str | None = None
    repo_ref: str | None = None
    repo_commit: str = "unknown"
    paper_path: str | None = None
    paper_sha256: str | None = None
    user_command: str | None = None
    run_timeout_s: int | None = None
    simulated: bool = False
    phase: Phase
    budgets: dict = Field(default_factory=dict)
    claims: list[Claim] = Field(default_factory=list)
    paper_settings: list[PaperSetting] = Field(default_factory=list)
    command_confirmed: bool = False
    allow_high_risk: bool = False
    repo_profile: dict = Field(default_factory=dict)
    plan: Plan | None = None
    preflight: dict = Field(default_factory=lambda: {"blockers": []})
    environment: dict = Field(default_factory=dict)
    attempts: list[Attempt] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    patches: list[PatchProposal] = Field(default_factory=list)
    critic_reviews: list[CriticReview] = Field(default_factory=list)
    approvals: list[Approval] = Field(default_factory=list)
    failed_fixes: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    config_diff: list[dict] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    version: int = 1
    workspace: str | None = None
    latest_log_path: str | None = None
    silent_divergence: bool = False
    active_container_name: str | None = None
    abort_requested: bool = False
    provisioning_plan: dict | None = None
    provisioning_approved: bool = False
    provisioning_status: ProvisioningStatus = "NOT_REQUIRED"
    # Remote GPU execution (DigitalOcean Gradient). `remote_plan` holds the
    # priced offer the operator is shown; `remote_receipt` holds what the run
    # actually cost and where it ran, which the report prints verbatim so a
    # reader can tell a locally-sandboxed result from a rented-hardware one.
    remote_plan: dict | None = None
    remote_approved: bool = False
    remote_receipt: dict | None = None
    pending: dict | None = None
    final: dict | None = None
    rejected_actions: list[dict] = Field(default_factory=list)
    diagnostic_findings: list[dict] = Field(default_factory=list)
    llm_call_metadata: list[dict] = Field(default_factory=list)

    @property
    def reviews(self) -> list[CriticReview]:
        return self.critic_reviews

    @reviews.setter
    def reviews(self, val: list[CriticReview]):
        self.critic_reviews = val


class Event(BaseModel):
    id: int
    ts: str
    project_id: str
    step: int
    role: Literal["solver", "critic", "arbiter", "tool", "human", "system"]
    type: str
    tool: str | None = None
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)
    payload: dict = Field(default_factory=dict)
