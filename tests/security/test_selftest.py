import os
import json
import shutil
import pytest
from pathlib import Path

from sandbox.manager import run_container
import docker


def is_docker_available():
    try:
        docker.from_env().ping()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not is_docker_available(), reason="Docker is not available")


@pytest.fixture(scope="session", autouse=True)
def setup_limits():
    os.environ["SANDBOX_PIDS"] = "512"
    os.environ["SANDBOX_MEM"] = "1g"
    os.environ["SANDBOX_CPUS"] = "1.0"
    os.environ["RUN_TIMEOUT_S"] = "5"
    os.environ["INSTALL_TIMEOUT_S"] = "60"


def test_sandbox_security(tmp_path):
    repo_src = Path("tests/security/escape_repo")
    workspace = tmp_path / "escape_repo"
    shutil.copytree(repo_src, workspace)

    result = run_container(
        project_id="selftest_security",
        workspace=workspace,
        is_setup=False,
        command="python attempt.py",
        kind="run",
        n=1,
    )

    assert not result.timed_out
    assert not result.oom

    log_content = Path(result.log_path).read_text()

    try:
        lines = [line.strip() for line in log_content.split("\n") if line.strip()]
        output_data = json.loads(lines[-1])
    except Exception:
        pytest.fail(f"Failed to parse JSON output from attempt.py. Log:\n{log_content}")

    assert not output_data.get("network_access"), "Network access is allowed!"
    assert not output_data.get("write_root"), "Write to / is allowed!"
    assert not output_data.get("write_etc"), "Write to /etc is allowed!"
    assert not output_data.get("leaked_env"), "Environment variables leaked!"
    assert not output_data.get("docker_socket"), "Docker socket is mounted!"
    assert not output_data.get("is_root"), "Running as root user!"
    assert not output_data.get("fork_bomb_success"), "Fork bomb succeeded (PIDs limit not enforced)!"


def test_sandbox_timeout(tmp_path):
    workspace = tmp_path / "timeout_repo"
    workspace.mkdir()

    result = run_container(
        project_id="selftest_timeout",
        workspace=workspace,
        is_setup=False,
        command='python -c "import time; time.sleep(100)"',
        kind="run",
        n=1,
    )

    assert result.timed_out


def test_sandbox_oom(tmp_path):
    workspace = tmp_path / "oom_repo"
    workspace.mkdir()

    script_path = workspace / "oom.py"
    script_path.write_text("a = []\nwhile True:\n    a.append(' ' * 10**7)\n")

    result = run_container(
        project_id="selftest_oom",
        workspace=workspace,
        is_setup=False,
        command="python oom.py",
        kind="run",
        n=1,
    )

    assert result.oom
