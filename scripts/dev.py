#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


def run_cmd(cmd: str) -> None:
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)


def setup() -> None:
    print("Setting up environment...")
    run_cmd(f"{sys.executable} -m pip install -r requirements-dev.txt")


def test() -> None:
    print("Running test suite...")
    run_cmd(f"{sys.executable} -m pytest tests -q")


def main() -> None:
    parser = argparse.ArgumentParser(description="ReRun Developer CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Stage 1 implemented commands
    subparsers.add_parser("setup", help="Install development dependencies")
    subparsers.add_parser("test", help="Run pytest suite")

    # Future stage commands (stubs that exit non-zero)
    subparsers.add_parser("images", help="Build Docker images (Stage 2)")
    subparsers.add_parser("hardened-smoke", help="Run hardened sandbox smoke test (Stage 2)")
    subparsers.add_parser("wheelhouse", help="Build offline wheelhouse (Stage 2)")

    bench_parser = subparsers.add_parser("bench", help="Run benchmark suite (Stage 3)")
    bench_parser.add_argument("--systems", required=False, default=None, help="Systems to evaluate")
    bench_parser.add_argument("--case", required=False, default=None, help="Benchmark case")

    subparsers.add_parser("build-benchmarks", help="Build benchmark assets (Stage 3)")
    subparsers.add_parser("export-digits", help="Export dataset (Stage 3)")
    subparsers.add_parser("calibrate", help="Calibrate benchmark thresholds (Stage 3)")
    subparsers.add_parser("papers", help="Generate paper PDFs (Stage 3)")
    subparsers.add_parser("seed-faults", help="Seed benchmark faults (Stage 3)")
    subparsers.add_parser("selftest", help="Run security selftests (Stage 3)")
    subparsers.add_parser("bench-real", help="Run real-world benchmarks (Stage 3)")

    subparsers.add_parser("record", help="Record LLM cassettes (Stage 5)")

    run_parser = subparsers.add_parser("run", help="Run headless reproduction (Stage 6)")
    run_parser.add_argument("--case", required=False, default=None, help="Case to run")

    subparsers.add_parser("demo-check", help="Verify end-to-end demo readiness (Stage 6)")
    subparsers.add_parser("cleanup", help="Clean up orphan containers (Stage 7)")
    subparsers.add_parser("api", help="Start FastAPI backend (Stage 7)")
    subparsers.add_parser("ui", help="Start Vite frontend (Stage 8)")
    subparsers.add_parser("adversarial", help="Run adversarial red-team suite (Stage 9)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "setup":
        setup()
    elif args.command == "test":
        test()
    else:
        stage_map = {
            "images": 2,
            "hardened-smoke": 2,
            "wheelhouse": 2,
            "bench": 3,
            "build-benchmarks": 3,
            "export-digits": 3,
            "calibrate": 3,
            "papers": 3,
            "seed-faults": 3,
            "selftest": 3,
            "bench-real": 3,
            "record": 5,
            "run": 6,
            "demo-check": 6,
            "cleanup": 7,
            "api": 7,
            "ui": 8,
            "adversarial": 9,
        }
        target_stage = stage_map.get(args.command, "N")
        print(f"not implemented until Stage {target_stage}")
        sys.exit(1)


if __name__ == "__main__":
    main()
