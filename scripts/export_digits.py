import os
import csv
import shutil
from pathlib import Path

def export_digits(target_csv_path="benchmarks/template/data/digits.csv"):
    try:
        from sklearn.datasets import load_digits
    except ImportError:
        print("scikit-learn not installed. Please install scikit-learn in dev environment.")
        return False
        
    digits = load_digits()
    X = digits.data  # shape (1797, 64)
    y = digits.target # shape (1797,)
    
    target_path = Path(target_csv_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(target_path, "w", newline="") as f:
        writer = csv.writer(f)
        header = [f"pixel_{i}" for i in range(X.shape[1])] + ["target"]
        writer.writerow(header)
        for i in range(len(X)):
            row = list(X[i]) + [int(y[i])]
            writer.writerow(row)
            
    print(f"Exported {len(X)} rows x {X.shape[1] + 1} columns to {target_csv_path}")
    
    # Also ensure all existing benchmark cases have data/digits.csv
    cases_dir = Path("benchmarks/cases")
    if cases_dir.exists():
        for case in cases_dir.iterdir():
            if case.is_dir():
                dest_dir = case / "data"
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / "digits.csv"
                shutil.copy2(target_path, dest)
                print(f"Copied to {dest}")
                
    return True

if __name__ == "__main__":
    export_digits()
