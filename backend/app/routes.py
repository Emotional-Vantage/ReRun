import json
import os
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Header, Request, Response
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import uuid
import datetime

from agent.config import MAX_PATCHES, MAX_STEPS
from tools.report import generate_report

from backend.app.models import (
    ProjectCreateRequest, ProjectCreateResponse,
    ClaimsConfirmRequest, ApprovalRequest, HealthResponse,
    ProvisioningApproveRequest
)
from backend.app.db import get_connection, get_project_state, save_project_state
import backend.app.runner as runner

def start_project_worker(project_id: str, allow_resume: bool = False) -> bool:
    return runner.start_project_worker(project_id, allow_resume=allow_resume)

def stop_project_worker(project_id: str):
    return runner.stop_project_worker(project_id)

from backend.app.sse import stream_manager
from agent.state import ProjectState, Approval
from tools import paths

router = APIRouter()

@router.get("/api/health", response_model=HealthResponse)
def health_check():
    import docker
    from pathlib import Path
    
    docker_ok = False
    image_ok = False
    try:
        client = docker.from_env()
        client.ping()
        docker_ok = True
        try:
            client.images.get("rerun-base:py311")
            image_ok = True
        except Exception:
            image_ok = False
    except Exception:
        docker_ok = False

    wheelhouse_ok = len(list(Path("wheelhouse").glob("*.whl"))) > 0
    sandbox_type = os.getenv("SANDBOX_TYPE", "docker")
    
    from agent.config import SOLVER_API_KEY
    llm_primary = bool(SOLVER_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("LLM_MODE") == "replay")
    llm_fallback = bool(os.getenv("FALLBACK_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("LLM_MODE") == "replay")
    
    ok = (docker_ok or sandbox_type == "fake") and (image_ok or sandbox_type == "fake")
    return HealthResponse(
        ok=ok,
        docker=docker_ok,
        image_present=image_ok,
        wheelhouse_ready=wheelhouse_ok,
        sandbox_type=sandbox_type,
        llm_primary=llm_primary,
        llm_fallback=llm_fallback
    )

@router.get("/api/benchmarks")
def get_benchmarks():
    reg_path = "benchmarks/registry.json"
    if not os.path.exists(reg_path):
        return []
    with open(reg_path) as f:
        data = json.load(f)
    out = []
    for c in data.get("cases", []):
        out.append({
            "id": c["id"],
            "title": c.get("title", ""),
            "description": c.get("description", ""),
            "paper_filename": c.get("paper_path", "")
        })
    return out

@router.post("/api/projects", response_model=ProjectCreateResponse)
async def create_project(request: Request):
    content_type = request.headers.get("content-type", "")
    import hashlib
    import shutil
    from pathlib import Path
    
    if "application/json" in content_type:
        try:
            req_data = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed JSON payload")
            
        benchmark_id = req_data.get("benchmark_id")
        if not benchmark_id:
            raise HTTPException(status_code=400, detail="Missing benchmark_id in JSON payload")
            
        allow_high_risk = bool(req_data.get("allow_high_risk", False))
        project_id = f"proj_{uuid.uuid4().hex[:8]}"
        
        paper_path = None
        paper_sha256 = None
        reg_path = "benchmarks/registry.json"
        if os.path.exists(reg_path):
            try:
                with open(reg_path, "r", encoding="utf-8") as f:
                    reg = json.load(f)
                case_info = next((c for c in reg.get("cases", []) if c["id"] == benchmark_id), None)
                if case_info and case_info.get("paper_path"):
                    paper_path = case_info["paper_path"]
                    if os.path.exists(paper_path):
                        paper_sha256 = hashlib.sha256(Path(paper_path).read_bytes()).hexdigest()
            except Exception:
                pass

        state = ProjectState(
            project_id=project_id,
            source="benchmark",
            benchmark_id=benchmark_id,
            repo_commit="unknown",
            paper_path=paper_path,
            paper_sha256=paper_sha256,
            phase="INGEST",
            budgets={"steps_used": 0, "patches_used": 0},
            claims=[],
            paper_settings=[],
            allow_high_risk=allow_high_risk,
            repo_profile={}
        )
        save_project_state("data/rerun.db", project_id, benchmark_id, "unknown", "INGEST", state)
        return ProjectCreateResponse(project_id=project_id)
        
    elif "multipart/form-data" in content_type:
        from agent.config import is_custom_repos_allowed
        if not is_custom_repos_allowed():
            raise HTTPException(
                status_code=403,
                detail="Custom repository execution is currently disabled on this server."
            )
            
        from tools.ingest import ingest_custom_repo, validate_repo_url, RepoIngestError
        from tools.paper import validate_pdf_bytes, PDFValidationError
        
        try:
            form = await request.form()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse multipart form data: {e}")
            
        repo_url = form.get("repo_url")
        repo_ref = form.get("repo_ref")
        if not repo_url or not isinstance(repo_url, str):
            raise HTTPException(status_code=400, detail="Missing required field: repo_url")
            
        try:
            validate_repo_url(repo_url)
        except RepoIngestError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        paper_file = form.get("paper")
        if not paper_file:
            raise HTTPException(status_code=400, detail="Missing required file: paper (PDF)")
            
        try:
            paper_bytes = await paper_file.read()
            pdf_info = validate_pdf_bytes(paper_bytes)
        except PDFValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read paper PDF: {e}")
            
        allow_high_risk = form.get("allow_high_risk") in ("true", "1", True)
        project_id = f"proj_{uuid.uuid4().hex[:8]}"
        
        project_run_dir = paths.run_dir(project_id)
        project_run_dir.mkdir(parents=True, exist_ok=True)
        saved_paper_path = str(project_run_dir / "paper.pdf")
        Path(saved_paper_path).write_bytes(paper_bytes)
        
        ws_path = str(project_run_dir / "workspace")
        try:
            ingest_res = ingest_custom_repo(
                repo_url=repo_url,
                repo_ref=repo_ref if isinstance(repo_ref, str) and repo_ref.strip() else None,
                workspace_path=ws_path
            )
        except RepoIngestError as e:
            shutil.rmtree(project_run_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail=str(e))
            
        commit_sha = ingest_res.get("commit_sha", "unknown")
        state = ProjectState(
            project_id=project_id,
            source="custom",
            benchmark_id="custom",
            repo_url=repo_url,
            repo_ref=repo_ref if isinstance(repo_ref, str) else None,
            repo_commit=commit_sha,
            paper_path=saved_paper_path,
            paper_sha256=pdf_info["sha256"],
            phase="INGEST",
            budgets={"steps_used": 0, "patches_used": 0},
            claims=[],
            paper_settings=[],
            allow_high_risk=allow_high_risk,
            repo_profile={}
        )
        save_project_state("data/rerun.db", project_id, "custom", commit_sha, "INGEST", state)
        return ProjectCreateResponse(project_id=project_id)
        
    else:
        raise HTTPException(
            status_code=400,
            detail="Content-Type must be 'application/json' or 'multipart/form-data'"
        )

@router.post("/api/projects/{id}/start")
def start_project(id: str):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")
    state.phase = "INGEST"
    save_project_state("data/rerun.db", id, state.benchmark_id, state.repo_commit, state.phase, state)
    try:
        start_project_worker(id)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))
    return {"status": "started"}

