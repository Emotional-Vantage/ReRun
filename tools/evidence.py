import hashlib
import json
import logging
import os
import shutil
import datetime
import re
from pathlib import Path
from agent.state import Evidence
from tools import paths

logger = logging.getLogger(__name__)

def _project_run_dir(project_id, data_dir=None):
    """
    Where this project's evidence lives.
    Follows `tools.paths.run_dir(project_id)` by default.
    """
    if data_dir is None:
        return paths.run_dir(project_id)
    p = Path(data_dir)
    if (p / "runs" / project_id).exists():
        return p / "runs" / project_id
    if (p / project_id).exists():
        return p / project_id
    if (p / "runs").exists():
        return p / "runs" / project_id
    if p.name == "runs":
        return p / project_id
    return p / "runs" / project_id

def record_evidence(project_state, type_, source_path, line_start, line_end, tool, tool_call_id, data_dir=None):
    ev_id = f"E-{len(project_state.evidence_ids) + 1:03d}"
    
    source_p = Path(source_path)
    basename = source_p.name
    p_run_dir = _project_run_dir(project_state.project_id, data_dir)
    snapshot_dir = p_run_dir / "evidence"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{ev_id}_{basename}"
    
    shutil.copy2(str(source_path), str(snapshot_path))
    
    content_bytes = snapshot_path.read_bytes()
    sha256 = hashlib.sha256(content_bytes).hexdigest()
        
    try:
        content_str = content_bytes.decode('utf-8')
    except Exception:
        content_str = "<binary>"
        
    lines = content_str.splitlines()
    excerpt = ""
    if line_start and line_end:
        start_idx = max(0, line_start - 1)
        end_idx = min(len(lines), line_end)
        excerpt = "\n".join(lines[start_idx:end_idx])[:600]
    else:
        excerpt = content_str[:600]
        
    ev = Evidence(
        id=ev_id,
        type=type_,
        artifact_path=str(snapshot_path),
        line_start=line_start,
        line_end=line_end,
        sha256=sha256,
        excerpt=excerpt,
        created_by_tool=tool,
        tool_call_id=tool_call_id,
        ts=datetime.datetime.now().isoformat()
    )
    
    project_state.evidence_ids.append(ev_id)
    
    # 1. Persist to ledger file evidence.json
    ledger_path = p_run_dir / "evidence.json"
    ledger = []
    if ledger_path.exists():
        try:
            with open(ledger_path, "r", encoding="utf-8") as f:
                ledger = json.load(f)
        except Exception:
            ledger = []
    ledger.append(ev.model_dump())

    try:
        with open(ledger_path, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2)
    except Exception as exc:
        logger.warning(f"evidence {ev_id}: could not write ledger {ledger_path}: {exc}")

    # 2. Persist to SQLite evidence table (D12)
    try:
        from backend.app.db import insert_evidence
        db_path = os.path.join(data_dir, "rerun.db") if data_dir else "data/rerun.db"
        insert_evidence(db_path, ev.model_dump(), project_state.project_id)
    except Exception as exc:
        logger.warning(f"evidence {ev_id}: could not insert into {db_path}: {exc}")

    try:
        if data_dir not in (None, "data"):
            from backend.app.db import insert_evidence
            insert_evidence("data/rerun.db", ev.model_dump(), project_state.project_id)
    except Exception:
        pass

    return ev


def load_evidence_artifact(project_id, eid, data_dir=None):
    """
    Returns the text of the artifact the ledger records for EXACTLY this evidence id.
    """
    if not eid or not re.match(r"^E-\d+$", eid):
        return None

    p_run_dir = _project_run_dir(project_id, data_dir)
    if not p_run_dir.exists():
        return None

    ledger_path = p_run_dir / "evidence.json"
    artifact_path = None
    found_in_ledger = False
    ledger_valid = False

    if ledger_path.exists():
        try:
            with open(ledger_path, "r", encoding="utf-8") as f:
                ledger = json.load(f)
            ledger_valid = True
            for entry in reversed(ledger):
                if isinstance(entry, dict) and entry.get("id") == eid:
                    artifact_path = entry.get("artifact_path")
                    found_in_ledger = True
                    break
        except Exception:
            ledger_valid = False
            found_in_ledger = False

    if found_in_ledger:
        if artifact_path and os.path.exists(artifact_path):
            try:
                with open(artifact_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception:
                return None
        return None


    # Fallback to unambiguous single match in evidence directory
    snapshot_dir = p_run_dir / "evidence"
    if not snapshot_dir.is_dir():
        return None
    try:
        matches = [
            str(snapshot_dir / name)
            for name in sorted(os.listdir(str(snapshot_dir)))
            if name.startswith(f"{eid}_")
        ]
    except Exception:
        return None
    if len(matches) != 1:
        return None
    try:
        with open(matches[0], "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return None

def verify_quote(evidence_record, quote):
    try:
        with open(evidence_record.artifact_path, "rb") as f:
            content_bytes = f.read()
            curr_sha256 = hashlib.sha256(content_bytes).hexdigest()
    except Exception:
        return False
        
    if curr_sha256 != evidence_record.sha256:
        return False
        
    content_str = content_bytes.decode('utf-8', errors='ignore')
    norm_quote = " ".join(quote.split())
    
    if evidence_record.line_start and evidence_record.line_end:
        lines = content_str.splitlines()
        start = max(0, evidence_record.line_start - 1)
        end = min(len(lines), evidence_record.line_end)
        search_text = " ".join(" ".join(lines[start:end]).split())
    else:
        search_text = " ".join(content_str.split())
        
    return norm_quote in search_text
