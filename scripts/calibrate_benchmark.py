#!/usr/bin/env python3
import json
import shutil
import time
from pathlib import Path
import sys
import os

# Add root to pythonpath
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sandbox.manager import run_container

def main():
    candidates = [0.5, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001, 0.0005]
    
    workspace = Path("calibration_workspace").absolute()
    if workspace.exists():
        import stat
        def remove_readonly(func, path, _):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(workspace, onerror=remove_readonly)
        
    shutil.copytree("benchmarks/template", workspace)
    
    setup_result = run_container(
        project_id="calibration",
        workspace=workspace,
        is_setup=True,
        command="",
        kind="setup",
        n=1
    )
    if setup_result.exit_code != 0:
        raise RuntimeError(f"Setup failed: {setup_result}")

    results = []
    
    for i, lr in enumerate(candidates):
        cmd = f"python train.py --config configs/default.yaml --learning-rate {lr}"
        run_result = run_container(
            project_id="calibration",
            workspace=workspace,
            is_setup=False,
            command=cmd,
            kind="run",
            n=i+1
        )
        if run_result.exit_code != 0:
            print(f"LR {lr} failed to run")
            continue
            
        out_json = workspace / "outputs" / "results.json"
        if out_json.exists():
            with open(out_json) as f:
                data = json.load(f)
            mean_acc = data["test_accuracy_mean"]
            std_acc = data["test_accuracy_std"]
            results.append({"lr": lr, "mean": mean_acc, "std": std_acc})
            print(f"LR {lr}: {mean_acc:.4f} ± {std_acc:.4f}")
            
    # Determinism check
    det_lr = results[0]["lr"]
    cmd = f"python train.py --config configs/default.yaml --learning-rate {det_lr}"
    det_result = run_container("calibration", workspace, False, cmd, "run", len(candidates)+1)
    with open(workspace / "outputs" / "results.json") as f:
        det_data = json.load(f)
    if abs(det_data["test_accuracy_mean"] - results[0]["mean"]) > 1e-6:
        raise RuntimeError("Determinism check failed!")
        
    print("Determinism check passed.")
    
    good_lr = None
    good_mean = None
    good_std = None
    for res in results:
        if 0.85 <= res["mean"] <= 0.97 and res["std"] <= 0.01:
            if good_lr is None or res["mean"] > good_mean:
                good_lr = res["lr"]
                good_mean = res["mean"]
                good_std = res["std"]
                
    if good_lr is None:
        raise RuntimeError("Could not find a good_lr")
        
    bad_lr = None
    bad_mean = None
    for res in sorted(results, key=lambda x: -x["lr"]):
        if res["lr"] != good_lr and (good_mean - res["mean"]) >= 0.08:
            bad_lr = res["lr"]
            bad_mean = res["mean"]
            break
            
    if bad_lr is None:
        raise RuntimeError("Could not find a bad_lr")
        
    print(f"Selected good_lr={good_lr} ({good_mean:.3f}), bad_lr={bad_lr} ({bad_mean:.3f})")
    
    out_data = {
        "good_lr": good_lr,
        "good_mean": good_mean,
        "good_std": good_std,
        "bad_lr": bad_lr,
        "bad_mean": bad_mean,
        "epochs": 20,
        "batch_size": 32
    }
    
    with open("benchmarks/calibration.json", "w") as f:
        json.dump(out_data, f, indent=2)
        
    md_content = "# Benchmark Calibration\n\n## Candidates\n| LR | Mean | Std |\n|---|---|---|\n"
    for res in results:
        md_content += f"| {res['lr']} | {res['mean']:.4f} | {res['std']:.4f} |\n"
        
    md_content += f"\n**Selected good_lr**: {good_lr}\n"
    md_content += f"**Selected bad_lr**: {bad_lr}\n"
    md_content += "\nDeterminism check passed.\n"
    
    with open("benchmarks/MEASURED.md", "w") as f:
        f.write(md_content)

if __name__ == "__main__":
    main()
