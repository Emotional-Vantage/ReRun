import os
import json
import shutil
import pytest
from pathlib import Path

from tools.provisioning import (
    parse_dependency_files,
    select_python_image,
    check_package_wheel_availability,
    build_provisioning_plan,
    download_wheels_for_project,
    detect_typosquat
)
from sandbox.manager import build_container_spec, run_container
from sandbox.docker_sandbox import DockerSandbox
from agent.state import ProjectState
from tools import paths

def test_python_image_selection(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    
    pyproject.write_text('requires-python = ">=3.9, <3.10"')
    assert select_python_image(str(tmp_path)) == "rerun-base:py39"

    pyproject.write_text('requires-python = ">=3.10, <3.11"')
    assert select_python_image(str(tmp_path)) == "rerun-base:py310"

    pyproject.write_text('requires-python = ">=3.11, <3.12"')
    assert select_python_image(str(tmp_path)) == "rerun-base:py311"

    pyproject.write_text('requires-python = ">=3.12"')
    assert select_python_image(str(tmp_path)) == "rerun-base:py312"

    assert select_python_image(str(tmp_path), {"python_requires": "3.9"}) == "rerun-base:py39"
    assert select_python_image(str(tmp_path), {"python_requires": "3.12"}) == "rerun-base:py312"

def test_static_dependency_parsing_without_code_execution(tmp_path):
    req1 = tmp_path / "requirements.txt"
    req1.write_text("scikit-learn==1.9.1\npandas>=2.0.0\n# comment\n-r dev.txt\n")

    cfg = tmp_path / "setup.cfg"
    cfg.write_text("[options]\ninstall_requires =\n    matplotlib>=3.5.0\n    scipy\n")

    pyproj = tmp_path / "pyproject.toml"
    pyproj.write_text('[project]\ndependencies = [\n    "pyyaml>=6.0",\n    "numpy==1.26.4"\n]\n')

    env_yaml = tmp_path / "environment.yml"
    env_yaml.write_text("name: test\ndependencies:\n  - python=3.11\n  - pip:\n    - joblib>=1.3.0\n")

    trap_file = tmp_path / "setup.py"
    trap_file.write_text("raise RuntimeError('setup.py executed!')")

    parsed = parse_dependency_files(str(tmp_path))
    names = {p["name"] for p in parsed}

    assert "scikit-learn" in names
    assert "pandas" in names
    assert "matplotlib" in names
    assert "scipy" in names
    assert "pyyaml" in names
    assert "numpy" in names
    assert "joblib" in names

    assert trap_file.exists()

def test_typosquatting_and_dependency_drift_warnings(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("numppy\nreqeusts==2.28.0\npandas\ntorch\n")

    plan = build_provisioning_plan(str(tmp_path), "proj_warnings_test")
    warnings = " ".join(plan["warnings"])

    assert "numppy" in warnings and "numpy" in warnings
    assert "reqeusts" in warnings and "requests" in warnings
    assert "Dependency drift risk" in warnings
    assert "torch" in warnings

def test_sdist_only_dependency_triggers_needs_build_without_code_execution(tmp_path):
    ws = tmp_path / "sdist_repo"
    ws.mkdir()

    req = ws / "requirements.txt"
    req.write_text("numpy\nuncompiled_sdist_pkg==0.1.0\n")

    trap_marker = ws / "TRAP_TRIGGERED.txt"
    setup_py = ws / "setup.py"
    setup_py.write_text(f"open('{trap_marker}', 'w').write('TRAPPED')\nraise SystemExit('Trap executed!')\n")

    plan = build_provisioning_plan(str(ws), "proj_sdist_test")
    assert plan["status"] == "NEEDS_BUILD"
    assert "NEEDS_BUILD" in plan["reason"]
    assert "uncompiled_sdist_pkg" in plan["sdist_blockers"] or "uncompiled-sdist-pkg" in plan["sdist_blockers"]
    assert not trap_marker.exists()

def test_fixture_repo_data_science_stack_installs_and_runs_offline(tmp_path):
    try:
        import docker
        docker.from_env().ping()
    except Exception:
        pytest.skip("Docker daemon not available")

    project_id = "proj_ds_fixture_offline"
    run_dir = paths.run_dir(project_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    ws = run_dir / "workspace"
    ws.mkdir(parents=True, exist_ok=True)

    (ws / "requirements.txt").write_text("scikit-learn\npandas\nmatplotlib\n")

    script = ws / "experiment.py"
    script.write_text("""import sys
sys.path.insert(0, '/workspace/.site')
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
import json
from pathlib import Path

df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [0, 0, 1, 1]})
clf = LogisticRegression()
clf.fit(df[["x"]], df["y"])
preds = clf.predict([[2.5]])

plt.figure()
plt.plot(df["x"], df["y"])
plt.savefig("/workspace/outputs/plot.png")

res = {
    "test_accuracy_mean": 0.95,
    "pred_at_2_5": int(preds[0]),
    "rows": len(df)
}

Path("/workspace/outputs/results.json").write_text(json.dumps(res))
print("EXPERIMENT_COMPLETE")
""")

    target_whl = run_dir / "wheelhouse"
    prov_res = download_wheels_for_project(
        project_id=project_id,
        packages=["scikit-learn", "pandas", "matplotlib"],
        dest_wheelhouse=target_whl,
        python_image="rerun-base:py311",
        allow_network=False
    )
    assert prov_res["success"] is True

    sandbox = DockerSandbox()
    state = ProjectState(
        project_id=project_id,
        source="custom",
        phase="SETUP",
        workspace=str(ws),
        budgets={"steps_used": 0, "patches_used": 0},
        claims=[],
        paper_settings=[],
        provisioning_approved=True,
        provisioning_plan={"python_image": "rerun-base:py311"}
    )

    exit_code, log_path, run_res = sandbox.install(state, str(ws), n=1)
    assert exit_code == 0, f"Setup failed with exit {exit_code}. Log:\n{Path(log_path).read_text() if os.path.exists(log_path) else ''}"

    exec_res = sandbox.execute(state, str(ws), "python experiment.py", "run", 1)
    assert exec_res.exit_code == 0, f"Run failed with exit {exec_res.exit_code}. Log:\n{Path(exec_res.log_path).read_text() if os.path.exists(exec_res.log_path) else ''}"

    out_json = ws / "outputs" / "results.json"
    assert out_json.exists()
    data = json.loads(out_json.read_text())
    assert data["test_accuracy_mean"] == 0.95
    assert data["rows"] == 4
    assert (ws / "outputs" / "plot.png").exists()

def test_self_test_after_provisioning_confirms_run_container_offline(tmp_path):
    try:
        import docker
        docker.from_env().ping()
    except Exception:
        pytest.skip("Docker daemon not available")

    project_id = "proj_selftest_offline"
    run_dir = paths.run_dir(project_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    ws = run_dir / "workspace"
    ws.mkdir(parents=True, exist_ok=True)

    script = ws / "net_check.py"
    script.write_text("""import socket
import urllib.request
import json
from pathlib import Path

out = {"network_blocked": True, "error": ""}

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect(("8.8.8.8", 53))
    s.close()
    out["network_blocked"] = False
except Exception as e:
    out["error"] = str(e)

try:
    urllib.request.urlopen("http://1.1.1.1", timeout=2.0)
    out["network_blocked"] = False
except Exception as e:
    pass

Path("/workspace/outputs/net_res.json").write_text(json.dumps(out))
""")

    sandbox = DockerSandbox()
    state = ProjectState(
        project_id=project_id,
        source="custom",
        phase="RUN",
        workspace=str(ws),
        budgets={"steps_used": 0, "patches_used": 0},
        claims=[],
        paper_settings=[]
    )

    spec = build_container_spec(project_id, ws, is_setup=False, command="python net_check.py")
    assert spec["network_mode"] == "none", "Container spec must enforce network_mode='none'"

    exec_res = sandbox.execute(state, str(ws), "python net_check.py", "run", 1)
    assert exec_res.exit_code == 0

    net_res_f = ws / "outputs" / "net_res.json"
    assert net_res_f.exists()
    net_data = json.loads(net_res_f.read_text())
    assert net_data["network_blocked"] is True, f"Network access was NOT blocked! Result: {net_data}"
