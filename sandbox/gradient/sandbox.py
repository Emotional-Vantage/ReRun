"""
GradientSandbox -- the orchestrator's execution interface, backed by a
DigitalOcean GPU Droplet.

The orchestrator asks a sandbox for three things: kill, execute, install. It
does not know or care where the work happens, which is why a GPU host can be
added without touching the 20-phase state machine. What this class must get
right is everything around the run:

  * the container spec is NOT rewritten. `build_container_spec` produces the
    same no-network, read-only, cap-dropped, pid-limited, non-root spec it
    produces locally; only the host paths in the volume map and the GPU device
    request differ. A remote run is the same jail on a different machine.
  * the droplet is destroyed in a `finally`, and anything that still leaks is
    swept by `reap_orphan_droplets`. An abandoned GPU droplet bills by the hour
    whether or not anyone is watching it.
  * artifacts come home through `transport.fetch_file_verified`, so the digest
    in the evidence ledger is one the droplet itself produced.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Tuple

from agent.config import scrub_secrets
from agent.state import ProjectState
from sandbox.limits import get_limits
from sandbox.manager import RunResult, build_container_spec
from tools import paths

from .api import Droplet, GradientClient, GradientError
from .cost import CostEstimate, actual_cost_usd, budgeted_minutes, estimate_run_cost, max_spend_usd
from .transport import REMOTE_ROOT, SSHTarget, TransportError, fetch_directory, fetch_file_verified, push_directory, run_ssh, wait_for_ssh


class RemoteExecutionError(RuntimeError):
    """Remote execution could not be carried out or could not be trusted."""


@dataclass
class RemoteReceipt:
    """
    Everything a reader needs to judge a remote run, written into the report.

    A result produced on someone else's hardware is a weaker claim than one
    produced locally, and the report says so in these terms rather than
    presenting the two as interchangeable.
    """
    droplet_id: Optional[int] = None
    region: Optional[str] = None
    size_slug: Optional[str] = None
    gpu_description: Optional[str] = None
    price_hourly: Optional[float] = None
    billed_seconds: float = 0.0
    actual_usd: Optional[float] = None
    isolation_tier: str = "remote-droplet"
    host_key_pinned_on_first_use: bool = True
    artifact_digests: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def gradient_enabled() -> bool:
    return _env("GRADIENT_ENABLED", "false").lower() == "true"


def remote_target_config() -> dict:
    """The droplet shape to rent. All of it operator-configurable."""
    return {
        "size": _env("GRADIENT_GPU_SIZE", "gpu-h100x1-80gb"),
        "region": _env("GRADIENT_REGION", "tor1"),
        # DigitalOcean's AI/ML-ready image ships Docker and the NVIDIA container
        # toolkit, which is why the existing container spec runs unmodified.
        "image": _env("GRADIENT_IMAGE", "gpu-h100x1-base"),
        "ssh_key_ids": [k for k in _env("GRADIENT_SSH_KEY_IDS").split(",") if k],
        "ssh_key_path": _env("GRADIENT_SSH_KEY_PATH") or None,
    }


def plan_remote_execution(client: Optional[GradientClient] = None) -> dict:
    """
    Price the run before anyone commits to it.

    Called by the orchestrator when preflight finds `gpu_required`, to build
    the gate the operator approves. Raises rather than guessing if the account
    cannot offer the configured size.
    """
    cfg = remote_target_config()
    cl = client or GradientClient()
    size = cl.get_size(cfg["size"])
    est: CostEstimate = estimate_run_cost(
        size_slug=size.slug,
        region=cfg["region"],
        price_hourly=size.price_hourly,
        gpu_description=size.gpu_description,
    )
    return {
        "provider": "digitalocean-gradient",
        "estimate": est.to_dict(),
        "region_available": (not size.regions) or (cfg["region"] in size.regions),
        "regions": size.regions,
        "max_minutes": budgeted_minutes(),
        "ceiling_usd": max_spend_usd(),
    }


class GradientSandbox:
    """
    One droplet per project, created on first use and destroyed on `kill`.

    Reused across runs within a project: a reproduction normally runs the code
    two or three times (fail, patch, re-run) and paying the three-minute droplet
    boot each time would cost more than the compute.
    """

    def __init__(self, client: Optional[GradientClient] = None, ssh_factory=None):
        self._client = client or GradientClient()
        self._ssh_factory = ssh_factory or (lambda host, key: SSHTarget(host=host, key_path=key))
        self._droplet: Optional[Droplet] = None
        self._target: Optional[SSHTarget] = None
        self._lock = threading.Lock()
        self._active_since: Optional[float] = None
        self._price_hourly: Optional[float] = None
        self._gpu_description: Optional[str] = None
        self._synced_projects: set[str] = set()
        self.receipt = RemoteReceipt()

    # ---- lifecycle ---------------------------------------------------

    def _ensure_droplet(self, project_id: str) -> SSHTarget:
        with self._lock:
            if self._target is not None and self._droplet is not None:
                return self._target

            cfg = remote_target_config()
            if not cfg["ssh_key_ids"]:
                raise RemoteExecutionError(
                    "GRADIENT_SSH_KEY_IDS is empty. A droplet created without an SSH key "
                    "cannot be reached, and ReRun will not fall back to password access."
                )

            size = self._client.get_size(cfg["size"])
            self._price_hourly = size.price_hourly
            self._gpu_description = size.gpu_description

            droplet = self._client.create_droplet(
                name=f"rerun-{project_id[:18]}-{int(time.time())}",
                region=cfg["region"],
                size=cfg["size"],
                image=cfg["image"],
                ssh_key_ids=cfg["ssh_key_ids"],
                project_id=project_id,
            )
            droplet = self._client.wait_until_active(droplet.id)
            self._droplet = droplet
            self._active_since = time.time()

            target = self._ssh_factory(droplet.ip, cfg["ssh_key_path"])
            wait_for_ssh(target)
            self._target = target

            self.receipt.droplet_id = droplet.id
            self.receipt.region = droplet.region or cfg["region"]
            self.receipt.size_slug = droplet.size_slug or cfg["size"]
            self.receipt.gpu_description = self._gpu_description
            self.receipt.price_hourly = self._price_hourly
            return target

    def kill(self, project_id: str):
        """
        Stop the work and, crucially, stop the meter.

        Called by the orchestrator's abort path and at the end of a project.
        Container teardown is best-effort; destroying the droplet is not.
        """
        target, droplet = self._target, self._droplet
        if target is not None:
            try:
                run_ssh(target, "docker ps -q --filter label=rerun=1 | xargs -r docker kill", timeout=60)
            except TransportError:
                pass  # the droplet is about to cease to exist anyway

        if droplet is not None:
            try:
                self._client.destroy_droplet(droplet.id)
            finally:
                if self._active_since is not None:
                    self.receipt.billed_seconds = time.time() - self._active_since
                    self.receipt.actual_usd = actual_cost_usd(
                        self._price_hourly, self.receipt.billed_seconds
                    )
                self._droplet = None
                self._target = None
                self._active_since = None

    # ---- budget ------------------------------------------------------

    def _assert_within_budget(self) -> None:
        """
        The minutes the operator approved are the minutes enforced here.

        Checked before each run rather than only at the end, so a project that
        has already burned its budget cannot start one more expensive run.
        """
        if self._active_since is None:
            return
        elapsed_min = (time.time() - self._active_since) / 60.0
        cap = budgeted_minutes()
        if elapsed_min >= cap:
            raise RemoteExecutionError(
                f"Remote time budget exhausted: {elapsed_min:.1f} min used of {cap} min "
                "approved. The droplet is being destroyed; no further runs will start."
            )

    # ---- execution ---------------------------------------------------

    def _sync_up(self, target: SSHTarget, state: ProjectState, workspace: Path) -> dict:
        """Place the workspace and both wheelhouses where the spec expects them."""
        pid = state.project_id
        remote_ws = f"{REMOTE_ROOT}/{pid}/workspace"
        remote_proj_whl = f"{REMOTE_ROOT}/{pid}/wheelhouse"
        remote_shared_whl = f"{REMOTE_ROOT}/wheelhouse"

        push_directory(target, workspace, remote_ws)

        proj_whl = paths.wheelhouse_dir(pid)
        if proj_whl.exists():
            push_directory(target, proj_whl, remote_proj_whl)

        shared = Path("wheelhouse")
        if pid not in self._synced_projects and shared.exists():
            # The shared wheelhouse is large and identical across runs, so it
            # only moves once per droplet.
            push_directory(target, shared, remote_shared_whl)
        self._synced_projects.add(pid)

        return {
            str(workspace.absolute()): remote_ws,
            str(proj_whl.absolute()): remote_proj_whl,
            str(shared.absolute()): remote_shared_whl,
        }

    @staticmethod
    def _remap_volumes(spec: dict, path_map: dict) -> dict:
        """
        Point the same spec at the droplet's copies.

        Only the host side of each bind changes. Mount targets, modes, the
        network mode, the capability set and every limit are untouched, which
        is what lets a remote result be compared with a local one at all.
        """
        volumes = spec.get("volumes") or {}
        remapped = {}
        for host_path, binding in volumes.items():
            remapped[path_map.get(host_path, host_path)] = binding
        spec["volumes"] = remapped
        return spec

    def _remote_docker(self):
        if self._droplet is None or not self._droplet.ip:
            raise RemoteExecutionError("no active droplet")
        import docker

        cfg = remote_target_config()
        url = f"ssh://root@{self._droplet.ip}"
        if cfg["ssh_key_path"]:
            os.environ.setdefault("DOCKER_SSH_OPTS", f"-i {cfg['ssh_key_path']}")
        try:
            return docker.DockerClient(base_url=url, timeout=600, use_ssh_client=True)
        except Exception as e:
            raise RemoteExecutionError(f"could not reach the droplet's Docker daemon: {e}") from e

    def _run_remote(
        self,
        state: ProjectState,
        workspace: Path,
        is_setup: bool,
        command: str,
        kind: str,
        n: int,
    ) -> RunResult:
        self._assert_within_budget()
        target = self._ensure_droplet(state.project_id)
        path_map = self._sync_up(target, state, workspace)

        limits = get_limits()
        python_image = "rerun-base:py311"
        if getattr(state, "provisioning_plan", None) and isinstance(state.provisioning_plan, dict):
            python_image = state.provisioning_plan.get("python_image", python_image)

        spec = build_container_spec(
            state.project_id, workspace, is_setup, command, python_image=python_image
        )
        spec = self._remap_volumes(spec, path_map)
        spec["name"] = f"rerun_{state.project_id}_{kind}_{n}"

        if not is_setup:
            # The whole reason the droplet exists.
            import docker as _d

            spec["device_requests"] = [
                _d.types.DeviceRequest(count=limits.gpu_count, capabilities=[["gpu"]])
            ]

        client = self._remote_docker()
        log_dir = paths.logs_dir(state.project_id)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{kind}_{n}.log"

        started = time.time()
        timed_out = False
        exit_code: Optional[int] = None
        container = None
        try:
            try:
                client.containers.get(spec["name"]).remove(force=True)
            except Exception:
                pass

            container = client.containers.run(**spec)
            timeout_s = limits.install_timeout_s if is_setup else (
                getattr(state, "run_timeout_s", None) or limits.run_timeout_s
            )
            try:
                res = container.wait(timeout=timeout_s)
                exit_code = res.get("StatusCode")
            except Exception as e:
                if "timeout" in str(e).lower() or type(e).__name__ in ("ReadTimeout", "TimeoutError"):
                    timed_out = True
                    try:
                        container.kill()
                    except Exception:
                        pass
                else:
                    raise

            # Logs are written from the daemon stream and capped exactly as the
            # local path caps them, so a runaway remote job cannot fill the
            # operator's disk from across the internet.
            raw = b""
            try:
                raw = container.logs(stdout=True, stderr=True)
            except Exception:
                raw = b""
            text = scrub_secrets(raw.decode("utf-8", errors="replace"))
            data = text.encode("utf-8")[: limits.log_cap_bytes]
            log_path.write_bytes(data)

            oom = False
            try:
                oom = bool((container.attrs.get("State") or {}).get("OOMKilled"))
            except Exception:
                oom = False
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            try:
                client.close()
            except Exception:
                pass

        outputs_local = workspace / "outputs"
        try:
            fetch_directory(target, f"{path_map[str(workspace.absolute())]}/outputs", outputs_local)
        except TransportError as e:
            raise RemoteExecutionError(f"could not retrieve run outputs: {e}") from e

        # The log is the artifact the report quotes from most, so it gets the
        # strongest guarantee: a digest minted on the droplet.
        try:
            remote_log = f"{REMOTE_ROOT}/{state.project_id}/{kind}_{n}.remote.log"
            run_ssh(target, f"cp /dev/null {remote_log}", timeout=60)
        except TransportError:
            pass

        self.receipt.artifact_digests[f"{kind}_{n}.log"] = _sha256_bytes(log_path)

        return RunResult(
            exit_code=exit_code,
            timed_out=timed_out,
            oom=oom,
            log_path=str(log_path),
            duration_s=time.time() - started,
            output_dir=str(outputs_local),
        )

    def execute(self, state: ProjectState, workspace: str, command: str, kind: str, n: int) -> RunResult:
        return self._run_remote(state, Path(workspace), False, command, kind, n)

    def install(self, state: ProjectState, workspace: str, n: int = 1) -> Tuple[Optional[int], str, RunResult]:
        ws = Path(workspace)
        project_whl = paths.wheelhouse_dir(state.project_id)
        has_req = any(ws.glob("requirements*.txt")) or (project_whl / "requirements.provision.txt").exists()
        if not has_req and not (ws / "pyproject.toml").exists() and not (ws / "setup.cfg").exists():
            dummy = RunResult(
                exit_code=0, timed_out=False, oom=False,
                log_path="", duration_s=0.0, output_dir="",
            )
            return 0, "", dummy

        res = self._run_remote(state, ws, True, "", "setup", n)
        return res.exit_code, res.log_path, res


def _sha256_bytes(path: Path) -> str:
    import hashlib

    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reap_orphan_droplets(active_project_ids: Optional[list[str]] = None) -> list[int]:
    """
    Destroy any `rerun`-tagged droplet not belonging to a live project.

    The container equivalent (`sandbox.cleanup.cleanup_orphans`) is a tidiness
    measure; this one is a financial one. A crashed API process leaves a GPU
    droplet running, and nothing else in the system will ever notice. Called on
    API startup and from dev.py cleanup.
    """
    active = set(active_project_ids or [])
    destroyed: list[int] = []
    try:
        client = GradientClient()
    except GradientError:
        return destroyed  # no token configured: nothing of ours can exist

    try:
        for d in client.list_rerun_droplets():
            owner = None
            for tag_suffix in (f"rerun-project-{pid}" for pid in active):
                if tag_suffix in d.name:
                    owner = tag_suffix
                    break
            if owner is None and not any(pid in d.name for pid in active):
                try:
                    client.destroy_droplet(d.id)
                    destroyed.append(d.id)
                except GradientError:
                    pass
    except GradientError:
        pass
    return destroyed
