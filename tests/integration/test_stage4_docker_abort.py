import time
import threading
import docker
import pytest
from pathlib import Path
from sandbox.manager import run_container
from agent.state import ProjectState

try:
    from backend.app.main import app
    from backend.app.db import init_db, save_project_state, get_project_state
    from fastapi.testclient import TestClient
    _HAS_APP = True
except (ImportError, AttributeError):
    _HAS_APP = False


def is_docker_available():
    try:
        docker.from_env().ping()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not is_docker_available(), reason="Docker is not available")


def test_docker_container_killed_on_abort(tmp_path):
    if not _HAS_APP or not hasattr(app, "routes") or len(app.routes) == 0:
        pytest.skip("Backend API and persistence routes are implemented in Stage 7")

    client_docker = docker.from_env()
    client = TestClient(app)

    proj_id = "test_docker_abort"
    init_db("data/rerun.db")

    ws = tmp_path / "workspace"
    ws.mkdir(parents=True)

    state = ProjectState(
        project_id=proj_id,
        benchmark_id="b1",
        repo_commit="c1",
        phase="RUN",
        workspace=str(ws),
        budgets={"steps_used": 1},
        claims=[],
        paper_settings=[],
    )
    save_project_state("data/rerun.db", proj_id, "b1", "c1", "RUN", state)

    # Launch a long-running container in a background thread
    def run_target():
        try:
            run_container(
                project_id=proj_id,
                workspace=ws,
                is_setup=False,
                command="python -c 'import time; time.sleep(30)'",
                kind="run",
                n=1,
            )
        except Exception:
            pass

    t = threading.Thread(target=run_target)
    t.daemon = True
    t.start()

    # Wait until the container is visible in docker ps
    container_found = False
    for _ in range(50):
        time.sleep(0.1)
        containers = client_docker.containers.list(filters={"label": f"rerun_project={proj_id}"})
        if containers:
            container_found = True
            break

    assert container_found, "Container did not start or was not labeled with rerun_project"

    # Call /abort
    res = client.post(f"/api/projects/{proj_id}/abort")
    assert res.status_code == 200
    assert res.json() == {"status": "aborted"}

    # Verify container is killed and no longer in docker ps
    time.sleep(0.5)
    running = client_docker.containers.list(filters={"label": f"rerun_project={proj_id}"})
    assert len(running) == 0, f"Expected 0 running containers for project, found: {[c.name for c in running]}"

    # State verification
    persisted = get_project_state("data/rerun.db", proj_id)
    assert persisted.phase == "DONE"
    assert persisted.abort_requested is True
    assert persisted.final["status"] == "INCONCLUSIVE"

    t.join(timeout=3.0)
