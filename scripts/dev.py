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


def images() -> None:
    print("Building base Docker image...")
    run_cmd("docker build -t rerun-base:py311 -f sandbox/images/Dockerfile.base sandbox/images")


def hardened_smoke() -> None:
    print("Running hardened sandbox smoke test...")
    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--read-only",
        "--tmpfs", "/tmp:rw,size=256m",
        "--pids-limit", "256",
        "--user", "1000",
        "rerun-base:py311",
        "python", "-c",
        (
            "import os, sys, socket, subprocess\n"
            "checks = {}\n"
            "# 1. Outbound network check\n"
            "try:\n"
            "    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "    s.settimeout(1)\n"
            "    s.connect(('8.8.8.8', 53))\n"
            "    checks['network_blocked'] = False\n"
            "except Exception:\n"
            "    checks['network_blocked'] = True\n"
            "# 2. Filesystem write outside /workspace\n"
            "try:\n"
            "    with open('/escape.txt', 'w') as f: f.write('escape')\n"
            "    checks['readonly_root'] = False\n"
            "except Exception:\n"
            "    checks['readonly_root'] = True\n"
            "# 3. Non-root user\n"
            "checks['non_root'] = (os.getuid() == 1000)\n"
            "# 4. Fork bomb resistance\n"
            "try:\n"
            "    procs = []\n"
            "    for _ in range(300):\n"
            "        procs.append(subprocess.Popen(['sleep', '5']))\n"
            "    checks['pids_limit_enforced'] = False\n"
            "except Exception:\n"
            "    checks['pids_limit_enforced'] = True\n"
            "# 5. Disk bomb containment\n"
            "try:\n"
            "    with open('/tmp/bomb.bin', 'wb') as f:\n"
            "        for _ in range(400): f.write(b'\\x00' * (1024 * 1024))\n"
            "    checks['disk_bomb_contained'] = False\n"
            "except OSError:\n"
            "    checks['disk_bomb_contained'] = True\n"
            "print('RESULTS:' + str(checks))\n"
        ),
    ]

    print(f"Executing: {' '.join(cmd[:10])} ...")
    res = subprocess.run(cmd, capture_output=True, text=True)

    results = {}
    for line in res.stdout.splitlines():
        if line.startswith("RESULTS:"):
            try:
                results = eval(line[len("RESULTS:"):])
            except Exception:
                pass

    print("\n--- Hardened Sandbox Verification ---")
    print(f"| {'Check':<28} | {'Status':<8} |")
    print(f"|{'-'*30}|{'-'*10}|")
    all_passed = True
    check_names = [
        ("network_blocked", "Network blocked"),
        ("readonly_root", "Read-only root filesystem"),
        ("non_root", "Non-root user (uid 1000)"),
        ("pids_limit_enforced", "PIDs limit enforced"),
        ("disk_bomb_contained", "Disk bomb contained (tmpfs)"),
    ]
    for key, label in check_names:
        status = results.get(key, False)
        status_str = "PASS" if status else "FAIL"
        print(f"| {label:<28} | {status_str:<8} |")
        if not status:
            all_passed = False

    if all_passed and res.returncode == 0:
        print("\nAll hardened sandbox checks PASSED.\n")
    else:
        print("\nHardened smoke test FAILED.")
        print(f"Stdout:\n{res.stdout}")
        print(f"Stderr:\n{res.stderr}")
        sys.exit(1)


def wheelhouse() -> None:
    print("Building offline wheelhouse...")
    run_cmd(f"{sys.executable} scripts/make_wheelhouse.py")


def cleanup() -> None:
    print("Cleaning up orphan rerun containers...")
    from sandbox.cleanup import cleanup_orphans
    cleanup_orphans()
    print("Cleanup complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="ReRun Developer CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Stage 1 implemented commands
    subparsers.add_parser("setup", help="Install development dependencies")
    subparsers.add_parser("test", help="Run pytest suite")

    # Stage 2 implemented commands
    subparsers.add_parser("images", help="Build Docker images (Stage 2)")
    subparsers.add_parser("hardened-smoke", help="Run hardened sandbox smoke test (Stage 2)")
    subparsers.add_parser("wheelhouse", help="Build offline wheelhouse (Stage 2)")
    subparsers.add_parser("cleanup", help="Clean up orphan containers (Stage 2)")

    # Future stage commands (stubs that exit non-zero)
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
    elif args.command == "images":
        images()
    elif args.command == "hardened-smoke":
        hardened_smoke()
    elif args.command == "wheelhouse":
        wheelhouse()
    elif args.command == "cleanup":
        cleanup()
    elif args.command == "export-digits":
        run_cmd(f"{sys.executable} scripts/export_digits.py")
    elif args.command == "papers":
        run_cmd(f"{sys.executable} scripts/make_papers.py")
    elif args.command == "seed-faults":
        run_cmd(f"{sys.executable} scripts/seed_faults.py")
    elif args.command == "build-benchmarks":
        print("Building full Stage 3 benchmarks...")
        run_cmd(f"{sys.executable} scripts/export_digits.py")
        run_cmd(f"{sys.executable} scripts/seed_faults.py")
        run_cmd(f"{sys.executable} scripts/make_papers.py")
        print("Benchmarks built successfully!")
    elif args.command == "bench":
        systems_arg = f"--systems {args.systems}" if args.systems else ""
        run_cmd(f"{sys.executable} benchmarks/run_bench.py {systems_arg}")
    elif args.command == "run":
        if not args.case:
            print("Error: --case is required for run")
            sys.exit(1)
        from scripts.run_case import run_case_headless
        run_case_headless(args.case)
    elif args.command == "selftest":
        run_cmd(f"{sys.executable} -m pytest tests/security/test_selftest.py -v")
    else:
        stage_map = {
            "calibrate": 3,
            "bench-real": 3,
            "record": 5,
            "demo-check": 6,
            "api": 7,
            "ui": 8,
            "adversarial": 9,
        }
        target_stage = stage_map.get(args.command, "N")
        print(f"not implemented until Stage {target_stage}")
        sys.exit(1)


if __name__ == "__main__":
    main()
