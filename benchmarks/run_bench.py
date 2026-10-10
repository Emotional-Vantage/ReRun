import json
import time
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from benchmarks.baselines.b0_fixed import run_b0
from benchmarks.baselines.b2_oneshot import run_b2

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--systems", type=str, default="B-0,B-2", help="Comma separated systems: B-0,B-2,Rerun")
    parser.add_argument("--repeats", type=int, default=1, help="Number of repeats per case")
    args = parser.parse_args()

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    repeats = args.repeats

    with open("benchmarks/registry.json", "r", encoding="utf-8") as f:
        registry = json.load(f)
        
    out_dir = Path(f"benchmarks/results/{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    for case in registry["cases"]:
        case_id = case["id"]
        with open(case["gold_path"], "r", encoding="utf-8") as f:
            gold = json.load(f)
            
        for sys_name in systems:
            if sys_name == "B-0":
                for i in range(repeats):
                    print(f"Running {sys_name} on {case_id} (run {i+1}/{repeats})...")
                    start_t = time.time()
                    try:
                        status = run_b0(case_id, case, run_n=i+1)
                    except Exception as e:
                        print(f"Error in B-0: {e}")
                        status = "FAILED_TO_RUN"
                    wall_time = time.time() - start_t
                    matches_gold = (status == gold["expected_status"])
                    res = {
                        "case": case_id,
                        "system": sys_name,
                        "run": i+1,
                        "final_status": status,
                        "matches_gold": matches_gold,
                        "wall_time_s": round(wall_time, 2)
                    }
                    results.append(res)
                    print(f"Result: {status} (matches gold: {matches_gold})")

            elif sys_name == "B-2":
                for i in range(repeats):
                    print(f"Running {sys_name} on {case_id} (run {i+1}/{repeats})...")
                    start_t = time.time()
                    try:
                        status = run_b2(case_id, case, run_n=i+1)
                    except Exception as e:
                        print(f"Error in B-2: {e}")
                        status = "FAILED_TO_RUN"
                    wall_time = time.time() - start_t
                    matches_gold = (status == gold["expected_status"])
                    res = {
                        "case": case_id,
                        "system": sys_name,
                        "run": i+1,
                        "final_status": status,
                        "matches_gold": matches_gold,
                        "wall_time_s": round(wall_time, 2)
                    }
                    results.append(res)
                    print(f"Result: {status} (matches gold: {matches_gold})")

    summary_file = out_dir / "summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nBenchmark run complete. Results saved to {summary_file}")

if __name__ == "__main__":
    main()
