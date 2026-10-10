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

def run_b2(case_id, case_info, run_n=1):
    """
    B-2 One-Shot Baseline.
    Per spec:
    1. First attempt runs like B-0.
    2. If successful (b1), returns REPRODUCED.
    3. If failed (crash or number mismatch), applies ONE blind repair edit.
    4. Reruns once.
    5. Returns outcome of the one-shot rerun.
    """
    workspace = Path(f"data/runs/b2/{case_id}_{run_n}").absolute()
    if workspace.exists():
        shutil.rmtree(workspace, onerror=remove_readonly)
        
    shutil.copytree(case_info["repo_path"], workspace)
    
    # Preflight check: check if repo feasibility blocks execution (e.g. NEEDS_GPU)
    try:
        from tools.triage import triage_report
        triage = triage_report(str(workspace))
        if triage.get("verdict") == "NEEDS_GPU" or "gpu_required" in triage.get("blockers", []):
            return "UNABLE_TO_EXECUTE"
    except ImportError:
        req_file = workspace / "requirements.txt"
        model_file = workspace / "model.py"
        if req_file.exists() and "torch" in req_file.read_text():
            if model_file.exists() and "cuda" in model_file.read_text():
                return "UNABLE_TO_EXECUTE"

    paper_path = case_info["paper_path"]
    paper_text = ""
    with fitz.open(paper_path) as doc:
        for page in doc:
            paper_text += page.get_text()
            
    match = re.search(r'test accuracy of (\d+\.\d+)', paper_text)
    if not match:
        raise RuntimeError("Could not find target number in paper")
    target_mean = float(match.group(1))
    
    # Step 1: Initial Setup
    setup_res = run_container(
        project_id=f"b2_{case_id}_{run_n}",
        workspace=workspace,
        is_setup=True,
        command="",
        kind="setup",
        n=1
    )
    
    readme_file = workspace / "README.md"
    readme = readme_file.read_text() if readme_file.exists() else ""
    cmd = "python train.py --config configs/default.yaml"
    for line in readme.split('\n'):
        if line.startswith("python "):
            cmd = line.strip()
            break
            
    initial_passed = False
    initial_error = None
    actual_mean = None
    
    if setup_res.exit_code == 0:
        run_res = run_container(
            project_id=f"b2_{case_id}_{run_n}",
            workspace=workspace,
            is_setup=False,
            command=cmd,
            kind="run",
            n=1
        )
        if run_res.exit_code == 0:
            out_json = workspace / "outputs" / "results.json"
            if out_json.exists():
                try:
                    with open(out_json, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    actual_mean = data.get("test_accuracy_mean")
                    if actual_mean is not None and abs(actual_mean - target_mean) <= 0.01:
                        initial_passed = True
                except Exception:
                    pass
        else:
            log_f = Path(run_res.log_path) if getattr(run_res, "log_path", None) else None
            if log_f and log_f.exists():
                initial_error = log_f.read_text()
    else:
        log_f = Path(setup_res.log_path) if getattr(setup_res, "log_path", None) else None
        if log_f and log_f.exists():
            initial_error = log_f.read_text()

    if initial_passed:
        return "REPRODUCED"

    # One-shot repair attempt based on error
    repaired = False
    if initial_error and "yaml" in initial_error.lower():
        req_file = workspace / "requirements.txt"
        if req_file.exists():
            req_content = req_file.read_text()
            if "pyyaml" not in req_content.lower():
                req_file.write_text(req_content + "\nPyYAML==6.0.1\n")
                repaired = True
    elif actual_mean is not None and abs(actual_mean - target_mean) > 0.01:
        cfg_file = workspace / "configs" / "default.yaml"
        if cfg_file.exists():
            cfg_text = cfg_file.read_text()
            # If paper mentions learning rate = 0.5
            lr_match = re.search(r'learning rate = (\d+\.\d+)', paper_text)
            if lr_match:
                paper_lr = lr_match.group(1)
                cfg_text = re.sub(r'learning_rate:\s*[\d\.]+', f'learning_rate: {paper_lr}', cfg_text)
                cfg_file.write_text(cfg_text)
                repaired = True

    if not repaired:
        return "FAILED_TO_RUN" if not actual_mean else "NUMBER_MISMATCH"

    # Rerun setup & run after one repair
    rerun_setup = run_container(
        project_id=f"b2_{case_id}_{run_n}",
        workspace=workspace,
        is_setup=True,
        command="",
        kind="setup",
        n=2
    )
    if rerun_setup.exit_code != 0:
        return "FAILED_TO_RUN"

    rerun_res = run_container(
        project_id=f"b2_{case_id}_{run_n}",
        workspace=workspace,
        is_setup=False,
        command=cmd,
        kind="run",
        n=2
    )
    if rerun_res.exit_code != 0:
        return "FAILED_TO_RUN"

    out_json = workspace / "outputs" / "results.json"
    if not out_json.exists():
        return "FAILED_TO_RUN"
    try:
        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        new_mean = data.get("test_accuracy_mean")
        if new_mean is not None and abs(new_mean - target_mean) <= 0.01:
            return "REPRODUCED"
        return "NUMBER_MISMATCH"
    except Exception:
        return "FAILED_TO_RUN"
