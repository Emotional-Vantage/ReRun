import json
import re
import sys
import os
import shutil
import stat
from pathlib import Path

sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from sandbox.manager import run_container
import fitz  # PyMuPDF

def remove_readonly(func, path, _):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def run_b0(case_id, case_info, run_n=1):
    workspace = Path(f"data/runs/b0/{case_id}_{run_n}").absolute()
    if workspace.exists():
        shutil.rmtree(workspace, onerror=remove_readonly)
        
    shutil.copytree(case_info["repo_path"], workspace)
    
    paper_path = case_info["paper_path"]
    paper_text = ""
    with fitz.open(paper_path) as doc:
        for page in doc:
            paper_text += page.get_text()
            
    match = re.search(r'test accuracy of (\d+\.\d+)', paper_text)
    if not match:
        raise RuntimeError("Could not find target number in paper")
    target_mean = float(match.group(1))
    
    # Preflight check: check if repo feasibility blocks execution (e.g. NEEDS_GPU)
    try:
        from tools.triage import triage_report
        triage = triage_report(str(workspace))
        if triage.get("verdict") == "NEEDS_GPU" or "gpu_required" in triage.get("blockers", []):
            return "UNABLE_TO_EXECUTE"
    except ImportError:
        # Fallback if tools.triage not yet implemented
        req_file = workspace / "requirements.txt"
        model_file = workspace / "model.py"
        if req_file.exists() and "torch" in req_file.read_text():
            if model_file.exists() and "cuda" in model_file.read_text():
                return "UNABLE_TO_EXECUTE"
    
    setup_res = run_container(
        project_id=f"b0_{case_id}_{run_n}",
        workspace=workspace,
        is_setup=True,
        command="",
        kind="setup",
        n=1
    )
    if setup_res.exit_code != 0:
        return "FAILED_TO_RUN"
        
    readme_file = workspace / "README.md"
    readme = readme_file.read_text() if readme_file.exists() else ""
    cmd = "python train.py --config configs/default.yaml"
    for line in readme.split('\n'):
        if line.startswith("python "):
            cmd = line.strip()
            break
            
    run_res = run_container(
        project_id=f"b0_{case_id}_{run_n}",
        workspace=workspace,
        is_setup=False,
        command=cmd,
        kind="run",
        n=1
    )
    
    if run_res.exit_code != 0:
        return "FAILED_TO_RUN"
        
    out_json = workspace / "outputs" / "results.json"
    if not out_json.exists():
        return "FAILED_TO_RUN"
        
    with open(out_json, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    actual_mean = data.get("test_accuracy_mean")
    if actual_mean is None:
        return "FAILED_TO_RUN"
        
    if abs(actual_mean - target_mean) <= 0.01:
        return "REPRODUCED"
    else:
        return "NUMBER_MISMATCH"
