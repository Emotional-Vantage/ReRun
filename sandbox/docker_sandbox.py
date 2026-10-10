from pathlib import Path
from typing import Tuple, Optional
from agent.state import ProjectState
from sandbox.manager import run_container, RunResult, kill_project_containers
from tools import paths


class DockerSandbox:
    """Real Docker sandbox adapter implementing the orchestrator execution interface."""

    def kill(self, project_id: str):
        """Immediately kill any running containers for this project."""
        kill_project_containers(project_id)

    def execute(self, state: ProjectState, workspace: str, command: str, kind: str, n: int) -> RunResult:
        """Run an experiment execution container (isolated, offline, CPU/mem/PID capped)."""
        ws = Path(workspace)
        python_image = "rerun-base:py311"
        if getattr(state, "provisioning_plan", None) and isinstance(state.provisioning_plan, dict):
            python_image = state.provisioning_plan.get("python_image", "rerun-base:py311")
        run_timeout = getattr(state, "run_timeout_s", None)
        return run_container(
            project_id=state.project_id,
            workspace=ws,
            is_setup=False,
            command=command,
            kind=kind,
            n=n,
            python_image=python_image,
            run_timeout_override=run_timeout,
        )

    def install(self, state: ProjectState, workspace: str, n: int = 1) -> Tuple[Optional[int], str, RunResult]:
        """Run a setup container mounting the offline wheelhouse to install dependencies."""
        ws = Path(workspace)
        project_whl = paths.wheelhouse_dir(state.project_id)
        has_req = any(ws.glob("requirements*.txt")) or (project_whl / "requirements.provision.txt").exists()
        if not has_req and not (ws / "pyproject.toml").exists() and not (ws / "setup.cfg").exists():
            dummy = RunResult(
                exit_code=0,
                timed_out=False,
                oom=False,
                log_path="",
                duration_s=0.0,
                output_dir="",
            )
            return 0, "", dummy

        python_image = "rerun-base:py311"
        if getattr(state, "provisioning_plan", None) and isinstance(state.provisioning_plan, dict):
            python_image = state.provisioning_plan.get("python_image", "rerun-base:py311")

        res = run_container(
            project_id=state.project_id,
            workspace=ws,
            is_setup=True,
            command="",
            kind="setup",
            n=n,
            python_image=python_image,
        )
        return res.exit_code, res.log_path, res
