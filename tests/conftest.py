"""
Shared pytest fixtures for ReRun test suite.
"""

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def pin_llm_mode_to_live(monkeypatch):
    """Default every test to live mode so provider-level patching works as written."""
    try:
        import agent.llm as llm
        monkeypatch.setattr(llm, "LLM_MODE", "live", raising=False)
    except ImportError:
        pass


@pytest.fixture(autouse=True, scope="session")
def isolate_database_from_the_running_app():
    """
    Never let the test suite touch real data/rerun.db.
    No-ops gracefully until backend.app.db exists in Stage 7.
    """
    try:
        from backend.app import db as app_db
        has_override = hasattr(app_db, "set_db_path_override")
    except (ImportError, AttributeError):
        has_override = False

    if has_override:
        tmp_dir = tempfile.mkdtemp(prefix="rerun_test_db_")
        app_db.set_db_path_override(str(Path(tmp_dir) / "rerun.db"))
        app_db.init_db("data/rerun.db")
        try:
            yield
        finally:
            app_db.set_db_path_override(None)
            shutil.rmtree(tmp_dir, ignore_errors=True)
    else:
        yield


@pytest.fixture(autouse=True, scope="session")
def isolate_run_artifacts_from_the_real_data_dir():
    """
    Never let the suite write into data/runs/.
    Redirects runs_root to a scratch directory on disk under data/.pytest-runs/.
    """
    from tools import paths as run_paths

    scratch_parent = Path("data") / ".pytest-runs"
    scratch_parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = tempfile.mkdtemp(prefix="runs_", dir=str(scratch_parent))
    run_paths.set_runs_root(tmp_dir)
    try:
        yield
    finally:
        run_paths.set_runs_root(None)
        shutil.rmtree(tmp_dir, ignore_errors=True)
