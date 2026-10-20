"""
Where a project's run artifacts live.

Every run writes a workspace, a per-project wheelhouse, logs, outputs and an evidence
ledger under `data/runs/<project_id>/`.
"""

import os
import re
from pathlib import Path
from typing import Optional

DEFAULT_RUNS_ROOT = "data/runs"

_RUNS_ROOT_OVERRIDE: Optional[str] = None
_SAFE_PROJECT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def set_runs_root(path: Optional[str]) -> None:
    """Redirect every run directory. Pass None to restore the default."""
    global _RUNS_ROOT_OVERRIDE
    _RUNS_ROOT_OVERRIDE = str(path) if path is not None else None


def runs_root() -> Path:
    """The directory that holds one subdirectory per project."""
    if _RUNS_ROOT_OVERRIDE is not None:
        return Path(_RUNS_ROOT_OVERRIDE)
    return Path(os.getenv("RERUN_RUNS_ROOT", DEFAULT_RUNS_ROOT))


def validate_project_id(project_id: str) -> str:
    """Return a safe project id or raise ``ValueError``.

    Project ids are used as path components throughout the application. Keep
    accepting historical test ids, but reject absolute paths, separators, and
    traversal segments before they reach the filesystem.
    """
    if not isinstance(project_id, str) or not project_id or not _SAFE_PROJECT_ID.fullmatch(project_id):
        raise ValueError(f"Invalid project id: {project_id!r}")
    return project_id


def resolve_workspace_path(workspace: str | Path, relative_path: str) -> Path:
    """Resolve a path while keeping it inside ``workspace``.

    ``strict=False`` allows append operations to create a new file, while
    resolving existing symlinks prevents a symlink inside the workspace from
    redirecting a write outside it.
    """
    root = Path(workspace).resolve()
    candidate = (root / relative_path).resolve(strict=False)
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"Path escapes workspace: {relative_path!r}")
    return candidate


def run_dir(project_id: str) -> Path:
    """`data/runs/<project_id>` — the root of one project's artifacts."""
    return runs_root() / validate_project_id(project_id)


def workspace_dir(project_id: str) -> Path:
    """The checked-out repository the sandbox runs against."""
    return run_dir(project_id) / "workspace"


def workspace_path(project_id: str) -> str:
    """String form, for the many call sites that pass a workspace around as `str`."""
    return str(workspace_dir(project_id))


def wheelhouse_dir(project_id: str) -> Path:
    """Wheels downloaded for this project, installed offline inside the sandbox."""
    return run_dir(project_id) / "wheelhouse"


def logs_dir(project_id: str) -> Path:
    return run_dir(project_id) / "logs"


def evidence_ledger_path(project_id: str) -> Path:
    return run_dir(project_id) / "evidence.json"
