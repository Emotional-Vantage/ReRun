import threading
import logging
from typing import Optional, Dict
import os

from agent.loop import run_project
from backend.app.db import get_project_state, save_project_state
from sandbox.manager import kill_project_containers

logger = logging.getLogger(__name__)

MAX_CONCURRENT_PROJECTS = int(os.getenv("MAX_CONCURRENT_PROJECTS", "2"))

_RUNNING_WORKERS: Dict[str, threading.Thread] = {}
_RUNNING_WORKERS_LOCK = threading.Lock()

def is_worker_running(project_id: str) -> bool:
    """Check if a background worker thread is actively running for the given project."""
    with _RUNNING_WORKERS_LOCK:
        t = _RUNNING_WORKERS.get(project_id)
        return t is not None and t.is_alive()

def stop_all_workers():
    """Terminates all active workers globally."""
    with _RUNNING_WORKERS_LOCK:
        pids = list(_RUNNING_WORKERS.keys())
    for pid in pids:
        stop_project_worker(pid)

def stop_project_worker(project_id: str):
    """Signals worker to stop and kills associated containers."""
    try:
        state = get_project_state("data/rerun.db", project_id)
        if state:
            state.abort_requested = True
            save_project_state("data/rerun.db", project_id, state.benchmark_id, state.repo_commit, "DONE", state)
    except Exception as e:
        logger.warning(f"Failed to set abort flag for project {project_id}: {e}")

    try:
        import sandbox.manager
        sandbox.manager.kill_project_containers(project_id)
    except Exception as e:
        logger.warning(f"Failed to kill containers for project {project_id}: {e}")

    with _RUNNING_WORKERS_LOCK:
        t = _RUNNING_WORKERS.get(project_id)
    if t and t.is_alive() and t != threading.current_thread():
        t.join(timeout=2.0)

def run_project_thread(project_id: str):
    """
    Background worker that runs the synchronous `run_project` loop.
    It returns when `state.pending` is set or when phase is "DONE".
    """
    logger.info(f"Starting worker for project {project_id}")
    state = get_project_state("data/rerun.db", project_id)
    if not state:
        logger.error(f"Project {project_id} not found.")
        return
        
    if getattr(state, "abort_requested", False) or state.phase == "DONE":
        logger.info(f"Project {project_id} is already aborted or DONE. Worker exiting.")
        return

    try:
        run_project(state, deps={})
    except Exception as e:
        logger.exception(f"Exception in worker for project {project_id}: {e}")
        state.phase = "DONE"
        state.final = {"status": "INCONCLUSIVE", "reason": f"internal error: {str(e)}"}
        
    """
    Hand back the GPU before anything else.

    A droplet bills by the hour from the moment it is active, so the window
    between "this project is finished" and "the droplet is destroyed" is money.
    It is closed here, on the worker's way out, for every exit path including
    the exception handler above -- not in the orchestrator, which can return
    early at a gate and legitimately leave the droplet up for the operator's
    next decision.

    The teardown also produces the receipt (where it ran, how long, what it
    cost), which is persisted with the state below so the report can print it.
    """
    if getattr(state, "remote_approved", False) and (state.phase == "DONE" or state.final):
        try:
            from agent.loop import release_remote_sandbox

            released = release_remote_sandbox(project_id)
            if released is not None and getattr(released, "receipt", None) is not None:
                state.remote_receipt = released.receipt.to_dict()
                logger.info(
                    f"Destroyed remote droplet for {project_id}: "
                    f"{state.remote_receipt.get('billed_seconds', 0):.0f}s billed"
                )
        except Exception as e:
            # Never let a teardown failure mask the run's own outcome, but make
            # it loud: an undestroyed droplet keeps charging.
            logger.error(f"FAILED to release remote droplet for {project_id}: {e}")

    status = state.final.get("status") if state.final else state.phase
    save_project_state("data/rerun.db", project_id, state.benchmark_id, state.repo_commit, status, state)
    logger.info(f"Worker for project {project_id} finished. Phase: {state.phase}, Pending: {state.pending}")

def start_project_worker(project_id: str, allow_resume: bool = False) -> bool:
    """
    Starts the synchronous orchestrator in a background thread.
    Returns True if a new worker thread was started, or False if one was already running.
    `allow_resume` exempts the call from the concurrency cap.
    """
    with _RUNNING_WORKERS_LOCK:
        t = _RUNNING_WORKERS.get(project_id)
        if t is not None and t.is_alive():
            logger.warning(f"Worker for project {project_id} is already running. Duplicate start ignored.")
            return False

        active = [p for p, th in _RUNNING_WORKERS.items() if th.is_alive()]
        if not allow_resume and len(active) >= MAX_CONCURRENT_PROJECTS and project_id not in active:
            logger.warning(f"Concurrency limit ({MAX_CONCURRENT_PROJECTS}) reached. Active projects: {active}")
            raise RuntimeError(f"Concurrency limit reached ({MAX_CONCURRENT_PROJECTS}). Active projects: {len(active)}")

        def worker():
            try:
                run_project_thread(project_id)
            finally:
                with _RUNNING_WORKERS_LOCK:
                    _RUNNING_WORKERS.pop(project_id, None)

        thread = threading.Thread(target=worker, daemon=True, name=f"worker_{project_id}")
        _RUNNING_WORKERS[project_id] = thread
        thread.start()
        return True