@router.get("/api/projects/{id}")
def get_project(id: str):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "project_id": state.project_id,
        "source": state.source,
        "benchmark_id": state.benchmark_id,
        "repo_url": state.repo_url,
        "repo_ref": state.repo_ref,
        "paper_path": state.paper_path,
        "user_command": state.user_command,
        "simulated": state.simulated,
        "phase": state.phase,
        "pending": state.pending,
        "budgets": {
            **state.budgets,
            "max_steps": state.budgets.get("max_steps", MAX_STEPS),
            "max_patches": state.budgets.get("max_patches", MAX_PATCHES),
        },
        "attempts": [a.model_dump() for a in state.attempts],
        "patches": [p.model_dump() for p in state.patches],
        "provisioning_plan": state.provisioning_plan,
        "status": state.final.get("status") if state.final else state.phase,
        "report_available": bool(state.final and state.final.get("report")),
        "final": state.final.get("status") and {
            "status": state.final.get("status"),
            "reason": state.final.get("reason", ""),
            "after_n_fixes": state.final.get("after_n_fixes", 0),
        } if state.final else None,
        "unresolved_issues": state.unresolved_issues,
        "preflight": state.preflight,
        "evidence_count": len(state.evidence_ids),
    }

@router.get("/api/projects/{id}/claims-draft")
def get_claims_draft(id: str):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")
    profile = state.repo_profile or {}
    candidates: List[str] = []
    for cmd in profile.get("readme_commands", []) or []:
        if cmd not in candidates:
            candidates.append(cmd)
    for entry in profile.get("entry_points", []) or []:
        cmd = f"python {entry}"
        if cmd not in candidates:
            candidates.append(cmd)

    if state.benchmark_id:
        reg_path = "benchmarks/registry.json"
        if os.path.exists(reg_path):
            try:
                with open(reg_path) as f:
                    reg = json.load(f)
                c_info = next((c for c in reg.get("cases", []) if c["id"] == state.benchmark_id), None)
                if c_info and c_info.get("command") and c_info["command"] not in candidates:
                    candidates.insert(0, c_info["command"])
            except Exception:
                pass

    planned_cmd = state.user_command or (state.plan.command if state.plan else None)
    if not planned_cmd and candidates:
        planned_cmd = candidates[0]

    return {
        "claims": [c.model_dump() for c in state.claims],
        "paper_settings": [ps.model_dump() for ps in state.paper_settings],
        "command": planned_cmd,
        "command_candidates": candidates[:12],
        "extraction_issues": [
            issue for issue in state.unresolved_issues
            if "quote not found" in issue.lower() or "claim" in issue.lower()
        ],
    }

