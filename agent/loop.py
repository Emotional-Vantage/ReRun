import os
import json
import time
import shutil
import difflib
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from agent.state import (
    ProjectState, Claim, PaperSetting, Plan, Attempt,
    Hypothesis, PatchProposal, Edit, Approval, CriticReview
)
from agent.config import (
    MAX_STEPS, MAX_PATCHES, CRITIC_ROUNDS_MAX,
    DIAGNOSE_STEPS_MAX, RUN_TIMEOUT_S, INSTALL_TIMEOUT_S
)
from agent.events import emit_event
from agent.llm import call as llm_call
from agent.key_rotator import key_rotator
from agent.solver.schemas import (
    ExtractClaimsOutput, PlanExperimentOutput, DiagnoseStepOutput,
    ProposePatchOutput, WriteReportOutput
)
from agent.solver.prompts import (
    EXTRACT_CLAIMS_PROMPT, PLAN_EXPERIMENT_PROMPT,
    DIAGNOSE_STEP_PROMPT, PROPOSE_PATCH_PROMPT, WRITE_REPORT_PROMPT
)
from agent.critic.review import review_patch
from agent.arbiter import decide_patch
from tools.policy import check as check_policy, compute_fix_signature
from tools.patch import apply_edits_in_memory, make_diff, apply_patch, revert_patch
from tools.compare import compare
from tools.status import compute_status
from tools.errors import classify as classify_error
from tools.config_audit import audit as audit_config
from tools.results import validate_results, load_results
from tools.evidence import record_evidence
from tools.repo import inspect_repository
from tools.paper import extract_text, extract_paper, verify_quote as verify_paper_quote, resolve_setting_key
from tools.preflight import preflight_check
from tools.exec_tools import query_package_index
from tools.report import generate_report
from agent.critic.schemas import ReportReviewOutput
from agent.critic.prompts import CRITIC_REPORT_REVIEW_PROMPT

from sandbox.fake import FakeSandbox
from tools import paths

_OVERRIDE_SANDBOX = None


def get_sandbox():
    """
    Returns the active sandbox: DockerSandbox by default, or FakeSandbox if
    SANDBOX_TYPE=fake and ALLOW_FAKE_SANDBOX=1.

    The choice is delegated to sandbox.fake.get_sandbox rather than repeated here.
    This used to be a second, independent copy of that logic, and the two copies had
    drifted: this one honoured SANDBOX_TYPE=fake without also requiring
    ALLOW_FAKE_SANDBOX=1. Since every orchestrator call site resolves its sandbox
    through this function, the guard that tests/agent/test_default_sandbox_is_real.py
    asserts was absent from the one path that actually runs a reproduction, so a stray
    SANDBOX_TYPE=fake could have produced fabricated run output outside the API (which
    has its own guard in backend/app/main.py:startup_event).

    A selected FakeSandbox is cached, because callers register canned responses on the
    instance and the orchestrator must then see that same object.
    """
    global _OVERRIDE_SANDBOX
    if _OVERRIDE_SANDBOX is not None:
        return _OVERRIDE_SANDBOX

    from sandbox.fake import get_sandbox as select_sandbox
    sb = select_sandbox()
    if isinstance(sb, FakeSandbox):
        _OVERRIDE_SANDBOX = sb
    return sb


def set_sandbox(sb):
    """Override the active sandbox instance (used by test fixtures)."""
    global _OVERRIDE_SANDBOX
    _OVERRIDE_SANDBOX = sb


_REMOTE_SANDBOXES: dict = {}


def get_sandbox_for(state, deps: dict | None = None):
    """
    Pick the sandbox for one project.

    Remote GPU execution is approved per project, not per server, so the choice
    cannot live in SANDBOX_TYPE alone: two projects can legitimately be running
    at once with only one of them paying for a droplet. An injected sandbox
    (tests, fixtures) always wins; after that, a project whose operator approved
    the GPU bill gets a GradientSandbox, cached so repeated runs within the
    project reuse the one droplet instead of renting a new one each time.
    """
    deps = deps or {}
    injected = deps.get("sandbox")
    if injected is not None:
        return injected

    if getattr(state, "remote_approved", False):
        pid = state.project_id
        existing = _REMOTE_SANDBOXES.get(pid)
        if existing is not None:
            return existing
        from sandbox.gradient.sandbox import GradientSandbox

        sb = GradientSandbox()
        _REMOTE_SANDBOXES[pid] = sb
        return sb

    return get_sandbox()


def release_remote_sandbox(project_id: str):
    """Destroy a project's droplet and forget it. Safe to call more than once."""
    sb = _REMOTE_SANDBOXES.pop(project_id, None)
    if sb is not None:
        try:
            sb.kill(project_id)
        except Exception:
            pass
    return sb


def resolve_attempt_log(state: ProjectState, deps: dict, attempt_num: Optional[int] = None) -> Optional[Path]:
    """
    Resolves the path to a specific attempt's execution log.
    Attempt logs are named `<kind>_<n>.log` (e.g., setup_1.log or run_1.log).
    """
    att = (
        state.attempts[attempt_num - 1]
        if attempt_num and 0 < attempt_num <= len(state.attempts)
        else (state.attempts[-1] if state.attempts else None)
    )
    n = att.n if att else (attempt_num or len(state.attempts) or 1)
    is_latest = (attempt_num is None) or (n == (state.attempts[-1].n if state.attempts else n))

    log_dir = paths.logs_dir(state.project_id)
    ws = deps.get("workspace", state.workspace or paths.workspace_path(state.project_id))

    candidates: list = []
    if att and att.log_path:
        candidates.append(Path(att.log_path))

    for base in (log_dir, Path(ws) / "logs"):
        try:
            if base.is_dir():
                candidates.extend(sorted(base.glob(f"*_{n}.log")))
        except Exception:
            pass

    if is_latest:
        if getattr(state, "latest_log_path", None):
            candidates.append(Path(state.latest_log_path))
        if deps.get("latest_log_path"):
            candidates.append(Path(deps["latest_log_path"]))

    candidates.append(log_dir / f"run_{n}.log")
    candidates.append(Path(ws) / "logs" / f"run_{n}.log")

    for c in candidates:
        if c and str(c).strip() and c.is_file():
            return c
    return None


MAX_IDENTICAL_REJECTIONS = 2


def record_rejected_action(state: ProjectState, tool: str, detail: str, guidance: str) -> int:
    """
    Records a refused tool call and returns how many times this exact call has been refused.
    """
    signature = f"{tool}|{detail}"
    for entry in state.rejected_actions:
        if entry.get("signature") == signature:
            entry["count"] = entry.get("count", 1) + 1
            entry["guidance"] = guidance
            return entry["count"]

    state.rejected_actions.append({
        "signature": signature,
        "tool": tool,
        "detail": detail,
        "guidance": guidance,
        "count": 1,
    })
    if len(state.rejected_actions) > 10:
        del state.rejected_actions[:-10]
    return 1


_EDITABLE_SUFFIXES = (".yaml", ".yml", ".json", ".toml", ".txt", ".py", ".cfg", ".ini")


def _editable_file_paths(state: ProjectState, ws: str) -> list:
    """Repository files a patch may target, as real paths relative to the root."""
    paths_list = []
    root = Path(ws)
    for rel in (state.repo_profile or {}).get("tree", []):
        if rel.endswith(_EDITABLE_SUFFIXES) and not rel.startswith((".git/", "outputs/")):
            paths_list.append(rel)
    if not paths_list and root.is_dir():
        for f in root.rglob("*"):
            if f.is_file() and f.suffix in _EDITABLE_SUFFIXES:
                rel = str(f.relative_to(root)).replace("\\", "/")
                if not rel.startswith((".git/", "outputs/", ".site/")):
                    paths_list.append(rel)
    return sorted(set(paths_list))[:60]


