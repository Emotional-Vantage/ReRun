import json
import datetime
import os
from typing import Optional, List, Dict, Any

from agent.state import Event, ProjectState

try:
    from backend.app.db import get_connection
except (ImportError, ModuleNotFoundError):
    get_connection = None

_EVENT_SUBSCRIBERS = []

def subscribe(callback):
    _EVENT_SUBSCRIBERS.append(callback)

def unsubscribe(callback):
    if callback in _EVENT_SUBSCRIBERS:
        _EVENT_SUBSCRIBERS.remove(callback)

def emit_event(
    state: ProjectState,
    role: str,
    type_: str,
    summary: str,
    tool: Optional[str] = None,
    evidence_ids: Optional[List[str]] = None,
    payload: Optional[Dict[str, Any]] = None,
    db_path: str = "data/rerun.db"
) -> Event:
    """Emits an event, saves it to the SQLite events table (if available), and notifies subscribers."""
    ev_ids = evidence_ids or []
    p_load = payload or {}
    now_str = datetime.datetime.now().isoformat()
    
    # Calculate step
    step_num = state.budgets.get("steps_used", 0)

    event_id = 0
    if get_connection is not None:
        try:
            conn = get_connection(db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO events (project_id, ts, step, role, type, tool, summary, evidence_ids_json, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                state.project_id,
                now_str,
                step_num,
                role,
                type_,
                tool,
                summary[:240],
                json.dumps(ev_ids),
                json.dumps(p_load)
            ))
            conn.commit()
            event_id = cursor.lastrowid
            conn.close()
        except Exception:
            pass

    ev = Event(
        id=event_id,
        ts=now_str,
        project_id=state.project_id,
        step=step_num,
        role=role,
        type=type_,
        tool=tool,
        summary=summary[:240],
        evidence_ids=ev_ids,
        payload=p_load
    )

    for sub in list(_EVENT_SUBSCRIBERS):
        try:
            sub(ev)
        except Exception:
            pass

    return ev