@router.post("/api/projects/{id}/claims/confirm")
def confirm_claims(id: str, req: ClaimsConfirmRequest):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if state.command_confirmed and state.phase != "CLAIMS_CONFIRM":
        return {"status": "already_confirmed"}

    state.claims = req.claims
    state.allow_high_risk = req.allow_high_risk
    if req.command:
        from tools.commands import validate_command
        val_cmd = validate_command(req.command, workspace=state.workspace or paths.workspace_path(id))
        if not val_cmd["valid"]:
            raise HTTPException(status_code=400, detail=val_cmd["reason"])
        state.user_command = req.command
        if state.plan:
            state.plan.command = req.command
    if req.run_timeout_s:
        state.run_timeout_s = min(1800, max(5, int(req.run_timeout_s)))
    state.command_confirmed = True
    
    save_project_state("data/rerun.db", id, state.benchmark_id, state.repo_commit, state.phase, state)
    start_project_worker(id, allow_resume=True)
    return {"status": "confirmed"}

@router.post("/api/projects/{id}/claims/reject")
def reject_claims(id: str):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")
    
    state.phase = "DONE"
    state.final = {"status": "INCONCLUSIVE", "reason": "no claim confirmed", "after_n_fixes": 0}
    state.pending = None
    save_project_state("data/rerun.db", id, state.benchmark_id, state.repo_commit, "INCONCLUSIVE", state)
    return {"status": "rejected"}

@router.get("/api/projects/{id}/provisioning/plan")
def get_provisioning_plan(id: str):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")
    return state.provisioning_plan or {}

@router.post("/api/projects/{id}/provisioning/approve")
def approve_provisioning(id: str, req: ProvisioningApproveRequest):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")

    if not req.confirm:
        raise HTTPException(status_code=400, detail="Provisioning was not confirmed")

    if state.provisioning_approved:
        return {"status": "already_approved"}

    from tools.provisioning import download_wheels_for_project
    from tools.evidence import record_evidence
    from agent.loop import emit_event

    plan = state.provisioning_plan or {}
    packages_to_download = req.packages
    if not packages_to_download:
        packages_to_download = [p["name"] for p in plan.get("packages", [])]

    python_image = plan.get("python_image", "rerun-base:py311")
    target_whl = paths.wheelhouse_dir(id)

    res = download_wheels_for_project(id, packages_to_download, target_whl, python_image=python_image)

    if res.get("log_path") and os.path.exists(res["log_path"]):
        record_evidence(state, "log", res["log_path"], None, None, "provision_wheels", f"prov_{id}")

    state.provisioning_approved = True
    if state.pending and state.pending.get("kind") == "provisioning":
        state.pending = None

    state.phase = "SETUP"
    emit_event(state, "system", "provisioning_approved", f"Approved provisioning for {len(packages_to_download)} packages")
    save_project_state("data/rerun.db", id, state.benchmark_id, state.repo_commit, state.phase, state)

    start_project_worker(id, allow_resume=True)
    return {
        "status": "approved",
        "downloaded_count": res.get("downloaded_count", 0),
        "wheel_files": res.get("wheel_files", [])
    }

