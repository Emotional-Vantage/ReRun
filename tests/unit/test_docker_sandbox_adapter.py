import inspect
from pathlib import Path
from sandbox.docker_sandbox import DockerSandbox
from sandbox.fake import FakeSandbox
from sandbox.manager import RunResult
from agent.state import ProjectState


def test_docker_sandbox_interface():
    ds = DockerSandbox()
    assert hasattr(ds, "execute"), "DockerSandbox must provide execute()"
    assert hasattr(ds, "install"), "DockerSandbox must provide install()"

    # Check method signatures
    exec_sig = inspect.signature(ds.execute)
    assert list(exec_sig.parameters.keys()) == ["state", "workspace", "command", "kind", "n"]

    inst_sig = inspect.signature(ds.install)
    assert list(inst_sig.parameters.keys()) == ["state", "workspace", "n"]


def test_fake_sandbox_interface_matches():
    fs = FakeSandbox()
    assert hasattr(fs, "execute"), "FakeSandbox must provide execute()"
    assert hasattr(fs, "install"), "FakeSandbox must provide install()"

    exec_sig = inspect.signature(fs.execute)
    assert list(exec_sig.parameters.keys()) == ["state", "workspace", "command", "kind", "n"]

    inst_sig = inspect.signature(fs.install)
    assert list(inst_sig.parameters.keys()) == ["state", "workspace", "n"]


def test_fake_sandbox_execution_return_type(tmp_path):
    fs = FakeSandbox(exit_code=0, output_text="Adapter test log")
    state = ProjectState(
        project_id="test_adapter",
        benchmark_id="b1_control",
        repo_commit="abc",
        phase="RUN",
        budgets={"steps_used": 0, "max_steps": 40},
        claims=[],
        paper_settings=[],
        repo_profile={},
    )
    ws = str(tmp_path / "workspace")
    Path(ws).mkdir(parents=True)

    res = fs.execute(state, ws, "python train.py", "run", 1)
    assert isinstance(res, RunResult)
    assert hasattr(res, "exit_code")
    assert hasattr(res, "log_path")
    assert hasattr(res, "output_dir")
    assert hasattr(res, "duration_s")
    assert hasattr(res, "timed_out")
    assert hasattr(res, "oom")

    # Test install
    code, log, inst_res = fs.install(state, ws, 1)
    assert code == 0
    assert isinstance(inst_res, RunResult)
