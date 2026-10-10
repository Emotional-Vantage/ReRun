#!/usr/bin/env python3
"""
Reclaim disk space from data/runs/.

Artifact retention policies:
- Retained permanently:
    * Execution logs (logs/)
    * Outputs and metric summaries (outputs/)
    * Evidence ledger and cryptographic snapshots (evidence/, evidence.json)
    * Reproduction report (report.json, report.md)
- Reclaimed for completed ('DONE') projects:
    * Project-level wheel cache (wheelhouse/)
    * Python site-packages installed into workspace (workspace/.site)
    * Temporary pip build artifacts (pip_tmp)
- Pruned:
    * Orphaned run directories with no matching row in projects table

Default operation is report-only. Pass --apply to execute deletions.
"""

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGENERABLE_SUBPATHS = ("wheelhouse", "workspace/.site", "pip_tmp")


def calculate_dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def get_project_phases(db_path: Path) -> dict:
    """Returns mapping of project_id -> phase directly from database JSON column."""
    phases = {}
    if not db_path.exists():
        return phases
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("SELECT id, state_json FROM projects")
        for pid, state_json in cursor:
            phase = None
            if state_json:
                try:
                    phase = json.loads(state_json).get("phase")
                except Exception:
                    phase = None
            phases[pid] = phase
    finally:
        conn.close()
    return phases


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Perform actual deletions (default: report only)"
    )
    parser.add_argument(
        "--runs-root", default=str(REPO_ROOT / "data" / "runs"),
        help="Root path of runs directory"
    )
    parser.add_argument(
        "--db", default=str(REPO_ROOT / "data" / "rerun.db"),
        help="Path to SQLite database"
    )
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    if not runs_root.is_dir():
        print(f"no runs directory at {runs_root}")
        return 0

    phases = get_project_phases(Path(args.db))
    orphans = []
    regenerable = []
    kept_active = 0

    for entry in sorted(runs_root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name not in phases:
            orphans.append(entry)
            continue
        if phases[entry.name] != "DONE":
            kept_active += 1
            continue
        for subpath in REGENERABLE_SUBPATHS:
            target = entry.joinpath(*subpath.split("/"))
            if target.exists():
                regenerable.append(target)

    orphan_bytes = sum(calculate_dir_size(p) for p in orphans)
    regen_bytes = sum(calculate_dir_size(p) for p in regenerable)

    print(f"runs root            : {runs_root}")
    print(f"unfinished, untouched: {kept_active} projects")
    print(f"orphaned run dirs    : {len(orphans)} ({orphan_bytes / 1e9:.1f} GB)")
    print(f"regenerable artifacts: {len(regenerable)} ({regen_bytes / 1e9:.1f} GB)")
    print(f"reclaimable total    : {(orphan_bytes + regen_bytes) / 1e9:.1f} GB")

    if not args.apply:
        print("\nreport only; re-run with --apply to delete")
        return 0

    deleted_count = 0
    for path in orphans + regenerable:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            deleted_count += 1
        elif path.is_file():
            path.unlink(missing_ok=True)
            deleted_count += 1

    print(f"\ndeleted {deleted_count} paths")
    return 0


if __name__ == "__main__":
    sys.exit(main())