@router.post("/api/projects/{id}/provisioning/reject")
def reject_provisioning(id: str):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")

    state.phase = "DONE"
    state.final = {"status": "UNABLE_TO_EXECUTE", "reason": "provisioning rejected by user", "after_n_fixes": 0}
    state.pending = None
    save_project_state("data/rerun.db", id, state.benchmark_id, state.repo_commit, "UNABLE_TO_EXECUTE", state)
    return {"status": "rejected"}

@router.post("/api/projects/{id}/triage")
def run_project_triage(id: str):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")

    from tools.triage import triage_report
    from pathlib import Path
    
    ws = Path(paths.workspace_path(id))
    if not ws.exists():
        if state.benchmark_id:
            reg_path = "benchmarks/registry.json"
            if os.path.exists(reg_path):
                with open(reg_path, "r", encoding="utf-8") as f:
                    reg = json.load(f)
                case_info = next((c for c in reg.get("cases", []) if c["id"] == state.benchmark_id), None)
                if case_info and case_info.get("repo_path") and os.path.exists(case_info["repo_path"]):
                    ws = Path(case_info["repo_path"])
                    
    if not ws.exists():
        raise HTTPException(status_code=400, detail="Project workspace does not exist on disk.")

    report = triage_report(str(ws))
    state.repo_profile["triage"] = report
    save_project_state("data/rerun.db", id, state.benchmark_id, state.repo_commit, state.phase, state)
    return report

@router.get("/api/projects/{id}/events")
def stream_events(id: str, request: Request, last_event_id: Optional[str] = Header(default=None)):
    query_last_id = request.query_params.get("last_event_id") or request.query_params.get("last_id")
    header_last_id = last_event_id or request.headers.get("last-event-id")
    raw_id = query_last_id or header_last_id or "0"
    try:
        last_id = int(raw_id)
    except (ValueError, TypeError):
        last_id = 0
    return StreamingResponse(
        stream_manager.event_generator(id, last_id, request=request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@router.get("/api/projects/{id}/approvals/pending")
def get_pending_approval(id: str):
    state = get_project_state("data/rerun.db", id)
    if not state or not state.pending or state.pending.get("kind") != "approval":
        raise HTTPException(status_code=404, detail="No pending approval")
    
    patch_id = state.pending.get("patch_id")
    patch = next((p for p in state.patches if p.id == patch_id), None)
    if not patch:
        raise HTTPException(status_code=404, detail="Patch not found")
        
    reviews = [r for r in state.critic_reviews if r.patch_id == patch_id]

    policy_result = patch.policy_result or {}
    requires_extra_confirm = bool(
        state.pending.get("banner") or policy_result.get("requires_extra_confirm")
    )

    return {
        "approval_id": state.pending.get("id"),
        "project_id": id,
        "patch": patch.model_dump(),
        "reviews": [r.model_dump() for r in reviews],
        "critic_review": reviews[-1].model_dump() if reviews else None,
        "requires_extra_confirm": requires_extra_confirm,
        "banner": state.pending.get("banner")
    }

def _find_project_by_pending_id(pending_id: str, db_path: str = "data/rerun.db") -> Optional[str]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, state_json FROM projects")
    rows = cursor.fetchall()
    conn.close()

    matches = []
    for proj_id, state_json in rows:
        if not state_json:
            continue
        try:
            pending = json.loads(state_json).get("pending")
        except Exception:
            continue
        if isinstance(pending, dict) and pending.get("id") == pending_id:
            matches.append(proj_id)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Approval id {pending_id!r} is pending in {len(matches)} projects; "
                "name the project (POST /api/projects/{project_id}/approvals/{approval_id})"
            ),
        )
    return None

@router.post("/api/projects/{project_id}/approvals/{approval_id}")
def process_project_approval(project_id: str, approval_id: str, req: ApprovalRequest):
    req.project_id = project_id
    return process_approval(approval_id, req)

