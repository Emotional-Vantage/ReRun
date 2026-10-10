"""
Regression tests for two defects that made the whole API unresponsive.

1. The SSE stream waited on an unbounded `await queue.get()`. An idle dashboard tab therefore
   held a response open forever, so uvicorn's graceful shutdown blocked on it ("Waiting for
   connections to close") and, under --reload, any backend edit wedged the entire API. Every
   request then hung: the benchmark list rendered empty and a repository clone spun forever.

2. The test suite wrote to the real data/rerun.db, and tests/e2e/test_b4_api.py deleted it
   outright, so a full test run destroyed every live project belonging to the running app.
"""

import asyncio
import os
import re
from pathlib import Path

import pytest

from backend.app import db as app_db
from backend.app.sse import StreamManager


# ---------------------------------------------------------------------------
# 1. The event stream must not hold a response open forever
# ---------------------------------------------------------------------------

def _run(coro):
    """Run one coroutine to completion. Avoids depending on pytest-asyncio."""
    return asyncio.run(coro)


class _FakeRequest:
    def __init__(self, disconnected: bool = False):
        self._disconnected = disconnected

    async def is_disconnected(self):
        return self._disconnected


async def _test_idle_stream_emits_a_heartbeat_instead_of_blocking(monkeypatch):
    """An idle project must still produce output, so the response can make progress."""
    manager = StreamManager()
    monkeypatch.setattr(manager, "HEARTBEAT_SECONDS", 0.05, raising=False)
    monkeypatch.setattr("backend.app.sse.get_events_since", lambda *_a, **_k: [])

    gen = manager.event_generator("p_idle", 0, request=_FakeRequest())
    frame = await asyncio.wait_for(gen.__anext__(), timeout=2.0)

    assert frame.startswith(":"), f"expected an SSE comment heartbeat, got {frame!r}"
    await gen.aclose()


async def _test_stream_ends_when_the_client_disconnects(monkeypatch):
    """
    A disconnected client must end the generator. While this never returned, uvicorn could
    not finish a shutdown or a reload.
    """
    manager = StreamManager()
    monkeypatch.setattr(manager, "HEARTBEAT_SECONDS", 0.05, raising=False)
    monkeypatch.setattr("backend.app.sse.get_events_since", lambda *_a, **_k: [])

    frames = []
    gen = manager.event_generator("p_gone", 0, request=_FakeRequest(disconnected=True))
    async for frame in gen:
        frames.append(frame)
        if len(frames) > 5:
            pytest.fail("generator did not terminate for a disconnected client")

    assert frames == []


async def _test_stream_deregisters_its_listener_on_exit(monkeypatch):
    """A finished stream must not leak a listener, or events pile up against a dead queue."""
    manager = StreamManager()
    monkeypatch.setattr(manager, "HEARTBEAT_SECONDS", 0.05, raising=False)
    monkeypatch.setattr("backend.app.sse.get_events_since", lambda *_a, **_k: [])

    gen = manager.event_generator("p_leak", 0, request=_FakeRequest())
    await asyncio.wait_for(gen.__anext__(), timeout=2.0)
    assert len(manager.listeners["p_leak"]) == 1

    await gen.aclose()
    assert len(manager.listeners["p_leak"]) == 0


# ---------------------------------------------------------------------------
# 2. The suite must never touch the database the running app is serving
# ---------------------------------------------------------------------------

def test_production_path_is_redirected_while_an_override_is_active():
    """The autouse session fixture sets this, so the suite cannot reach data/rerun.db."""
    resolved = app_db.resolve_db_path("data/rerun.db")
    assert resolved != "data/rerun.db", "test run is still pointed at the real database"
    assert os.path.normpath(resolved) != os.path.normpath(app_db.PRODUCTION_DB_PATH)


def test_an_explicit_database_path_is_never_redirected(tmp_path):
    """Tests that name their own database must get exactly that database."""
    explicit = str(tmp_path / "mine.db")
    assert app_db.resolve_db_path(explicit) == explicit


def test_connections_opened_without_a_path_go_to_the_override():
    conn = app_db.get_connection()
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        on_disk = row[2] or ""
    finally:
        conn.close()
    assert "data/rerun.db" not in on_disk.replace(os.sep, "/")


def test_the_suite_does_not_delete_the_real_database():
    """
    Guard against the deletion that wiped live projects.

    Parsed from the AST rather than matched as text, so prose describing the bug in a
    comment or docstring cannot trip it; only a real call can.
    """
    import ast
    from pathlib import Path

    destructive = {"remove", "unlink", "rmtree"}
    offending = []

    for path in Path("tests").rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name not in destructive:
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if "data/rerun.db" in arg.value.replace("\\", "/"):
                        offending.append(f"{path}:{node.lineno} calls {name}({arg.value!r})")

    assert not offending, (
        "test code deletes the production database: " + "; ".join(offending)
    )


def test_run_artifacts_are_redirected_away_from_the_real_data_dir():
    """
    The suite must not write into data/runs/.

    Tests used fixed project ids and wrote workspaces and wheelhouses into the directory
    the dev server serves: tens of gigabytes of leftovers, and tests that could pass on a
    directory an earlier run had created. conftest redirects the runs root for the whole
    session; this asserts the redirect is actually in force.
    """
    from tools import paths

    root = paths.runs_root()
    assert root != Path(paths.DEFAULT_RUNS_ROOT), "runs root was not redirected for the suite"
    norm_resolved = str(root.resolve()).replace("\\", "/")
    assert paths.DEFAULT_RUNS_ROOT not in norm_resolved.rsplit("/", 2)[0]


def test_no_test_hardcodes_the_production_runs_directory():
    """
    A literal "data/runs" in a test escapes the redirect above and starts the leak again.
    Parsed from the AST so prose in a comment or docstring cannot trip it.
    """
    import ast

    from tools import paths

    offending = []
    for path in Path("tests").rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue

        # Docstrings are string constants too; describing the bug must not trip the guard.
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                first = node.body[0] if node.body else None
                if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                        and isinstance(first.value.value, str)):
                    docstrings.add(id(first.value))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in docstrings:
                continue
            if paths.DEFAULT_RUNS_ROOT in node.value.replace("\\", "/"):
                offending.append(f"{path}:{node.lineno}: {node.value!r}")

    assert not offending, (
        "tests must resolve run paths through tools.paths, not a literal: "
        + "; ".join(offending)
    )


def test_idle_stream_emits_a_heartbeat(monkeypatch):
    _run(_test_idle_stream_emits_a_heartbeat_instead_of_blocking(monkeypatch))


def test_stream_ends_on_client_disconnect(monkeypatch):
    _run(_test_stream_ends_when_the_client_disconnects(monkeypatch))


def test_stream_deregisters_listener(monkeypatch):
    _run(_test_stream_deregisters_its_listener_on_exit(monkeypatch))
