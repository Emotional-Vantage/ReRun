import os
import pytest
from pathlib import Path
import docker

from sandbox.manager import build_container_spec, run_container, get_limits


def is_docker_available():
    try:
        docker.from_env().ping()
        return True
    except Exception:
        return False


def test_container_spec_hardening_attributes(tmp_path):
    """
    Gate: Verify container specification strictly adheres to defense-in-depth:
    - network_mode="none" (offline)
    - user="1000:1000" (non-root)
    - read_only=True (immutable root filesystem)
    - cap_drop=["ALL"] (all Linux capabilities dropped)
    - security_opt=["no-new-privileges"]
    - no privileged mode
    - tmpfs capped (/tmp 256m)
    - strictly isolated volume bindings
    """
    ws = tmp_path / "workspace"
    ws.mkdir()

    spec = build_container_spec("proj_sec_spec", ws, is_setup=False, command="python test.py")

    assert spec["network_mode"] == "none", "Network must be disabled ('none')"
    assert spec["user"] == "1000:1000", "User must be non-root (1000:1000)"
    assert spec["read_only"] is True, "Root filesystem must be read-only"
    assert "ALL" in spec["cap_drop"], "All capabilities must be dropped"
    assert "no-new-privileges" in spec["security_opt"], "no-new-privileges must be enforced"
    assert spec.get("privileged", False) is False, "Privileged containers are strictly forbidden"
    assert "/tmp" in spec["tmpfs"], "tmpfs must be configured for temporary scratch space"

    # Check volume mounts: only workspace and wheelhouses should be bound
    volumes = spec["volumes"]
    for host_path, mount_cfg in volumes.items():
        assert "/workspace" in mount_cfg["bind"] or "/wheelhouse" in mount_cfg["bind"]
        # Ensure no sensitive host files are mounted
        assert "/var/run/docker.sock" not in host_path
        assert "/etc" not in host_path
        assert "/root" not in host_path


@pytest.mark.skipif(not is_docker_available(), reason="Docker is not available")
def test_container_network_unreachable(tmp_path):
    """Network is unreachable: socket connect to 8.8.8.8:53 fails and urllib fails."""
    ws = tmp_path / "net_repo"
    ws.mkdir()
    (ws / "net_test.py").write_text(
        "import socket, urllib.request, sys\n"
        "s_ok = False\n"
        "try:\n"
        "    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "    s.settimeout(1)\n"
        "    s.connect(('8.8.8.8', 53))\n"
        "    s_ok = True\n"
        "except Exception:\n"
        "    pass\n"
        "u_ok = False\n"
        "try:\n"
        "    urllib.request.urlopen('http://example.com', timeout=1)\n"
        "    u_ok = True\n"
        "except Exception:\n"
        "    pass\n"
        "if s_ok or u_ok:\n"
        "    print('FAIL_NETWORK_ACCESSIBLE')\n"
        "    sys.exit(1)\n"
        "print('PASS_NETWORK_BLOCKED')\n"
    )

    res = run_container("sec_net", ws, False, "python net_test.py", "run", 1)
    assert res.exit_code == 0
    log = Path(res.log_path).read_text()
    assert "PASS_NETWORK_BLOCKED" in log
    assert "FAIL_NETWORK_ACCESSIBLE" not in log


@pytest.mark.skipif(not is_docker_available(), reason="Docker is not available")
def test_container_write_outside_workspace_fails(tmp_path):
    """A write outside /workspace raises because root is read-only."""
    ws = tmp_path / "write_repo"
    ws.mkdir()
    (ws / "write_test.py").write_text(
        "import sys\n"
        "try:\n"
        "    with open('/escape.txt', 'w') as f:\n"
        "        f.write('fail')\n"
        "    print('FAIL_WRITE_SUCCEEDED')\n"
        "    sys.exit(1)\n"
        "except OSError as e:\n"
        "    print(f'PASS_WRITE_BLOCKED: {e}')\n"
    )

    res = run_container("sec_write", ws, False, "python write_test.py", "run", 1)
    assert res.exit_code == 0
    log = Path(res.log_path).read_text()
    assert "PASS_WRITE_BLOCKED" in log
    assert "FAIL_WRITE_SUCCEEDED" not in log


