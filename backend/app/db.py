import sqlite3
import json
import logging
import os
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class ConcurrentModificationError(Exception):
    """Raised when an optimistic locking version mismatch occurs."""
    pass

class CorruptProjectStateError(Exception):
    """
    Raised when a project's persisted state_json cannot be validated back into a
    ProjectState. Callers should surface this as a per-project error (422), never as a
    generic server failure, so one unreadable row cannot look like a server outage.
    """
    def __init__(self, project_id: str, detail: str):
        self.project_id = project_id
        self.detail = detail
        super().__init__(f"Corrupt persisted state for project '{project_id}': {detail}")

# Process-wide redirect for the database location.
_DB_PATH_OVERRIDE: Optional[str] = None

def set_db_path_override(path: Optional[str]) -> None:
    """Redirect every subsequent connection. Pass None to restore normal behaviour."""
    global _DB_PATH_OVERRIDE
    _DB_PATH_OVERRIDE = path

PRODUCTION_DB_PATH = "data/rerun.db"

def resolve_db_path(db_path: str = PRODUCTION_DB_PATH) -> str:
    """
    The database a caller should actually use.
    Only the production path is redirected.
    """
    target = _DB_PATH_OVERRIDE or os.getenv("RERUN_DB_PATH")
    if not target:
        return db_path
    try:
        is_production = os.path.normpath(db_path) == os.path.normpath(PRODUCTION_DB_PATH)
    except Exception:
        is_production = db_path == PRODUCTION_DB_PATH
    return target if is_production else db_path

def get_connection(db_path="data/rerun.db"):
    db_path = resolve_db_path(db_path)
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db(db_path="data/rerun.db"):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            benchmark_id TEXT,
            commit_sha TEXT,
            status TEXT,
            state_json TEXT,
            created_at TEXT,
            updated_at TEXT,
            version INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute("PRAGMA table_info(projects)")
    columns = [row[1] for row in cursor.fetchall()]
    if "version" not in columns:
        cursor.execute("ALTER TABLE projects ADD COLUMN version INTEGER DEFAULT 1")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT,
            ts TEXT,
            step INTEGER,
            role TEXT,
            type TEXT,
            tool TEXT,
            summary TEXT,
            evidence_ids_json TEXT,
            payload_json TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evidence (
            id TEXT,
            project_id TEXT,
            type TEXT,
            artifact_path TEXT,
            line_start INTEGER,
            line_end INTEGER,
            sha256 TEXT,
            excerpt TEXT,
            created_by_tool TEXT,
            tool_call_id TEXT,
            ts TEXT,
            PRIMARY KEY (project_id, id)
        )
    ''')
    conn.commit()
    _migrate_evidence_primary_key(conn)
    conn.close()

    resolved = resolve_db_path(db_path)
    if resolved not in _REPAIRED_DATABASES:
        _REPAIRED_DATABASES.add(resolved)
        repair_unknown_error_classes(db_path)


def _migrate_evidence_primary_key(conn):
    """
    Rebuild a legacy `evidence` table whose primary key was `id` alone.
    Idempotent: a table that already carries the composite key is left untouched.
    """
    cursor = conn.cursor()
    row = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='evidence'"
    ).fetchone()
    if not row or not row[0] or "PRIMARY KEY (project_id, id)" in row[0]:
        return

    try:
        cursor.execute("ALTER TABLE evidence RENAME TO evidence_legacy_pk")
        cursor.execute('''
            CREATE TABLE evidence (
                id TEXT,
                project_id TEXT,
                type TEXT,
                artifact_path TEXT,
                line_start INTEGER,
                line_end INTEGER,
                sha256 TEXT,
                excerpt TEXT,
                created_by_tool TEXT,
                tool_call_id TEXT,
                ts TEXT,
                PRIMARY KEY (project_id, id)
            )
        ''')
        cursor.execute('''
            INSERT OR IGNORE INTO evidence
            (id, project_id, type, artifact_path, line_start, line_end, sha256,
             excerpt, created_by_tool, tool_call_id, ts)
            SELECT id, project_id, type, artifact_path, line_start, line_end, sha256,
                   excerpt, created_by_tool, tool_call_id, ts
            FROM evidence_legacy_pk
        ''')
        cursor.execute("DROP TABLE evidence_legacy_pk")
        conn.commit()
        logger.info("migrated evidence table to a per-project primary key")
    except Exception as exc:
        conn.rollback()
        logger.warning(f"could not migrate the evidence primary key: {exc}")


_REPAIRED_DATABASES: set = set()

def repair_unknown_error_classes(db_path: str = "data/rerun.db") -> int:
    """
    Idempotent repair for rows written before an attempt error_class value was added to the
    ErrorClass literal. Any attempt carrying an error_class outside the current literal is
    rewritten to 'unknown'.
    """
    from typing import get_args
    from agent.state import ErrorClass

    allowed = set(get_args(ErrorClass))
    repaired = 0
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, state_json FROM projects")
        rows = cursor.fetchall()
        for project_id, state_json in rows:
            if not state_json:
                continue
            try:
                data = json.loads(state_json)
            except Exception:
                continue
            attempts = data.get("attempts")
            if not isinstance(attempts, list):
                continue
            changed = False
            for att in attempts:
                if not isinstance(att, dict):
                    continue
                ec = att.get("error_class")
                if ec is not None and ec not in allowed:
                    logger.warning(
                        "Repairing project %s: attempt error_class %r is not a valid ErrorClass; "
                        "rewriting to 'unknown'", project_id, ec
                    )
                    att["error_class"] = "unknown"
                    changed = True
            if changed:
                cursor.execute(
                    "UPDATE projects SET state_json = ? WHERE id = ?",
                    (json.dumps(data), project_id)
                )
                repaired += 1
        if repaired:
            conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("error_class repair migration skipped: %s", e)
    return repaired

def save_project_state(db_path, project_id, benchmark_id, commit_sha, status, state_model, expected_version: Optional[int] = None):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(projects)")
    columns = [row[1] for row in cursor.fetchall()]
    if "version" not in columns:
        cursor.execute("ALTER TABLE projects ADD COLUMN version INTEGER DEFAULT 1")
    
    if expected_version is not None:
        cursor.execute('''
            UPDATE projects 
            SET benchmark_id = ?, commit_sha = ?, status = ?, state_json = ?, updated_at = datetime('now'), version = version + 1
            WHERE id = ? AND version = ?
        ''', (benchmark_id, commit_sha, status, state_model.model_dump_json(), project_id, expected_version))
        if cursor.rowcount == 0:
            conn.rollback()
            conn.close()
            raise ConcurrentModificationError(f"Concurrent update conflict for project {project_id} (expected version {expected_version})")
        state_model.version = expected_version + 1
    else:
        cursor.execute("SELECT version FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        if row is not None:
            cur_version = row[0] if row[0] is not None else 1
            new_version = cur_version + 1
            state_model.version = new_version
            cursor.execute('''
                UPDATE projects 
                SET benchmark_id = ?, commit_sha = ?, status = ?, state_json = ?, updated_at = datetime('now'), version = ?
                WHERE id = ?
            ''', (benchmark_id, commit_sha, status, state_model.model_dump_json(), new_version, project_id))
        else:
            state_model.version = 1
            cursor.execute('''
                INSERT INTO projects 
                (id, benchmark_id, commit_sha, status, state_json, created_at, updated_at, version) 
                VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'), 1)
            ''', (project_id, benchmark_id, commit_sha, status, state_model.model_dump_json()))
            
    conn.commit()
    conn.close()

def get_project_state(db_path, project_id):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(projects)")
    columns = [row[1] for row in cursor.fetchall()]
    has_version = "version" in columns
    
    if has_version:
        cursor.execute('SELECT state_json, version FROM projects WHERE id = ?', (project_id,))
    else:
        cursor.execute('SELECT state_json FROM projects WHERE id = ?', (project_id,))
        
    row = cursor.fetchone()
    conn.close()
    if row:
        from pydantic import ValidationError
        from agent.state import ProjectState
        try:
            state = ProjectState.model_validate_json(row[0])
        except ValidationError as e:
            detail = "; ".join(
                f"{'.'.join(str(p) for p in err.get('loc', ()))}: {err.get('msg', '')}"
                for err in e.errors()[:5]
            )
            logger.error("Corrupt persisted state for project %s: %s", project_id, detail)
            raise CorruptProjectStateError(project_id, detail) from e
        if has_version and row[1] is not None:
            state.version = row[1]
        return state
    return None

def get_events_since(db_path, project_id, last_event_id):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, ts, step, role, type, tool, summary, evidence_ids_json, payload_json
        FROM events 
        WHERE project_id = ? AND id > ?
        ORDER BY id ASC
    ''', (project_id, last_event_id))
    rows = cursor.fetchall()
    conn.close()
    
    events = []
    for row in rows:
        events.append({
            "id": row[0],
            "ts": row[1],
            "project_id": project_id,
            "step": row[2],
            "role": row[3],
            "type": row[4],
            "tool": row[5],
            "summary": row[6],
            "evidence_ids": json.loads(row[7]) if row[7] else [],
            "payload": json.loads(row[8]) if row[8] else {}
        })
    return events

