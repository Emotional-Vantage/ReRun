import os
import sys
import time
import shlex
import docker
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from .limits import get_limits
from tools import paths
from agent.config import scrub_secrets


@dataclass
class RunResult:
    exit_code: Optional[int]
    timed_out: bool
    oom: bool
    log_path: str
    duration_s: float
    output_dir: str


_ACTIVE_CONTAINERS: dict[str, str] = {}
_ACTIVE_CONTAINERS_LOCK = threading.Lock()


def kill_project_containers(project_id: str):
    """Kills and removes all running containers associated with a project ID."""
    try:
        client = docker.from_env()
        # 1. Kill by label
        try:
            labeled = client.containers.list(all=True, filters={"label": f"rerun_project={project_id}"})
            for c in labeled:
                try:
                    c.kill()
                except Exception:
                    pass
                try:
                    c.remove(force=True)
                except Exception:
                    pass
        except Exception:
            pass
        # 2. Kill by tracked id
        with _ACTIVE_CONTAINERS_LOCK:
            cid = _ACTIVE_CONTAINERS.get(project_id)
        if cid:
            try:
                c = client.containers.get(cid)
                c.kill()
            except Exception:
                pass
            try:
                c.remove(force=True)
            except Exception:
                pass
    except Exception:
        pass


def kill_all_rerun_containers():
    """Global kill switch: kills and removes all containers labeled rerun=1."""
    try:
        client = docker.from_env()
        labeled = client.containers.list(all=True, filters={"label": "rerun=1"})
        for c in labeled:
            try:
                c.kill()
            except Exception:
                pass
            try:
                c.remove(force=True)
            except Exception:
                pass
    except Exception:
        pass


def probe_gpu() -> dict:
    """Check if the Docker daemon lists an nvidia runtime and can run a test container."""
    if sys.platform == "darwin":
        return {"usable": False, "reason": "GPU mode is not supported on macOS", "count": 0}

    try:
        client = docker.from_env()
        info = client.info()
        runtimes = info.get("Runtimes", {})
        if "nvidia" not in runtimes:
            return {"usable": False, "reason": "No nvidia runtime found in Docker daemon", "count": 0}

        limits = get_limits()
        device_requests = [docker.types.DeviceRequest(count=limits.gpu_count, capabilities=[["gpu"]])]
        client.containers.run(
            image=limits.gpu_image,
            command="nvidia-smi -L",
            device_requests=device_requests,
            remove=True,
            detach=False,
        )
        return {"usable": True, "reason": "GPU probe successful", "count": limits.gpu_count}
    except Exception as e:
        return {"usable": False, "reason": f"GPU probe failed: {str(e)}", "count": 0}