@router.post("/api/approvals/{approval_id}")
def process_approval(approval_id: str, req: ApprovalRequest):
    target_project_id = req.project_id or _find_project_by_pending_id(approval_id)
    if not target_project_id:
        raise HTTPException(status_code=404, detail="Approval not found")

    state = get_project_state("data/rerun.db", target_project_id)
    if not state or not state.pending or state.pending.get("id") != approval_id:
        raise HTTPException(status_code=404, detail="Approval not found")
        
    if any(a.id == approval_id for a in state.approvals):
        return {"status": "already_processed"}
        
    patch_id = state.pending.get("patch_id")
    patch = next((p for p in state.patches if p.id == patch_id), None)
    if not patch:
        raise HTTPException(status_code=404, detail="Patch not found")

    if state.pending.get("banner") and req.decision == "approve" and not req.confirm_extra:
        raise HTTPException(status_code=400, detail="Extra confirmation required due to banner")

    if req.decision == "edit":
        if not req.edits:
            raise HTTPException(status_code=400, detail="Edits required when decision is 'edit'")
            
        from agent.state import Edit
        from tools.policy import check as check_policy, compute_fix_signature
        from tools.patch import apply_edits_in_memory, make_diff
        from agent.critic.review import review_patch
        
        parsed_edits = []
        for ed in req.edits:
            if isinstance(ed, dict):
                parsed_edits.append(Edit(**ed))
            elif isinstance(ed, Edit):
                parsed_edits.append(ed)
            else:
                raise HTTPException(status_code=400, detail="Invalid edit format")

        ws = state.workspace or paths.workspace_path(target_project_id)
        candidate_patch = patch.model_copy(deep=True)
        candidate_patch.edits = parsed_edits

        for ed in parsed_edits:
            target_f = os.path.join(ws, ed.file)
            if not os.path.exists(target_f):
                raise HTTPException(status_code=400, detail=f"Target file {ed.file} does not exist")

        try:
            new_contents = apply_edits_in_memory(ws, parsed_edits)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to apply edits: {str(e)}")

        candidate_patch.diff = make_diff(ws, new_contents)

        pol_res = check_policy(state, candidate_patch, ws)
        if not pol_res.get("passed", False):
            raise HTTPException(status_code=400, detail=f"Edited patch failed policy: {pol_res.get('violations', [])}")

        critic_rev = review_patch(state, candidate_patch)
        state.critic_reviews.append(critic_rev)

        patch.edits = parsed_edits
        patch.diff = candidate_patch.diff
        patch.policy_result = pol_res
        patch.fix_signature = compute_fix_signature(parsed_edits[0].file, parsed_edits[0].op, parsed_edits[0].new) if parsed_edits else None
        patch.critic_status = critic_rev.verdict.lower() if hasattr(critic_rev, 'verdict') else 'pending'
        patch.status = "approved"

        appr = Approval(
            id=approval_id,
            patch_id=patch_id,
            decision="edit",
            by="user",
            at=datetime.datetime.now().isoformat(),
            comment=req.comment or "Operator edited patch",
            over_critic_objection=(critic_rev.verdict == "BLOCK")
        )
        patch.approval = appr.id
        state.approvals.append(appr)
        state.pending = None
        state.phase = "PATCH_APPLY"

        save_project_state("data/rerun.db", target_project_id, state.benchmark_id, state.repo_commit, state.phase, state)
        start_project_worker(target_project_id, allow_resume=True)
        return {"status": "applied_and_approved", "patch": patch.model_dump()}

    appr = Approval(
        id=approval_id,
        patch_id=patch_id,
        decision=req.decision,
        by="user",
        at=datetime.datetime.now().isoformat(),
        comment=req.comment,
        over_critic_objection=(state.pending.get("banner") is not None)
    )
    
    state.approvals.append(appr)
    save_project_state("data/rerun.db", target_project_id, state.benchmark_id, state.repo_commit, state.phase, state)
    start_project_worker(target_project_id, allow_resume=True)
    return {"status": "processed"}

@router.get("/api/projects/{id}/evidence")
def list_evidence(id: str):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")

    from backend.app.db import get_all_evidence

    by_id = {}
    ledger_path = str(paths.evidence_ledger_path(id))
    if os.path.exists(ledger_path):
        try:
            with open(ledger_path, "r", encoding="utf-8") as f:
                for entry in json.load(f):
                    if isinstance(entry, dict) and entry.get("id"):
                        by_id[entry["id"]] = {**entry, "available": True, "source": "ledger"}
        except Exception:
            pass

    for entry in get_all_evidence("data/rerun.db", id):
        if entry.get("id"):
            by_id[entry["id"]] = {**entry, "available": True, "source": "db"}

    for eid in state.evidence_ids:
        if eid not in by_id:
            by_id[eid] = {"id": eid, "project_id": id, "available": False}

    return [by_id[k] for k in sorted(by_id)]

