import os
import json
from dataclasses import dataclass
from typing import Optional, Dict, Tuple
from pathlib import Path

from .manager import RunResult
from tools import paths


class FakeSandbox:
    """Mock sandbox implementation for testing state transitions and canned scenarios."""

    def __init__(
        self,
        exit_code: Optional[int] = 0,
        timed_out: bool = False,
        oom: bool = False,
        output_text: str = "",
    ):
        self.exit_code = exit_code
        self.timed_out = timed_out
        self.oom = oom
        self.output_text = output_text
        self.calls = []
        self.canned_runs: Dict[Tuple[str, int], Tuple[int, str, dict]] = {}

    def register(self, case_id: str, run_n: int, exit_code: int, logs: str, outputs: dict):
        self.canned_runs[(case_id, run_n)] = (exit_code, logs, outputs)

    def kill(self, project_id: str):
        """Mock kill method."""
        pass

    def execute(self, state, workspace: str, command: str, kind: str, n: int) -> RunResult:
        case_id = getattr(state, "benchmark_id", "default")
        if (case_id, n) in self.canned_runs:
            exit_code, logs, outputs = self.canned_runs[(case_id, n)]
        else:
            exit_code = self.exit_code if self.exit_code is not None else 0
            logs = self.output_text if self.output_text else "Execution completed successfully"
            outputs = {
                "test_accuracy_mean": 0.956,
                "test_accuracy_per_seed": [0.955, 0.957, 0.956, 0.956, 0.956],
                "test_accuracy_std": 0.001,
            }

        ws = Path(workspace)
        log_dir = ws / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{kind}_{n}.log"
        log_file.write_text(logs, encoding="utf-8")

        # Also write to data/runs/<id>/logs if state has project_id
        project_id = getattr(state, "project_id", "test_proj")
        data_log_dir = paths.logs_dir(project_id)
        data_log_dir.mkdir(parents=True, exist_ok=True)
        (data_log_dir / f"{kind}_{n}.log").write_text(logs, encoding="utf-8")

        out_dir = ws / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        res_file = out_dir / "results.json"
        res_file.write_text(json.dumps(outputs), encoding="utf-8")

        dest_output_dir = paths.run_dir(project_id) / "outputs" / f"run_{n}"
        dest_output_dir.mkdir(parents=True, exist_ok=True)
        (dest_output_dir / "results.json").write_text(json.dumps(outputs), encoding="utf-8")

        return RunResult(
            exit_code=exit_code,
            timed_out=self.timed_out,
            oom=self.oom,
            log_path=str(log_file),
            duration_s=0.1,
            output_dir=str(out_dir),
        )

    def install(self, state, workspace: str, n: int = 1) -> Tuple[int, str, RunResult]:
        project_id = getattr(state, "project_id", "test_proj")
        log_dir = paths.logs_dir(project_id)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"setup_{n}.log"
        log_file.write_text("Setup install succeeded (fake)", encoding="utf-8")

        res = RunResult(
            exit_code=0,
            timed_out=False,
            oom=False,
            log_path=str(log_file),
            duration_s=0.1,
            output_dir="",
        )
        return 0, str(log_file), res

    def run_container(
        self,
        project_id: str,
        workspace: Path,
        is_setup: bool,
        command: str,
        kind: str,
        n: int,
    ) -> RunResult:
        self.calls.append({
            "project_id": project_id,
            "workspace": workspace,
            "is_setup": is_setup,
            "command": command,
            "kind": kind,
            "n": n,
        })

        log_dir = paths.logs_dir(project_id)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{kind}_{n}.log"
        with open(log_path, "w") as f:
            f.write(self.output_text if self.output_text else "Execution completed successfully")

        dest_output_dir = paths.run_dir(project_id) / "outputs" / f"run_{n}"
        dest_output_dir.mkdir(parents=True, exist_ok=True)

        return RunResult(
            exit_code=self.exit_code,
            timed_out=self.timed_out,
            oom=self.oom,
            log_path=str(log_path),
            duration_s=0.1,
            output_dir=str(dest_output_dir),
        )


def get_sandbox():
    """Returns the active sandbox: DockerSandbox by default, or FakeSandbox if SANDBOX_TYPE=fake and ALLOW_FAKE_SANDBOX=1."""
    sandbox_type = os.getenv("SANDBOX_TYPE", "docker")
    if sandbox_type == "fake":
        if os.getenv("ALLOW_FAKE_SANDBOX") != "1":
            raise RuntimeError("Refusing to select FakeSandbox without ALLOW_FAKE_SANDBOX=1.")
        return FakeSandbox()
    from sandbox.docker_sandbox import DockerSandbox
    return DockerSandbox()
