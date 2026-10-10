import os
import sys
import json
import shutil
import stat
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from sandbox.manager import run_container

def remove_readonly(func, path, _):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def run_case_headless(case_id: str):
    """
    Runs a benchmark case in the sandbox.
    In Stage 3, this runs the case directly in the sandbox container to verify its execution.
    In Stage 6+, this coordinates with the orchestrator loop.
    """
    reg_path = Path("benchmarks/registry.json")
    if not reg_path.exists():
        print("benchmarks/registry.json not found. Run dev.py build-benchmarks first.")
        sys.exit(1)
        
    with open(reg_path, "r", encoding="utf-8") as f:
        registry = json.load(f)
        
    case_info = next((c for c in registry.get("cases", []) if c["id"] == case_id), None)
    if not case_info:
        print(f"Unknown benchmark case: {case_id}")
        sys.exit(1)
        
    ws_dir = Path(f"data/runs/{case_id}_direct").absolute()
    if ws_dir.exists():
        shutil.rmtree(ws_dir, onerror=remove_readonly)
    shutil.copytree(case_info["case_path"], ws_dir)
    
    print(f"==> Running case {case_id} in sandbox...")
    setup_res = run_container(
        project_id=f"direct_{case_id}",
        workspace=ws_dir,
        is_setup=True,
        command="",
        kind="setup",
        n=1
    )
    print(f"Setup exit code: {setup_res.exit_code}")
    if setup_res.exit_code != 0:
        print("Setup failed. Check setup log.")
        return setup_res
        
    cmd = case_info.get("command", "python train.py --config configs/default.yaml")
    run_res = run_container(
        project_id=f"direct_{case_id}",
        workspace=ws_dir,
        is_setup=False,
        command=cmd,
        kind="run",
        n=1
    )
    print(f"Run exit code: {run_res.exit_code}")
    
    results_path = ws_dir / "outputs" / "results.json"
    if results_path.exists():
        with open(results_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"Results: {data}")
    else:
        print("No outputs/results.json produced.")
        
    return run_res

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_case.py <case_id>")
        sys.exit(1)
    run_case_headless(sys.argv[1])