def build_container_spec(
    project_id: str,
    workspace: Path,
    is_setup: bool,
    command: str,
    python_image: str = "rerun-base:py311",
) -> dict:
    limits = get_limits()
    wheelhouse = Path("wheelhouse").absolute()
    project_whl = paths.wheelhouse_dir(project_id).absolute()

    spec = dict(
        image=python_image,
        detach=True,
        user="1000:1000",
        network_mode="none",
        read_only=True,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        pids_limit=limits.pids,
        mem_limit=limits.mem,
        memswap_limit=limits.mem,
        nano_cpus=int(limits.cpus * 1e9),
        tmpfs={"/tmp": f"rw,size={'1024m' if is_setup else os.getenv('SANDBOX_TMP_SIZE', '256m')}"},
        working_dir="/workspace",
        environment={
            "HOME": "/tmp",
            "PYTHONPATH": "/workspace/.site",
            "PYTHONHASHSEED": "0",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PIP_NO_CACHE_DIR": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        },
        labels={"rerun": "1", "rerun_project": project_id},
        volumes={
            str(workspace.absolute()): {"bind": "/workspace", "mode": "rw"}
        },
    )

    if is_setup:
        # pip unpacks wheels into TMPDIR before installing. /tmp is a RAM-backed tmpfs
        # bounded by the container memory limit, so a large wheel such as torch (811 MB
        # installed, and roughly that again while unpacking) exhausted it and the install
        # died with "No space left on device" even with ample disk free. Give the installer
        # a disk-backed scratch directory outside the repository workspace instead.
        pip_tmp = (paths.run_dir(project_id) / "pip_tmp").absolute()
        pip_tmp.mkdir(parents=True, exist_ok=True)
        spec["volumes"][str(pip_tmp)] = {"bind": "/pip_tmp", "mode": "rw"}
        spec["environment"]["TMPDIR"] = "/pip_tmp"

        spec["volumes"][str(wheelhouse)] = {"bind": "/wheelhouse", "mode": "ro"}
        find_links = ["--find-links", "/wheelhouse"]
        if project_whl.exists():
            spec["volumes"][str(project_whl)] = {"bind": "/wheelhouse_proj", "mode": "ro"}
            find_links.extend(["--find-links", "/wheelhouse_proj"])

        req_arg = ["-r", "requirements.txt"]
        if not (workspace / "requirements.txt").exists():
            matching_reqs = list(workspace.glob("requirements*.txt"))
            if matching_reqs:
                req_arg = ["-r", matching_reqs[0].name]
            elif (project_whl / "requirements.provision.txt").exists():
                req_arg = ["-r", "/wheelhouse_proj/requirements.provision.txt"]
            else:
                req_arg = []

        spec["command"] = ["pip", "install", "--no-index"] + find_links + ["--target", "/workspace/.site"] + req_arg
    else:
        spec["command"] = shlex.split(command)

    if limits.gpu_enabled:
        gpu_info = probe_gpu()
        if gpu_info["usable"]:
            spec["image"] = limits.gpu_image
            spec["device_requests"] = [docker.types.DeviceRequest(count=limits.gpu_count, capabilities=[["gpu"]])]

    return spec


def _make_tree_group_writable(root: Path) -> None:
    """
    Grants read/write (and traverse, for directories) to the whole tree so the container's
    uid 1000 can use the bind mount. Pure os.chmod over a walk: no shell, so paths containing
    spaces or shell metacharacters are handled correctly.
    """
    import stat

    file_bits = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH
    dir_bits = file_bits | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH

    try:
        os.chmod(root, dir_bits)
    except Exception:
        pass
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames:
            try:
                os.chmod(os.path.join(dirpath, name), dir_bits)
            except Exception:
                pass
        for name in filenames:
            try:
                target = os.path.join(dirpath, name)
                # Preserve the executable bit where it is already set (entry-point scripts).
                current = os.stat(target).st_mode
                bits = file_bits
                if current & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
                    bits |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
                os.chmod(target, bits)
            except Exception:
                pass


def _safe_remove(container) -> None:
    """
    Remove a container, tolerating the removal already being under way.

    Docker removes containers asynchronously, so a force-remove can collide with a removal
    already in progress and answer 409 Conflict. That exception propagated out of the
    sandbox and aborted the whole reproduction with "internal error", discarding a run that
    had actually completed.
    """
    for _ in range(3):
        try:
            container.remove(force=True)
            return
        except docker.errors.NotFound:
            return
        except docker.errors.APIError as e:
            message = str(e).lower()
            if "already in progress" in message or "is being removed" in message:
                time.sleep(0.5)
                continue
            return
        except Exception:
            return


def _remove_container_by_name(client, name: str, timeout_s: float = 10.0) -> None:
    """Free a container name before reusing it, waiting for any in-flight removal."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            existing = client.containers.get(name)
        except docker.errors.NotFound:
            return
        except Exception:
            return
        _safe_remove(existing)
        time.sleep(0.3)


def run_container(
    project_id: str,
    workspace: Path,
    is_setup: bool,
    command: str,
    kind: str,
    n: int,
    python_image: str = "rerun-base:py311",
    run_timeout_override: Optional[int] = None,
) -> RunResult:
    limits = get_limits()
    client = docker.from_env()

    # 1. Create workspace output dir and log file.
    outputs_dir = workspace / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        _make_tree_group_writable(workspace)

    log_dir = paths.logs_dir(project_id)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{kind}_{n}.log"

    # 2. Build spec and run
    spec = build_container_spec(project_id, workspace, is_setup, command, python_image=python_image)
    container_name = f"rerun_{project_id}_{kind}_{n}"
    _remove_container_by_name(client, container_name)
    spec["name"] = container_name

    container = client.containers.run(**spec)
    with _ACTIVE_CONTAINERS_LOCK:
        _ACTIVE_CONTAINERS[project_id] = container.id

    start_time = time.time()

    def stream_logs():
        written_bytes = 0
        with open(log_path, "wb") as f:
            for chunk in container.logs(stream=True, follow=True):
                if written_bytes < limits.log_cap_bytes:
                    try:
                        text_chunk = chunk.decode("utf-8", errors="replace")
                        scrubbed_text = scrub_secrets(text_chunk)
                        chunk_to_write = scrubbed_text.encode("utf-8")
                    except Exception:
                        chunk_to_write = chunk
                    allowed = limits.log_cap_bytes - written_bytes
                    to_write = chunk_to_write[:allowed]
                    f.write(to_write)
                    written_bytes += len(to_write)

    log_thread = threading.Thread(target=stream_logs)
    log_thread.daemon = True
    log_thread.start()

    timeout_s = limits.install_timeout_s if is_setup else (run_timeout_override or limits.run_timeout_s)

    # 3. Wait
    timed_out = False
    try:
        result = container.wait(timeout=timeout_s)
        exit_code = result.get("StatusCode")
    except Exception as e:
        err_str = str(e).lower()
        if (
            "timeout" in err_str
            or "timed out" in err_str
            or type(e).__name__ == "ReadTimeout"
            or type(e).__name__ == "TimeoutError"
        ):
            try:
                container.kill()
            except Exception:
                pass
            exit_code = None
            timed_out = True
        else:
            try:
                container.kill()
            except Exception:
                pass
            exit_code = -1
            timed_out = False

    log_thread.join(timeout=2.0)
    duration_s = time.time() - start_time

    # 4. Check OOM
    try:
        container.reload()
        oom = container.attrs.get("State", {}).get("OOMKilled", False)
    except Exception:
        oom = False

    # Harvest outputs
    dest_output_dir = paths.run_dir(project_id) / "outputs" / f"run_{n}"
    dest_output_dir.mkdir(parents=True, exist_ok=True)
    if outputs_dir.exists():
        import shutil
        for item in outputs_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, dest_output_dir / item.name)
            elif item.is_dir():
                shutil.copytree(item, dest_output_dir / item.name, dirs_exist_ok=True)

    # 5. Remove container
    _safe_remove(container)
    with _ACTIVE_CONTAINERS_LOCK:
        _ACTIVE_CONTAINERS.pop(project_id, None)

    return RunResult(
        exit_code=exit_code,
        timed_out=timed_out,
        oom=oom,
        log_path=str(log_path),
        duration_s=duration_s,
        output_dir=str(dest_output_dir),
    )