def _editable_file_contents(state: ProjectState, ws: str, max_bytes: int = 4000) -> dict:
    """Contents of the files a fix is most likely to touch."""
    root = Path(ws)
    wanted = []
    if state.plan and state.plan.config_file:
        wanted.append(state.plan.config_file)
    for name in ("requirements.txt", "pyproject.toml", "setup.cfg", "environment.yml"):
        wanted.append(name)
    hypo_text = state.hypotheses[-1].text if state.hypotheses else ""
    for rel in _editable_file_paths(state, ws):
        if rel in hypo_text or Path(rel).name in hypo_text:
            wanted.append(rel)
    for rel in _editable_file_paths(state, ws):
        if rel.startswith(("config", "configs/")) and rel not in wanted:
            wanted.append(rel)

    out = {}
    for rel in wanted:
        if rel in out or len(out) >= 6:
            continue
        f = root / rel
        try:
            if f.is_file():
                out[rel] = f.read_text(encoding="utf-8", errors="ignore")[:max_bytes]
        except Exception:
            continue
    return out


def _evidence_ledger_summary(state: ProjectState) -> list:
    """The recorded evidence summary from DB or state."""
    try:
        from backend.app.db import get_all_evidence
        items = get_all_evidence("data/rerun.db", state.project_id)
        if items:
            return items[-12:]
    except Exception:
        pass
    return [{"id": eid, "type": "unknown", "artifact_path": ""} for eid in state.evidence_ids[-12:]]


def finding_signature(tool: str, args: dict) -> str:
    """Identifies a diagnostic call, so the same question is not asked twice."""
    try:
        norm = json.dumps(args or {}, sort_keys=True, separators=(",", ":"))
    except Exception:
        norm = str(args)
    return f"{tool}|{norm}"


def record_finding(state: ProjectState, step: int, tool: str, args: dict, summary: str) -> None:
    """Records what a diagnostic call found."""
    state.diagnostic_findings.append({
        "step": step,
        "tool": tool,
        "signature": finding_signature(tool, args),
        "summary": summary[:600],
    })
    if len(state.diagnostic_findings) > 20:
        del state.diagnostic_findings[:-20]


def has_finding(state: ProjectState, tool: str, args: dict) -> Optional[dict]:
    """The existing finding for this exact call, if already answered."""
    sig = finding_signature(tool, args)
    for f in state.diagnostic_findings:
        if f.get("signature") == sig:
            return f
    return None


def guard_budgets(state: ProjectState) -> bool:
    if state.phase in ("STATUS", "REPORT", "REPORT_REVIEW", "DONE"):
        return False

    steps_used = state.budgets.get("steps_used", 0)
    max_steps = state.budgets.get("max_steps", MAX_STEPS)
    patches_applied = len([p for p in state.patches if p.status == "applied"])

    if steps_used >= int(max_steps * 0.8) and not state.budgets.get("warned_80", False):
        state.budgets["warned_80"] = True
        emit_event(state, "system", "budget_warning", f"Budget warning: {steps_used}/{max_steps} steps used (80%)")

    if steps_used >= max_steps:
        if "budget exhausted: steps limit reached" not in state.unresolved_issues:
            state.unresolved_issues.append("budget exhausted: steps limit reached")
        state.phase = "STATUS"
        return True

    if patches_applied >= MAX_PATCHES:
        if "budget exhausted: max patches applied" not in state.unresolved_issues:
            state.unresolved_issues.append("budget exhausted: max patches applied")
        state.phase = "STATUS"
        return True

    return False


# ----------------- PHASE HANDLERS -----------------