@router.get("/api/projects/{id}/evidence/{eid}")
def get_evidence(id: str, eid: str):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")
    from backend.app.db import get_evidence_by_id
    item = get_evidence_by_id("data/rerun.db", id, eid)
    if item:
        return item
    ledger_path = str(paths.evidence_ledger_path(id))
    if os.path.exists(ledger_path):
        try:
            with open(ledger_path, "r", encoding="utf-8") as f:
                ledger = json.load(f)
                for it in ledger:
                    if it.get("id") == eid:
                        return it
        except Exception:
            pass
    raise HTTPException(status_code=404, detail="Evidence not found")

@router.get("/api/projects/{id}/runs/{n}/log")
@router.get("/api/projects/{id}/logs/{n}")
def get_run_log(id: str, n: int, tail: Optional[int] = None):
    from agent.loop import resolve_attempt_log

    log_path = None
    state = get_project_state("data/rerun.db", id)
    if state:
        resolved = resolve_attempt_log(state, {}, n)
        if resolved:
            log_path = str(resolved)

    if log_path is None:
        log_dir = paths.logs_dir(id)
        matches = sorted(log_dir.glob(f"*_{n}.log")) if log_dir.is_dir() else []
        if matches:
            log_path = str(matches[0])

    if not log_path or not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail="Log not found")

    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    if tail and tail > 0:
        lines = lines[-tail:]
    return {"log": "".join(lines)}

@router.get("/api/projects/{id}/report")
def get_report(id: str):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")

    if state.final and "report" in state.final and state.final["report"]:
        return state.final["report"]

    rep = generate_report(state)
    if state.final is None:
        state.final = {}
    state.final["report"] = rep
    save_project_state("data/rerun.db", id, state.benchmark_id, state.repo_commit, state.final.get("status", state.phase), state)
    return rep

@router.get("/api/projects/{id}/report.md")
def get_report_md(id: str):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")
    report = state.final.get("report") if state.final else None
    if not report:
        report = generate_report(state)
    return Response(content=report["markdown"], media_type="text/markdown")

@router.get("/api/projects/{id}/report.html")
def get_report_html(id: str):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")
    report = state.final.get("report") if state.final else None
    if not report:
        report = generate_report(state)
    return Response(content=report["html"], media_type="text/html")

@router.post("/api/projects/{id}/abort")
def abort_project(id: str):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        import sandbox.manager
        sandbox.manager.kill_project_containers(id)
    except Exception:
        pass
    stop_project_worker(id)
    state.abort_requested = True
    state.phase = "DONE"
    state.final = {"status": "INCONCLUSIVE", "reason": "aborted by user", "after_n_fixes": len(state.patches)}
    state.pending = None
    save_project_state("data/rerun.db", id, state.benchmark_id, state.repo_commit, "INCONCLUSIVE", state)
    return {"status": "aborted"}

@router.get("/api/keys/stats")
def get_key_stats():
    from agent.key_rotator import key_rotator
    return key_rotator.get_stats()

@router.delete("/api/projects/{id}")
def delete_project(id: str):
    stop_project_worker(id)
    try:
        import sandbox.manager
        sandbox.manager.kill_project_containers(id)
    except Exception:
        pass

    import shutil
    run_dir = paths.run_dir(id)
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)

    conn = get_connection("data/rerun.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM projects WHERE id = ?", (id,))
    cursor.execute("DELETE FROM events WHERE project_id = ?", (id,))
    cursor.execute("DELETE FROM evidence WHERE project_id = ?", (id,))
    conn.commit()
    conn.close()

    return {"status": "deleted", "id": id}

@router.get("/api/projects/{id}/disk")
def get_project_disk(id: str):
    run_dir = paths.run_dir(id)
    total_bytes = 0
    if run_dir.exists():
        for p in run_dir.rglob("*"):
            if p.is_file():
                try:
                    total_bytes += p.stat().st_size
                except Exception:
                    pass
    return {
        "id": id,
        "disk_bytes": total_bytes,
        "disk_mb": round(total_bytes / (1024 * 1024), 2)
    }

@router.post("/api/admin/kill-switch")
def global_kill_switch():
    import sandbox.manager
    runner.stop_all_workers()
    sandbox.manager.kill_all_rerun_containers()
    return {"status": "all_containers_and_workers_terminated"}

@router.get("/api/projects/{id}/kit")
def download_reproduction_kit(id: str):
    state = get_project_state("data/rerun.db", id)
    if not state:
        raise HTTPException(status_code=404, detail="Project not found")

    from tools.kit import build_reproduction_kit
    zip_bytes = build_reproduction_kit(state)

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="rerun_kit_{id}.zip"'
        }
    )