def insert_evidence(db_path: str, ev_dict: Any, project_id: str = None):
    init_db(db_path)
    if isinstance(ev_dict, str) and not isinstance(project_id, str):
        ev_dict, project_id = project_id, ev_dict
    if hasattr(ev_dict, "model_dump"):
        ev_dict = ev_dict.model_dump()
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO evidence
        (id, project_id, type, artifact_path, line_start, line_end, sha256, excerpt, created_by_tool, tool_call_id, ts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        ev_dict.get("id"),
        project_id,
        ev_dict.get("type"),
        ev_dict.get("artifact_path"),
        ev_dict.get("line_start"),
        ev_dict.get("line_end"),
        ev_dict.get("sha256"),
        ev_dict.get("excerpt"),
        ev_dict.get("created_by_tool"),
        ev_dict.get("tool_call_id"),
        ev_dict.get("ts")
    ))
    conn.commit()
    conn.close()

def get_evidence_by_id(db_path: str, project_id: str, eid: str) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, project_id, type, artifact_path, line_start, line_end, sha256, excerpt, created_by_tool, tool_call_id, ts
        FROM evidence
        WHERE project_id = ? AND id = ?
    ''', (project_id, eid))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "project_id": row[1],
            "type": row[2],
            "artifact_path": row[3],
            "line_start": row[4],
            "line_end": row[5],
            "sha256": row[6],
            "excerpt": row[7],
            "created_by_tool": row[8],
            "tool_call_id": row[9],
            "ts": row[10]
        }
    return None

def get_all_evidence(db_path: str, project_id: str) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, project_id, type, artifact_path, line_start, line_end, sha256, excerpt, created_by_tool, tool_call_id, ts
        FROM evidence
        WHERE project_id = ?
        ORDER BY id ASC
    ''', (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "project_id": r[1],
            "type": r[2],
            "artifact_path": r[3],
            "line_start": r[4],
            "line_end": r[5],
            "sha256": r[6],
            "excerpt": r[7],
            "created_by_tool": r[8],
            "tool_call_id": r[9],
            "ts": r[10]
        }
        for r in rows
    ]