@pytest.mark.skipif(not is_docker_available(), reason="Docker is not available")
def test_container_runs_as_uid_1000(tmp_path):
    """The process inside the container runs as uid 1000."""
    ws = tmp_path / "uid_repo"
    ws.mkdir()
    (ws / "uid_test.py").write_text(
        "import os\n"
        "uid = os.getuid()\n"
        "print(f'UID:{uid}')\n"
    )

    res = run_container("sec_uid", ws, False, "python uid_test.py", "run", 1)
    assert res.exit_code == 0
    log = Path(res.log_path).read_text()
    assert "UID:1000" in log


@pytest.mark.skipif(not is_docker_available(), reason="Docker is not available")
def test_container_fork_bomb_capped(tmp_path):
    """A fork bomb is capped by pids_limit."""
    ws = tmp_path / "fork_repo"
    ws.mkdir()
    (ws / "fork_bomb.py").write_text(
        "import subprocess\n"
        "procs = []\n"
        "caught = False\n"
        "try:\n"
        "    for _ in range(400):\n"
        "        p = subprocess.Popen(['sleep', '10'])\n"
        "        procs.append(p)\n"
        "except Exception as e:\n"
        "    caught = True\n"
        "    print(f'CAUGHT_PID_LIMIT: {e}')\n"
        "finally:\n"
        "    for p in procs:\n"
        "        try: p.kill()\n"
        "        except: pass\n"
        "if not caught:\n"
        "    print('FAIL_FORK_BOMB_NOT_CAPPED')\n"
    )

    res = run_container("sec_fork", ws, False, "python fork_bomb.py", "run", 1)
    log = Path(res.log_path).read_text()
    assert "CAUGHT_PID_LIMIT" in log or "Resource temporarily unavailable" in log or "FAIL_FORK_BOMB_NOT_CAPPED" not in log


@pytest.mark.skipif(not is_docker_available(), reason="Docker is not available")
def test_container_disk_bomb_contained(tmp_path):
    """
    Gate: Host disk is protected. Attempt to fill /tmp beyond tmpfs cap (256MB)
    fails with ENOSPC (No space left on device) while host remains unharmed.
    """
    ws = tmp_path / "disk_bomb_repo"
    ws.mkdir()

    bomb_script = ws / "fill_tmp.py"
    bomb_script.write_text(
        "import os\n"
        "try:\n"
        "    with open('/tmp/bomb.bin', 'wb') as f:\n"
        "        for _ in range(400):\n"
        "            f.write(b'\\x00' * (1024 * 1024))\n"
        "    print('FAIL_ALLOWED')\n"
        "except OSError as e:\n"
        "    print(f'CAUGHT_ENOSPC: {e}')\n"
    )

    res = run_container(
        project_id="selftest_disk_bomb",
        workspace=ws,
        is_setup=False,
        command="python fill_tmp.py",
        kind="run",
        n=1,
    )

    log_content = Path(res.log_path).read_text()
    assert (
        "CAUGHT_ENOSPC" in log_content
        or "No space left on device" in log_content
        or res.exit_code != 0
    )
    assert "FAIL_ALLOWED" not in log_content
    # Assert host tmp is clean
    assert not os.path.exists("/tmp/bomb.bin")


@pytest.mark.skipif(not is_docker_available(), reason="Docker is not available")
def test_container_timeout_killed(tmp_path):
    """A run exceeding RUN_TIMEOUT_S is killed and timed_out=True."""
    ws = tmp_path / "timeout_repo"
    ws.mkdir()
    res = run_container(
        project_id="sec_timeout",
        workspace=ws,
        is_setup=False,
        command="python -c 'import time; time.sleep(100)'",
        kind="run",
        n=1,
        run_timeout_override=2,
    )
    assert res.timed_out is True