def handle_ingest(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")

    sandbox = get_sandbox_for(state, deps)
    is_real_container = type(sandbox).__name__ == "DockerSandbox"
    state.simulated = not is_real_container
    if state.simulated:
        emit_event(
            state, "system", "simulated_run",
            f"Run is SIMULATED: sandbox is {type(sandbox).__name__}, not a real container"
        )

    ws_path = state.workspace or deps.get("workspace", paths.workspace_path(state.project_id))
    state.workspace = ws_path
    deps["workspace"] = ws_path
    os.makedirs(ws_path, exist_ok=True)

    if state.source == "custom":
        if not any(Path(ws_path).iterdir()) and state.repo_url:
            from tools.ingest import ingest_custom_repo
            ingest_res = ingest_custom_repo(state.repo_url, state.repo_ref, ws_path)
            state.repo_commit = ingest_res.get("commit_sha", state.repo_commit)
    else:
        registry_path = deps.get("registry_path", "benchmarks/registry.json")
        if not os.path.exists(registry_path):
            state.phase = "DONE"
            state.final = {"status": "UNABLE_TO_EXECUTE", "reason": "Registry not found"}
            return

        with open(registry_path, "r", encoding="utf-8") as f:
            reg = json.load(f)

        case_info = next((c for c in reg.get("cases", []) if c["id"] == state.benchmark_id), None)
        if not case_info:
            state.phase = "DONE"
            state.final = {"status": "UNABLE_TO_EXECUTE", "reason": f"Benchmark {state.benchmark_id} not allow-listed"}
            return

        repo_src = case_info.get("repo_path")
        if repo_src:
            repo_src = repo_src.replace("\\", "/")
        if repo_src and os.path.exists(repo_src):
            for item in Path(repo_src).iterdir():
                dest = Path(ws_path) / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

        state.paper_path = case_info.get("paper_path")
        deps["paper_path"] = state.paper_path

    state.phase = "ANALYZE"


def handle_analyze(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")
    ws = deps.get("workspace", paths.workspace_path(state.project_id))
    state.repo_profile = inspect_repository(ws)

    paper_path = state.paper_path or deps.get("paper_path", "benchmarks/papers/digits_softmax.pdf")
    paper_text_data = (
        extract_paper(paper_path)
        if paper_path and os.path.exists(paper_path)
        else {"full_text": "", "marked_text": "", "selected_prompt_text": "", "tables": []}
    )
    prompt_paper_text = paper_text_data.get("selected_prompt_text") or paper_text_data.get("marked_text", "")

    try:
        out = llm_call(
            "solver", "extract_claims",
            {"paper_text": prompt_paper_text},
            ExtractClaimsOutput,
            benchmark_id=state.benchmark_id,
            task_prompt=EXTRACT_CLAIMS_PROMPT
        )
        verified_claims = []
        tables = paper_text_data.get("tables", [])
        for idx, c in enumerate(out.claims):
            c.id = f"C-{idx + 1}"
            if verify_paper_quote(paper_text_data["full_text"], c.source_quote, tables=tables):
                c.quote_verified = True
                c.verified_in_paper = True
                if len(verified_claims) == 0:
                    c.primary = True
                    c.selected = True
                elif len(verified_claims) < 3:
                    c.primary = False
                    c.selected = True
                else:
                    c.primary = False
                    c.selected = False
                verified_claims.append(c)
            else:
                c.quote_verified = False
                c.verified_in_paper = False
                state.unresolved_issues.append(f"Claim {c.id} quote not found in paper text or tables (rejected)")
        state.claims = verified_claims

        verified_settings = []
        for ps in out.paper_settings:
            if verify_paper_quote(paper_text_data["full_text"], ps.source_quote, tables=tables):
                repo_k, status = resolve_setting_key(ps.key, repo_workspace=ws)
                ps.repo_key = repo_k
                ps.alias_validated = (status == "validated_in_repo")
                verified_settings.append(ps)
        state.paper_settings = verified_settings
    except Exception as e:
        emit_event(state, "solver", "error", f"Claim extraction failed: {str(e)}")

    state.phase = "CLAIMS_CONFIRM"
    state.pending = {"kind": "claims", "id": "confirm_claims"}


def handle_claims_confirm(state: ProjectState, deps: dict):
    if not state.command_confirmed:
        state.pending = {"kind": "claims", "id": "confirm_claims"}
        return

    confirmed = [c for c in state.claims if c.confirmed_by_human]
    if not confirmed:
        state.phase = "DONE"
        state.final = {"status": "INCONCLUSIVE", "reason": "no claim confirmed", "after_n_fixes": 0}
        state.pending = None
        return

    state.pending = None
    state.phase = "PLAN"


def handle_plan(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")
    try:
        plan_out = llm_call(
            "solver", "plan_experiment",
            {"claims": [c.model_dump() for c in state.claims], "repo_profile": state.repo_profile},
            PlanExperimentOutput,
            benchmark_id=state.benchmark_id,
            task_prompt=PLAN_EXPERIMENT_PROMPT
        )
        state.plan = Plan(
            command=plan_out.command,
            config_file=plan_out.config_file,
            output_file=plan_out.output_file,
            effective_config_file=plan_out.effective_config_file,
            seeds=plan_out.seeds,
            notes=plan_out.notes
        )
        for c in state.claims:
            if c.id in plan_out.claim_result_keys:
                c.result_key = plan_out.claim_result_keys[c.id]
            elif not c.result_key:
                c.result_key = "test_accuracy_mean" if state.benchmark_id else c.metric
    except Exception as e:
        emit_event(state, "solver", "error", f"Planning failed: {str(e)}")
        state.plan = Plan(
            command="python train.py --config configs/default.yaml",
            config_file="configs/default.yaml",
            output_file="outputs/results.json",
            effective_config_file="outputs/effective_config.json",
            seeds=[0, 1, 2, 3, 4]
        )

    if state.user_command and state.user_command.strip():
        state.plan.command = state.user_command.strip()
        emit_event(state, "human", "command_customized", f"Honored user-customized command: {state.plan.command}")

    state.phase = "PREFLIGHT"


def handle_preflight(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")
    ws = deps.get("workspace", paths.workspace_path(state.project_id))

    from sandbox.limits import get_limits
    limits = get_limits()
    gpu_enabled = limits.gpu_enabled
    if gpu_enabled:
        from sandbox.manager import probe_gpu
        gpu_info = probe_gpu()
    else:
        gpu_info = {
            "usable": False,
            "reason": "GPU mode is disabled (set GPU_ENABLED=true to opt in)",
        }

    res = preflight_check(
        ws, state.repo_profile,
        gpu_enabled=gpu_enabled,
        gpu_usable=bool(gpu_info.get("usable")),
        gpu_detail=str(gpu_info.get("reason", "")),
    )
    state.preflight = res
    if res["blockers"]:
        if "gpu_required" in res["blockers"]:
            """
            A GPU requirement used to end the reproduction here: ReRun would
            report UNABLE_TO_EXECUTE without ever running the paper's code.
            That is a hardware limit, not a verdict about the paper, and it
            rules out most of the literature worth checking.

            When remote execution is configured we price a GPU droplet instead
            and put the cost in front of the operator. Renting hardware is a
            decision with a bill attached, so it gets a human gate of its own
            rather than happening quietly -- the same treatment provisioning
            and patching already get.
            """
            from sandbox.gradient.sandbox import gradient_enabled

            if gradient_enabled() and not state.remote_approved:
                try:
                    from sandbox.gradient.sandbox import plan_remote_execution

                    plan = plan_remote_execution()
                    state.remote_plan = plan
                    est = plan["estimate"]
                    state.pending = {
                        "kind": "remote_gpu",
                        "id": f"gpu_{state.project_id}",
                        "reason": res.get("gpu_detail", "This repository requires a GPU."),
                        "plan": plan,
                    }
                    cost_phrase = (
                        f"about ${est['estimated_usd']:.2f}"
                        if est["estimated_usd"] is not None
                        else "an amount DigitalOcean did not report"
                    )
                    emit_event(
                        state, "system", "remote_gpu_proposed",
                        f"This paper needs a GPU. A {est['size_slug']} droplet in "
                        f"{est['region']} would cost {cost_phrase} for up to "
                        f"{est['budgeted_minutes']} minutes. Awaiting approval.",
                    )
                    return
                except Exception as e:
                    # Could not price it, so we cannot ask for consent to spend.
                    # Fall through to the honest refusal rather than renting
                    # hardware on an unpriced guess.
                    emit_event(
                        state, "system", "warning",
                        f"Remote GPU execution is enabled but could not be planned: {e}",
                    )

            if state.remote_approved:
                # The operator agreed to pay. Drop the blocker that only ever
                # described the local host and carry on into SETUP; the sandbox
                # swap happens in get_sandbox via SANDBOX_TYPE.
                res["blockers"] = [b for b in res["blockers"] if b != "gpu_required"]
                state.preflight = res
                emit_event(
                    state, "system", "remote_gpu_approved",
                    "Running on a remote GPU droplet; results will be marked as "
                    "produced on rented hardware.",
                )
                if not res["blockers"]:
                    pass  # fall through to provisioning below
            else:
                emit_event(
                    state, "system", "gpu_unavailable",
                    f"Repository requires a GPU; sandbox cannot provide one: {res.get('gpu_detail', '')}"
                )

        if res["blockers"]:
            state.phase = "STATUS"
            return

    from tools.provisioning import build_provisioning_plan, download_wheels_for_project
    entry_script = None
    if state.plan and state.plan.command:
        import shlex as _shlex
        for token in _shlex.split(state.plan.command):
            if token.endswith(".py"):
                entry_script = token
                break
    plan = build_provisioning_plan(
        ws, state.project_id,
        triage_report=(state.repo_profile or {}).get("triage"),
        entry_script=entry_script,
    )
    if plan.get("status") == "NEEDS_BUILD":
        state.preflight["blockers"].append("NEEDS_BUILD")
        state.preflight["triage_verdict"] = "NEEDS_BUILD"
        state.provisioning_plan = plan
        emit_event(state, "system", "provisioning_blocked", plan.get("reason", "NEEDS_BUILD: sdist-only package"))
        state.phase = "STATUS"
        return

    is_benchmark = bool(state.benchmark_id and state.benchmark_id.startswith("b"))
    if is_benchmark:
        state.phase = "SETUP"
        return

    if plan.get("needed") and not state.provisioning_approved:
        state.provisioning_plan = plan
        state.pending = {
            "kind": "provisioning",
            "id": f"prov_{state.project_id}",
            "packages": [p["name"] for p in plan["packages"]],
            "details": plan["packages"],
            "python_image": plan["python_image"],
            "warnings": plan.get("warnings", [])
        }
        emit_event(state, "system", "provisioning_proposed", f"Provisioning plan proposed for {len(plan['packages'])} packages. Awaiting approval.")
        return

    if plan.get("needed") and state.provisioning_approved:
        target_whl = paths.wheelhouse_dir(state.project_id)
        res = download_wheels_for_project(
            state.project_id,
            [p["name"] for p in plan["packages"]],
            target_whl,
            python_image=plan["python_image"]
        )
        if res.get("log_path") and os.path.exists(res["log_path"]):
            record_evidence(state, "log", res["log_path"], None, None, "provision_wheels", f"prov_{state.project_id}")
        emit_event(state, "system", "provisioning_done", "Wheel packages downloaded into project wheelhouse")

    state.phase = "SETUP"


def handle_setup(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")
    ws = deps.get("workspace", paths.workspace_path(state.project_id))
    sb = get_sandbox_for(state, deps)

    req_file = Path(ws) / "requirements.txt"
    if req_file.exists():
        exit_code, log_path, res = sb.install(state, ws, len(state.attempts) + 1)
        if log_path:
            deps["latest_log_path"] = log_path
            state.latest_log_path = log_path
        if exit_code != 0:
            emit_event(state, "system", "setup_failed", f"Setup dependency install failed with exit code {exit_code}")
            att = Attempt(
                n=len(state.attempts) + 1,
                patches_applied=[p.id for p in state.patches if p.status == "applied"],
                exit_code=exit_code,
                started_at=time.ctime(),
                ended_at=time.ctime(),
                duration_s=getattr(res, "duration_s", 0.0),
                timed_out=getattr(res, "timed_out", False),
                oom=getattr(res, "oom", False),
                log_path=log_path
            )
            state.attempts.append(att)
            state.phase = "OBSERVE"
            return

    state.phase = "RUN"


def handle_run(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")
    ws = deps.get("workspace", paths.workspace_path(state.project_id))
    sb = get_sandbox_for(state, deps)

    n = len(state.attempts) + 1
    t0 = time.time()
    cmd = state.plan.command if state.plan else "python train.py"

    res = sb.execute(state, ws, cmd, "run", n)
    if hasattr(res, "exit_code"):
        exit_code = res.exit_code
        log_path = res.log_path
        out_dir = res.output_dir
        duration = getattr(res, "duration_s", time.time() - t0)
        timed_out = getattr(res, "timed_out", False)
        oom = getattr(res, "oom", False)
    elif isinstance(res, tuple):
        exit_code, log_path, out_dir = res[:3]
        duration = time.time() - t0
        timed_out = False
        oom = False
    else:
        exit_code, log_path, out_dir = 0, "", ""
        duration = time.time() - t0
        timed_out = False
        oom = False
    deps["latest_log_path"] = log_path
    state.latest_log_path = log_path

    att = Attempt(
        n=n,
        patches_applied=[p.id for p in state.patches if p.status == "applied"],
        exit_code=exit_code,
        started_at=time.ctime(t0),
        ended_at=time.ctime(),
        duration_s=duration,
        timed_out=timed_out,
        oom=oom,
        log_path=log_path
    )
    state.attempts.append(att)
    state.phase = "OBSERVE"


def handle_observe(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")
    latest = state.attempts[-1]
    log_file = resolve_attempt_log(state, deps, latest.n)
    log_text = log_file.read_text(encoding="utf-8", errors="ignore") if log_file else ""

    if latest.exit_code != 0:
        err_info = classify_error(
            log_text,
            attempt=latest,
            exit_code=latest.exit_code,
            oom=latest.oom,
            timed_out=latest.timed_out
        )
        latest.error_class = err_info["error_class"]
        state.phase = "DIAGNOSE"
    else:
        state.phase = "VALIDATE"


def handle_validate(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")
    ws = deps.get("workspace", paths.workspace_path(state.project_id))
    latest = state.attempts[-1]

    from tools.metrics import extract_metric, record_metric_evidence

    metrics_dict = {}
    any_failed = False
    failure_reason = None

    effective_log_path = latest.log_path or deps.get("latest_log_path") or getattr(state, "latest_log_path", None)

    for c in state.claims:
        ext_res = extract_metric(ws, c, log_path=effective_log_path, plan=state.plan)
        if ext_res.success and ext_res.value is not None:
            metrics_dict[c.id] = ext_res.value
            metrics_dict[c.metric] = ext_res.value

            if c.result_key == "test_accuracy_mean" or c.metric == "test_accuracy":
                metrics_dict["test_accuracy_mean"] = ext_res.value
                if ext_res.std is not None:
                    metrics_dict["test_accuracy_std"] = ext_res.std
            if ext_res.std is not None:
                metrics_dict[f"{c.metric}_std"] = ext_res.std
            if ext_res.per_seed:
                metrics_dict[f"{c.metric}_per_seed"] = ext_res.per_seed

            tool_call_id = f"extract_{c.id}_run{latest.n}"
            ev_id = record_metric_evidence(state, ext_res, tool_call_id)
            if ev_id and ev_id not in latest.evidence:
                latest.evidence.append(ev_id)
        else:
            any_failed = True
            failure_reason = ext_res.error
            break

    if not any_failed and metrics_dict:
        latest.metrics = metrics_dict
        state.phase = "COMPARE"
    else:
        latest.error_class = "metric_extraction_failed"
        emit_event(state, "system", "metric_extraction_failed", failure_reason or "Metric extraction failed")
        deps["extraction_error"] = failure_reason
        state.phase = "DIAGNOSE"


def handle_compare(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")
    latest = state.attempts[-1]

    comparisons = []
    all_within = True
    for c in state.claims:
        obs_val = None
        if latest.metrics:
            obs_val = latest.metrics.get(c.id)
            if obs_val is None:
                obs_val = latest.metrics.get(c.metric)
            if obs_val is None and c.result_key:
                obs_val = latest.metrics.get(c.result_key)

        res = compare(c, obs_val)
        comparisons.append(res)
        if not res.get("within_tolerance"):
            all_within = False

    latest.comparison = comparisons
    if all_within:
        state.phase = "STATUS"
    else:
        deps["silent_divergence"] = True
        state.silent_divergence = True
        state.phase = "DIAGNOSE"


def handle_diagnose(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")
    ws = deps.get("workspace", paths.workspace_path(state.project_id))
    state.budgets["steps_used"] = state.budgets.get("steps_used", 0) + 1

    step_num = state.budgets["steps_used"]
    silent_div = deps.get("silent_divergence", False)
    if silent_div and step_num >= 3 and not state.config_diff:
        state.config_diff = audit_config(ws, state.plan, state.paper_settings)
        emit_event(state, "system", "orchestrator_forced", "Safety-net nudge: auto-ran compare_configuration")

    obs_text = "See latest run results/logs"
    latest_log = resolve_attempt_log(state, deps)
    if latest_log:
        try:
            raw_log = latest_log.read_text(encoding="utf-8", errors="ignore").strip()
            lines = raw_log.splitlines()
            obs_text = "\n".join(lines[-40:]) if len(lines) > 40 else raw_log
        except Exception:
            pass

    # Deterministic diagnosis attempted first
    if attempt_deterministic_patch(state, deps, ws, step_num):
        return

    try:
        diag_out = llm_call(
            "solver", "diagnose_step",
            {
                "state_summary": f"Step {step_num}, silent_divergence={silent_div}",
                "observation": obs_text,
                "evidence_ledger": [
                    {"id": e["id"], "type": e.get("type"), "from": e.get("artifact_path", "").split("/")[-1]}
                    for e in _evidence_ledger_summary(state)
                ],
                "how_to_cite_evidence": (
                    "hypotheses[].evidence and propose_patch.evidence must contain ids from "
                    "evidence_ledger above, such as 'E-001'. Never put a tool name, a file "
                    "name or a sentence there. If the ledger is empty, call inspect_file, "
                    "read_logs, inspect_error or compare_configuration first to create one."
                ),
                "findings_so_far": [
                    {"step": f["step"], "tool": f["tool"], "found": f["summary"]}
                    for f in state.diagnostic_findings[-8:]
                ],
                "refused_actions": [
                    {
                        "tool": r.get("tool"),
                        "why_refused": r.get("detail"),
                        "do_this_instead": r.get("guidance"),
                        "times_refused": r.get("count", 1),
                    }
                    for r in state.rejected_actions[-5:]
                ],
                "allowed_tools": [
                    {"name": "inspect_file"},
                    {"name": "search_repository"},
                    {"name": "inspect_repository"},
                    {"name": "read_logs"},
                    {"name": "inspect_error"},
                    {"name": "query_package_index"},
                    {"name": "compare_configuration"},
                    {"name": "run_command"},
                    {"name": "propose_patch"},
                    {"name": "conclude_no_cause"}
                ]
            },
            DiagnoseStepOutput,
            benchmark_id=state.benchmark_id,
            task_prompt=DIAGNOSE_STEP_PROMPT
        )

        cleaned_hypotheses = []
        for h in diag_out.hypotheses:
            valid = [eid for eid in h.evidence if eid in state.evidence_ids]
            invalid = [eid for eid in h.evidence if eid not in state.evidence_ids]
            h.evidence = valid
            if invalid:
                emit_event(
                    state, "solver", "warning",
                    f"Hypothesis {h.id} cited {invalid[:3]} which are not evidence ids; dropped. "
                    f"Recorded evidence ids are {state.evidence_ids or ['(none yet)']}",
                )
            if h.status == "confirmed" and not valid:
                h.status = "open"
                record_rejected_action(
                    state, "confirm_hypothesis",
                    f"Hypothesis {h.id} claimed 'confirmed' with no recorded evidence id",
                    "Cite an id from the evidence ledger, e.g. E-001. Create one first with "
                    "inspect_file, read_logs, inspect_error or compare_configuration, then "
                    "cite the id it returns.",
                )
            cleaned_hypotheses.append(h)
        if cleaned_hypotheses:
            state.hypotheses = cleaned_hypotheses

        action_tool = diag_out.next_action.tool
        action_args = diag_out.next_action.args or {}

        if action_tool not in ("propose_patch", "conclude_no_cause"):
            prior = has_finding(state, action_tool, action_args)
            if prior is not None:
                count = record_rejected_action(
                    state, action_tool,
                    f"{action_tool} was already run at step {prior['step']}",
                    f"You already have this result: {prior['summary']}. "
                    "Use it, choose a different tool, or propose a patch.",
                )
                emit_event(
                    state, "solver", "warning",
                    f"{action_tool} repeated (refused {count}x); its result is already known",
                )
                if count >= MAX_IDENTICAL_REJECTIONS:
                    has_confirmed = any(
                        h.status == "confirmed" and len(h.evidence) >= 1 for h in state.hypotheses
                    )
                    emit_event(
                        state, "system", "action_refused_repeatedly",
                        "Same diagnostic repeated with no new information; moving on",
                    )
                    state.phase = "PATCH_PROPOSE" if has_confirmed else "STATUS"
                    return
                if step_num >= DIAGNOSE_STEPS_MAX:
                    state.phase = "STATUS"
                return

        if action_tool == "propose_patch":
            has_confirmed = any(h.status == "confirmed" and len(h.evidence) >= 1 for h in state.hypotheses)
            if has_confirmed:
                state.phase = "PATCH_PROPOSE"
            else:
                guidance = (
                    "Before proposing a patch, confirm a hypothesis: set its status to "
                    "'confirmed' and cite at least one evidence ID that already exists in the "
                    "ledger. Use inspect_file, read_logs or inspect_error to obtain one."
                )
                count = record_rejected_action(
                    state, "propose_patch",
                    "propose_patch rejected: no confirmed hypothesis with >= 1 evidence ID",
                    guidance
                )
                emit_event(
                    state, "solver", "error",
                    f"propose_patch rejected: no confirmed hypothesis with >= 1 evidence ID "
                    f"(refused {count}x). {guidance}"
                )
                if count >= MAX_IDENTICAL_REJECTIONS:
                    emit_event(
                        state, "system", "action_refused_repeatedly",
                        f"Refused propose_patch {count} times without a confirmed hypothesis; concluding"
                    )
                    state.phase = "STATUS"
                    return
                if step_num >= DIAGNOSE_STEPS_MAX:
                    state.phase = "STATUS"
        elif action_tool == "conclude_no_cause":
            state.phase = "STATUS"
        elif action_tool == "compare_configuration":
            state.config_diff = audit_config(ws, state.plan, state.paper_settings)
            mismatches = [d for d in state.config_diff if d.get("status") == "mismatch"]
            if mismatches:
                summary = "Config mismatches vs the paper: " + "; ".join(
                    f"{d['key']}: paper={d['paper_value']} effective={d['effective_value']}"
                    for d in mismatches[:5]
                )
            elif state.config_diff:
                summary = (
                    f"All {len(state.config_diff)} paper-stated settings match the effective "
                    "configuration. The divergence is not explained by configuration."
                )
            else:
                summary = "No paper-stated settings were available to compare."

            ev_ids = []
            try:
                audit_dir = paths.run_dir(state.project_id)
                audit_dir.mkdir(parents=True, exist_ok=True)
                audit_path = audit_dir / f"config_audit_step{step_num}.json"
                audit_path.write_text(json.dumps(state.config_diff, indent=2), encoding="utf-8")
                ev = record_evidence(
                    state, "config", str(audit_path), None, None,
                    "compare_configuration", f"diag_step_{step_num}",
                )
                ev_ids = [ev.id]
                summary = f"{summary} (recorded as evidence {ev.id})"
            except Exception as e:
                emit_event(state, "system", "warning", f"Could not record config audit evidence: {e}")

            record_finding(state, step_num, action_tool, action_args, summary)
            emit_event(state, "tool", "tool_finished", summary, evidence_ids=ev_ids)
        elif action_tool == "read_logs":
            found = resolve_attempt_log(state, deps, len(state.attempts))
            if found:
                ev = record_evidence(state, "log", str(found), action_args.get("line_start"), action_args.get("line_end"), "read_logs", f"diag_step_{step_num}")
                record_finding(
                    state, step_num, action_tool, action_args,
                    f"Read {found.name} as evidence {ev.id}. Excerpt: {ev.excerpt[:200]}",
                )
                emit_event(state, "tool", "evidence_recorded", f"Read logs ({found.name})", evidence_ids=[ev.id])
            else:
                emit_event(state, "solver", "error", "No log file found")
            if step_num >= DIAGNOSE_STEPS_MAX:
                state.phase = "STATUS"
        elif action_tool == "inspect_error":
            found = resolve_attempt_log(state, deps, len(state.attempts))
            if found:
                ev = record_evidence(state, "log", str(found), None, None, "inspect_error", f"diag_step_{step_num}")
                record_finding(
                    state, step_num, action_tool, action_args,
                    f"Inspected {found.name} as evidence {ev.id}. Excerpt: {ev.excerpt[:200]}",
                )
                emit_event(state, "tool", "evidence_recorded", f"Inspected error in {found.name}", evidence_ids=[ev.id])
            else:
                emit_event(state, "solver", "error", "No log file found")
            if step_num >= DIAGNOSE_STEPS_MAX:
                state.phase = "STATUS"
        elif action_tool == "run_command":
            cmd = action_args.get("command", "")
            if not cmd:
                emit_event(state, "solver", "error", "run_command requires 'command'")
            else:
                cmd_trim = cmd.strip()
                if (
                    cmd_trim.startswith("pip list")
                    or cmd_trim.startswith("pip show")
                    or cmd_trim.startswith("python -c")
                    or cmd_trim.startswith("ls")
                    or cmd_trim.startswith("cat")
                ):
                    sb = get_sandbox_for(state, deps)
                    res = sb.execute(state, ws, cmd, "investigate", step_num)
                    log_p = res.log_path if hasattr(res, "log_path") else (res[1] if isinstance(res, tuple) else "")
                    if log_p and Path(log_p).is_file():
                        ev = record_evidence(state, "log", log_p, None, None, "run_command", f"diag_step_{step_num}")
                        emit_event(state, "tool", "evidence_recorded", f"Ran {cmd}", evidence_ids=[ev.id])
                    else:
                        emit_event(state, "tool", "tool_finished", f"Ran {cmd} but no log produced")
                else:
                    if cmd_trim.startswith(("pip install", "pip3 install", "python -m pip install")):
                        guidance = (
                            "The sandbox runs offline and read-only, so packages cannot be "
                            "installed ad hoc. Propose a patch of type 'dependency' that edits "
                            "requirements.txt with an exact '==' pin instead; the orchestrator "
                            "reinstalls from the offline wheelhouse after the patch is approved."
                        )
                    else:
                        guidance = (
                            "Only read-only inspection commands are permitted: pip list, "
                            "pip show, python -c, ls, cat. Use inspect_file, read_logs or "
                            "search_repository to gather evidence."
                        )
                    count = record_rejected_action(state, "run_command", f"Command not allowed: {cmd}", guidance)
                    emit_event(
                        state, "solver", "error",
                        f"Command not allowed: {cmd} (refused {count}x). {guidance}"
                    )
                    if count >= MAX_IDENTICAL_REJECTIONS:
                        emit_event(
                            state, "system", "action_refused_repeatedly",
                            f"Refused the same command {count} times; moving on instead of re-asking"
                        )
                        has_confirmed = any(
                            h.status == "confirmed" and len(h.evidence) >= 1 for h in state.hypotheses
                        )
                        state.phase = "PATCH_PROPOSE" if has_confirmed else "STATUS"
                        return
            if step_num >= DIAGNOSE_STEPS_MAX:
                state.phase = "STATUS"
        elif action_tool == "inspect_file":
            fpath = action_args.get("file") or action_args.get("path")
            if fpath:
                target = (Path(ws) / fpath).resolve()
                ws_resolved = Path(ws).resolve()
                if ws_resolved in target.parents or target == ws_resolved:
                    if target.is_file():
                        ev = record_evidence(
                            state, "file", str(target),
                            action_args.get("line_start"),
                            action_args.get("line_end"),
                            "inspect_file",
                            f"diag_step_{step_num}"
                        )
                        record_finding(
                            state, step_num, action_tool, action_args,
                            f"Inspected {fpath} as evidence {ev.id}. Excerpt: {ev.excerpt[:200]}",
                        )
                        emit_event(state, "tool", "evidence_recorded", f"Inspected {fpath}", evidence_ids=[ev.id])
            if step_num >= DIAGNOSE_STEPS_MAX:
                state.phase = "STATUS"
        elif action_tool == "search_repository":
            q = action_args.get("query", "")
            matches = []
            if q:
                for f in Path(ws).rglob("*"):
                    if f.is_file() and not any(p in str(f) for p in [".git", "__pycache__", ".site"]):
                        try:
                            txt = f.read_text(encoding="utf-8", errors="ignore")
                            if q in txt:
                                matches.append(str(f.relative_to(ws)))
                        except Exception:
                            pass
            summary = (
                f"search_repository for {q!r} found {len(matches)} file(s): {matches[:5]}"
                if q else "search_repository called without a query"
            )
            record_finding(state, step_num, action_tool, action_args, summary)
            emit_event(state, "tool", "tool_finished", summary)
            if step_num >= DIAGNOSE_STEPS_MAX:
                state.phase = "STATUS"
        elif action_tool == "inspect_repository":
            state.repo_profile = inspect_repository(ws)
            tri = state.repo_profile.get("triage", {})
            summary = (
                f"Repository profile: verdict={tri.get('verdict')}, "
                f"entry points={state.repo_profile.get('entry_points', [])[:4]}, "
                f"unresolved imports={(tri.get('imports') or {}).get('unresolved', [])[:5]}"
            )
            record_finding(state, step_num, action_tool, action_args, summary)
            emit_event(state, "tool", "tool_finished", summary)
            if step_num >= DIAGNOSE_STEPS_MAX:
                state.phase = "STATUS"
        elif action_tool == "query_package_index":
            pkg = action_args.get("package") or action_args.get("name") or ""
            vers = query_package_index(pkg) if pkg else []
            summary = f"query_package_index({pkg!r}) -> versions available offline: {vers}"
            record_finding(state, step_num, action_tool, action_args, summary)
            emit_event(state, "tool", "tool_finished", summary)
            if step_num >= DIAGNOSE_STEPS_MAX:
                state.phase = "STATUS"
        else:
            allowed = [
                "inspect_file", "search_repository", "inspect_repository", "read_logs",
                "inspect_error", "query_package_index", "compare_configuration",
                "run_command", "propose_patch", "conclude_no_cause",
            ]
            count = record_rejected_action(
                state, "unknown_tool", f"{action_tool!r} is not a tool",
                f"Choose exactly one of: {', '.join(allowed)}.",
            )
            emit_event(
                state, "solver", "error",
                f"Unknown tool {action_tool!r} requested (refused {count}x). Allowed: {', '.join(allowed)}",
            )
            if count >= MAX_IDENTICAL_REJECTIONS:
                has_confirmed = any(
                    h.status == "confirmed" and len(h.evidence) >= 1 for h in state.hypotheses
                )
                emit_event(
                    state, "system", "action_refused_repeatedly",
                    "Solver kept requesting an unknown tool; moving on",
                )
                state.phase = "PATCH_PROPOSE" if has_confirmed else "STATUS"
                return
            if step_num >= DIAGNOSE_STEPS_MAX:
                state.phase = "STATUS"
    except Exception as e:
        emit_event(state, "solver", "error", f"Diagnose failed: {str(e)}")
        state.phase = "STATUS"


def attempt_deterministic_patch(state: ProjectState, deps: dict, ws: str, step_num: int) -> bool:
    """
    Build and stage the mechanical fix for this failure, if there is one.
    Returns True when a proposal was staged and the phase advanced to POLICY_CHECK.
    """
    from tools.diagnosis import derive_patch

    latest = state.attempts[-1] if state.attempts else None
    log_file = resolve_attempt_log(state, deps, latest.n if latest else None)
    log_text = ""
    if log_file:
        try:
            log_text = log_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            log_text = ""

    if not state.config_diff and latest is not None and latest.exit_code == 0:
        state.config_diff = audit_config(ws, state.plan, state.paper_settings)

    derived = derive_patch(state, ws, log_text)
    if not derived:
        return False

    edits = derived["edits"]
    signature = compute_fix_signature(edits[0].file, edits[0].op, edits[0].new)
    if signature in state.failed_fixes:
        return False

    evidence_ids = []
    try:
        if derived["type"] == "dependency" and log_file:
            ev = record_evidence(
                state, "log", str(log_file), None, None,
                "deterministic_diagnosis", f"diag_step_{step_num}",
            )
            evidence_ids = [ev.id]
        elif derived["type"] == "config_value":
            target = Path(ws) / edits[0].file
            if target.is_file():
                ev = record_evidence(
                    state, "config", str(target), None, None,
                    "deterministic_diagnosis", f"diag_step_{step_num}",
                )
                evidence_ids = [ev.id]
    except Exception as e:
        emit_event(state, "system", "warning", f"Could not record diagnosis evidence: {e}")
        return False

    if not evidence_ids:
        return False

    hypothesis = derived["hypothesis"]
    hypothesis.evidence = evidence_ids
    state.hypotheses.append(hypothesis)

    try:
        new_texts = apply_edits_in_memory(ws, edits)
        diff_str = make_diff(ws, new_texts)
    except Exception as e:
        emit_event(state, "system", "warning", f"Deterministic patch did not apply cleanly: {e}")
        return False

    proposal = PatchProposal(
        id=f"P-{len(state.patches) + 1}",
        hypothesis_id=hypothesis.id,
        type=derived["type"],
        rationale=derived["rationale"],
        evidence=evidence_ids,
        alternatives_considered=[],
        edits=edits,
        diff=diff_str,
        fix_signature=signature,
    )
    state.patches.append(proposal)
    state.budgets["steps_used"] = state.budgets.get("steps_used", 0) + 1
    emit_event(
        state, "system", "deterministic_diagnosis",
        f"Derived {proposal.id} ({derived['type']}) from evidence {evidence_ids}: {derived['rationale'][:150]}",
        evidence_ids=evidence_ids,
    )
    state.phase = "POLICY_CHECK"
    return True


def handle_patch_propose(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")
    ws = deps.get("workspace", paths.workspace_path(state.project_id))
    state.budgets["steps_used"] = state.budgets.get("steps_used", 0) + 1

    try:
        patch_out = llm_call(
            "solver", "propose_patch",
            {
                "hypothesis": state.hypotheses[-1].model_dump() if state.hypotheses else {},
                "paper_settings": [ps.model_dump() for ps in state.paper_settings],
                "failed_fixes": state.failed_fixes,
                "plan": {
                    "command": state.plan.command if state.plan else None,
                    "config_file": state.plan.config_file if state.plan else None,
                    "output_file": state.plan.output_file if state.plan else None,
                },
                "editable_files": _editable_file_paths(state, ws),
                "file_contents": _editable_file_contents(state, ws),
                "how_to_write_edits": (
                    "Every edit.file must be one of editable_files, written exactly as listed "
                    "and relative to the repository root. For replace_text, edit.old must be "
                    "copied character for character from file_contents and must occur exactly "
                    "once. Cite evidence ids from the ledger, never tool names or prose."
                ),
                "previous_failures": [
                    {"why": r["detail"], "do_this_instead": r["guidance"], "times": r["count"]}
                    for r in state.rejected_actions[-5:]
                    if r.get("tool") in ("propose_patch", "patch_edit")
                ],
            },
            ProposePatchOutput,
            benchmark_id=state.benchmark_id,
            task_prompt=PROPOSE_PATCH_PROMPT
        )

        if not patch_out.edits:
            emit_event(state, "solver", "error", "Patch proposal contained no edits")
            regen_count = state.budgets.get("patch_regenerations", 0)
            if regen_count < 2:
                state.budgets["patch_regenerations"] = regen_count + 1
                state.phase = "PATCH_PROPOSE"
            else:
                state.budgets["patch_regenerations"] = 0
                state.phase = "DIAGNOSE"
            return

        new_texts = apply_edits_in_memory(ws, patch_out.edits)
        diff_str = make_diff(ws, new_texts)
        sig = compute_fix_signature(patch_out.edits[0].file, patch_out.edits[0].op, patch_out.edits[0].new)

        proposal = PatchProposal(
            id=f"P-{len(state.patches) + 1}",
            hypothesis_id=patch_out.hypothesis_id,
            type=patch_out.type,
            rationale=patch_out.rationale,
            evidence=patch_out.evidence,
            alternatives_considered=patch_out.alternatives_considered,
            edits=patch_out.edits,
            diff=diff_str,
            fix_signature=sig
        )
        state.patches.append(proposal)
        state.phase = "POLICY_CHECK"
    except Exception as e:
        count = record_rejected_action(
            state, "patch_edit", f"Patch proposal failed: {str(e)}",
            "Re-read file_contents and copy edit.old exactly from it, or use append_line. "
            "edit.file must be one of editable_files.",
        )
        emit_event(state, "solver", "error", f"Patch proposal failed ({count}x): {str(e)}")
        regen_count = state.budgets.get("patch_regenerations", 0)
        if regen_count < 2 and count < MAX_IDENTICAL_REJECTIONS + 1:
            state.budgets["patch_regenerations"] = regen_count + 1
            state.phase = "PATCH_PROPOSE"
        else:
            state.budgets["patch_regenerations"] = 0
            state.phase = "DIAGNOSE"


def handle_policy_check(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")
    patch = state.patches[-1]
    ws = deps.get("workspace", paths.workspace_path(state.project_id))

    pol_res = check_policy(state, patch, ws)
    patch.policy_result = pol_res
    patch.risk_class = pol_res["risk_class"]

    if not pol_res["passed"]:
        patch.status = "rejected"
        state.failed_fixes.append(patch.fix_signature)
        regen_count = state.budgets.get("patch_regenerations", 0)
        if regen_count < 2:
            state.budgets["patch_regenerations"] = regen_count + 1
            state.phase = "PATCH_PROPOSE"
        else:
            state.budgets["patch_regenerations"] = 0
            for v in pol_res.get("violations", []):
                if "sensitive_key_locked" in v:
                    state.unresolved_issues.append("config mismatch on guarded key not patched (policy)")
            state.phase = "DIAGNOSE"
    else:
        state.budgets["patch_regenerations"] = 0
        state.phase = "CRITIC_REVIEW"


def handle_critic_review(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")
    patch = state.patches[-1]

    round_num = state.budgets.get("critic_revision_round", 0) + 1
    review = review_patch(state, patch, round_num=round_num)
    state.critic_reviews.append(review)
    patch.critic_status = review.verdict.lower()

    decision = decide_patch(patch.policy_result, review, round_num, CRITIC_ROUNDS_MAX)

    if decision.action == "DROP":
        patch.status = "dropped"
        state.failed_fixes.append(patch.fix_signature)
        state.budgets["critic_revision_round"] = 0
        state.phase = "DIAGNOSE"
    elif decision.action == "REVISE":
        patch.status = "dropped"
        state.budgets["critic_revision_round"] = round_num
        emit_event(
            state, "arbiter", "patch_revision_requested",
            f"Critic requested revision of {patch.id} (round {round_num}/{CRITIC_ROUNDS_MAX})"
        )
        state.phase = "PATCH_PROPOSE"
    elif decision.action == "TO_HUMAN":
        app_id = f"A-{len(state.approvals) + 1}"
        state.pending = {"kind": "approval", "id": app_id, "patch_id": patch.id, "banner": decision.banner}
        state.budgets["critic_revision_round"] = 0
        state.phase = "APPROVAL"


def handle_approval(state: ProjectState, deps: dict):
    pending_patch_id = (state.pending or {}).get("patch_id")
    patch = None
    if pending_patch_id:
        patch = next((p for p in state.patches if p.id == pending_patch_id), None)
    if patch is None:
        patch = next(
            (p for p in reversed(state.patches) if p.status in ("proposed", "approved")),
            None
        )
    if patch is None:
        emit_event(
            state, "system", "error",
            f"APPROVAL phase has no patch awaiting a decision (pending patch_id {pending_patch_id!r})"
        )
        state.pending = None
        state.phase = "DIAGNOSE"
        return

    matching_app = next((a for a in state.approvals if a.patch_id == patch.id), None)
    if not matching_app:
        return

    state.pending = None
    if matching_app.decision in ("approve", "edit"):
        state.phase = "PATCH_APPLY"
    else:
        patch.status = "rejected"
        state.failed_fixes.append(patch.fix_signature)
        state.phase = "DIAGNOSE"


def handle_patch_apply(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")
    patch = state.patches[-1]
    ws = deps.get("workspace", paths.workspace_path(state.project_id))
    sb = get_sandbox_for(state, deps)

    success = apply_patch(state, patch, ws)
    if success:
        emit_event(state, "system", "patch_applied", f"Patch {patch.id} applied successfully")

        touched_deps = False
        if hasattr(patch, "edits") and patch.edits:
            for ed in patch.edits:
                filename = getattr(ed, "file", "")
                if "requirements" in filename or filename.endswith((".txt", "setup.py", "pyproject.toml")):
                    touched_deps = True
                    break

        if touched_deps:
            emit_event(state, "system", "install_triggered", "Patch touched dependency files; running install")
            install_exit, install_log, install_res = sb.install(state, ws, len(state.attempts) + 1)
            if install_log:
                deps["latest_log_path"] = install_log
                state.latest_log_path = install_log
            if install_exit != 0:
                emit_event(state, "system", "install_failed", f"Install failed with exit code {install_exit}")
                att = Attempt(
                    n=len(state.attempts) + 1,
                    patches_applied=[p.id for p in state.patches if p.status == "applied"],
                    exit_code=install_exit,
                    started_at=time.ctime(),
                    ended_at=time.ctime(),
                    duration_s=getattr(install_res, "duration_s", 0.0),
                    timed_out=getattr(install_res, "timed_out", False),
                    oom=getattr(install_res, "oom", False),
                    log_path=install_log
                )
                state.attempts.append(att)
                state.phase = "OBSERVE"
                return

        state.phase = "RUN"
    else:
        patch.status = "reverted"
        state.failed_fixes.append(patch.fix_signature)
        state.phase = "DIAGNOSE"


def handle_status(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")
    status_res = compute_status(state)
    state.final = status_res
    state.phase = "REPORT"


def handle_report(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")

    base_report = generate_report(state)
    if state.final is None:
        state.final = {}
    state.final["report"] = base_report
    deps["report"] = base_report

    _safe_save_state(state)

    emit_event(
        state, "system", "report_available",
        "Deterministic report generated and saved; statement enrichment is optional"
    )

    raw_statements = []
    try:
        rep_out = llm_call(
            "solver", "write_report",
            {
                "final_status": state.final,
                "claims": [c.model_dump() for c in state.claims],
                "patches": [p.model_dump() for p in state.patches],
                "unresolved_issues": state.unresolved_issues
            },
            WriteReportOutput,
            benchmark_id=state.benchmark_id,
            max_retries=1,
            task_prompt=WRITE_REPORT_PROMPT
        )
        if rep_out and hasattr(rep_out, "statements"):
            raw_statements = rep_out.statements
            deps["report_statements"] = [s.model_dump() if hasattr(s, "model_dump") else s for s in rep_out.statements]
    except Exception as e:
        emit_event(state, "solver", "warning", f"Write report skipped or failed: {str(e)}")

    report_data = base_report
    if raw_statements:
        report_data = generate_report(state, raw_statements=raw_statements)
        state.final["report"] = report_data
        deps["report"] = report_data

    emit_event(
        state, "solver", "report_ready",
        f"Generated report: {report_data['verification_summary']['summary_text']}",
        payload={"verification": report_data["verification_summary"]}
    )

    state.phase = "REPORT_REVIEW"


def handle_report_review(state: ProjectState, deps: dict):
    emit_event(state, "system", "phase_changed", f"Transitioned to {state.phase}")
    raw_stmts = deps.get("report_statements", [])
    if raw_stmts:
        try:
            rev_out = llm_call(
                "critic", "report_review",
                {"statements": raw_stmts},
                ReportReviewOutput,
                benchmark_id=state.benchmark_id,
                task_prompt=CRITIC_REPORT_REVIEW_PROMPT
            )
            if rev_out and hasattr(rev_out, "flags") and state.final and "report" in state.final:
                state.final["report"]["critic_flags"] = [f.model_dump() for f in rev_out.flags]
                emit_event(state, "critic", "report_reviewed", f"Critic reviewed report: {rev_out.verdict} with {len(rev_out.flags)} flags")
        except Exception:
            pass

    state.phase = "DONE"


PHASE_HANDLERS = {
    "INGEST": handle_ingest,
    "ANALYZE": handle_analyze,
    "CLAIMS_CONFIRM": handle_claims_confirm,
    "PLAN": handle_plan,
    "PREFLIGHT": handle_preflight,
    "SETUP": handle_setup,
    "RUN": handle_run,
    "OBSERVE": handle_observe,
    "VALIDATE": handle_validate,
    "COMPARE": handle_compare,
    "DIAGNOSE": handle_diagnose,
    "PATCH_PROPOSE": handle_patch_propose,
    "POLICY_CHECK": handle_policy_check,
    "CRITIC_REVIEW": handle_critic_review,
    "APPROVAL": handle_approval,
    "PATCH_APPLY": handle_patch_apply,
    "STATUS": handle_status,
    "REPORT": handle_report,
    "REPORT_REVIEW": handle_report_review,
    "DONE": lambda state, deps: None
}


def _safe_save_state(state: ProjectState, status: Optional[str] = None):
    try:
        from backend.app.db import save_project_state
        effective_status = status or (state.final.get("status") if state.final else state.phase)
        save_project_state(
            "data/rerun.db", state.project_id, state.benchmark_id, state.repo_commit,
            effective_status, state
        )
    except Exception:
        pass


def run_project(state: ProjectState, deps: Optional[dict] = None):
    """
    Main orchestrator execution loop.
    Transitions through phases until DONE or paused for a human.
    Persists state after each step and supports clean abort / resumption.
    """
    deps_dict = deps or {}

    if state.workspace:
        deps_dict.setdefault("workspace", state.workspace)
    else:
        state.workspace = deps_dict.get("workspace", paths.workspace_path(state.project_id))
        deps_dict["workspace"] = state.workspace

    if state.latest_log_path and "latest_log_path" not in deps_dict:
        deps_dict["latest_log_path"] = state.latest_log_path
    if state.silent_divergence:
        deps_dict["silent_divergence"] = True

    while state.phase != "DONE":
        if getattr(state, "abort_requested", False):
            state.phase = "DONE"
            if not state.final:
                state.final = {"status": "INCONCLUSIVE", "reason": "aborted by user", "after_n_fixes": len(state.patches)}
            _safe_save_state(state, "DONE")
            return

        if guard_budgets(state):
            _safe_save_state(state)
            continue

        handler = PHASE_HANDLERS.get(state.phase)
        if not handler:
            break
        current_phase = state.phase
        key_rotator.begin_task(f"phase_{current_phase}")
        try:
            handler(state, deps_dict)
        finally:
            key_rotator.end_task()

        if "workspace" in deps_dict:
            state.workspace = deps_dict["workspace"]
        if "latest_log_path" in deps_dict:
            state.latest_log_path = deps_dict["latest_log_path"]
        if deps_dict.get("silent_divergence"):
            state.silent_divergence = True

        if getattr(state, "abort_requested", False):
            state.phase = "DONE"
            if not state.final:
                state.final = {"status": "INCONCLUSIVE", "reason": "aborted by user", "after_n_fixes": len(state.patches)}
            _safe_save_state(state, "DONE")
            return

        _safe_save_state(state)

        if state.pending:
            return
