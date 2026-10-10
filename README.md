# Rerun — Autonomous Research Paper Reproducibility Agent

Rerun is an autonomous AI agent engineered to verify whether code from published research papers faithfully reproduces stated headline results. Rerun executes experiments inside isolated Docker sandboxes, diagnoses crashes and metric mismatches, derives surgical configuration and dependency patches, and produces verifier-certified reproduction reports and self-contained reproduction kits.

---

## ⚠️ Limits & Honest Boundary Disclosures

Before exploring capabilities, understand Rerun's strict operational boundaries:
1. **Network-Isolated Execution (Invariant I3):** All reproduction code executes inside hardened Docker containers (`rerun-base:py311`) with `network_mode="none"`. The agent cannot fetch external datasets, weights, or packages from the internet during experiment runs.
2. **Mandatory Human-in-the-Loop (Invariant I8):** The AI **cannot** apply patches to disk or alter code autonomously without explicit human approval. Patch diffs must pass deterministic policy checks (P1–P10) and an independent 9-point Critic checklist before human sign-off.
3. **Hard Authority Hierarchy:**
   $$\text{Human} > \text{Policy Engine (Code)} > \text{Critic (LLM)} > \text{Solver (LLM)}$$
   The AI cannot determine its own reproduction verdict, write evidence arbitrarily, or bypass resource limits.
4. **Finite Resource Ceilings:** 40 orchestrator steps, 3 code patches, $\le 5$ files modified per patch, $\le 200$ changed lines, 600s container timeout, 2 CPUs, 2GB RAM, and 256 PIDs.
5. **Hardware Constraints:** GPU acceleration is strictly opt-in (`GPU_ENABLED=false` by default). Papers that strictly require CUDA GPUs are detected at preflight triage and flagged as infeasible on CPU-only infrastructure (`UNABLE_TO_EXECUTE`).
6. **Selection Bias & Scope Notice:** Track A synthetic benchmark cases (B1–B5) were designed to evaluate specific failure modes. Real external repositories with unstated dependencies or hardware prerequisites are handled via preflight triage.

---

## The Three Human Gates

Rerun parks at three explicit human verification gates:
- **Gate 1: Claims Confirmation (`CLAIMS_CONFIRM`)**: Operator reviews extracted paper claims, target metrics, baseline values, and experiment execution commands.
- **Gate 2: Provisioning Approval (`PROVISIONING_APPROVE`)**: Operator reviews reachable import analysis, required missing wheels, and authorizes offline wheelhouse preparation before isolated run.
- **Gate 3: Patch Approval (`APPROVAL`)**: When a failure is diagnosed, proposed code/config changes must pass the deterministic Policy engine and the independent Critic before operator review and approval.

---

## Quickstart

### 1. Prerequisites
- Linux (x86_64) or macOS with Docker installed and active
- Python 3.12+
- Node.js 20+ and npm
- ~4 GB free disk space

### 2. Setup & Execution Commands

```bash
# Set up virtual environment and dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Configure environment template
cp .env.example .env

# Build base Docker sandbox image (rerun-base:py311)
make images

# Generate offline wheelhouse (CPU-only PyTorch, numpy, scipy, etc.)
make wheelhouse

# Verify container security boundaries (non-root, read-only FS, network blocked)
python3 scripts/dev.py hardened-smoke

# Run the test suite
make test

# Run the benchmark suite (all five Track A cases)
make bench

# Start backend API (port 8000)
make api

# Start frontend Vite console (port 5173, proxies /api -> 8000)
make ui
```

### 3. Developer Tooling (`scripts/dev.py`)

`scripts/dev.py` provides operational commands:
- `python3 scripts/dev.py bench`: Runs Track A benchmark suite across B-0, B-2, and Rerun.
- `python3 scripts/dev.py adversarial`: Runs the 9-fixture red-team adversarial suite (all 9 refused).
- `python3 scripts/dev.py prune`: Reclaims disk space by pruning regenerable caches while preserving evidence ledgers.
- `python3 scripts/dev.py hardened-smoke`: Verifies container security invariants directly against Docker daemon.
- `python3 scripts/dev.py build-benchmarks`: Generates synthetic datasets, fault seeds, and benchmark papers.

---

## Measured Benchmark Evaluation (Track A)

Measured under real Docker execution (`DockerSandbox`, image `rerun-base:py311`, offline network):

| Case | Title | Gold Expected | B-0 (No Agent) | B-2 (One-Shot) | Rerun (Autonomous) | Rerun Status |
|---|---|---|---|---|---|---|
| `b1_control` | Clean Implementation | `REPRODUCED` | 1/1 | 1/1 | **1/1** | `REPRODUCED` (0 patches, exit 0) |
| `b2_dependency` | Missing PyYAML | `REPRODUCED` | 0/1 | 1/1 | **1/1** | `REPRODUCED` (1 patch: PyYAML==6.0.1) |
| `b3_silent_config` | Bad Learning Rate | `REPRODUCED` | 0/1 | 1/1 | **1/1** | `REPRODUCED` (1 patch: lr 0.01 -> 0.5) |
| `b4_combined` | Dependency + Bad LR | `REPRODUCED` | 0/1 | 0/1 | **1/1** | `REPRODUCED` (2 patches: PyYAML + lr) |
| `b5_unable` | Mandatory CUDA GPU | `UNABLE_TO_EXECUTE` | 1/1 | 1/1 | **1/1** | `UNABLE_TO_EXECUTE` (0 patches) |

### Summary Counts Across Two Consecutive Sweeps
- **B-0 Baseline**: 2/5 matched gold (40.0%)
- **B-2 Baseline**: 4/5 matched gold (80.0%)
- **Rerun**: **5/5 matched gold (100.0%)** on both sweeps

---

## Security Model & Sandboxing

1. **Host-Level Protection**:
   - `network_mode = "none"`: Containers have zero network access.
   - `read_only = True`: Root filesystem is mounted read-only. Only `/workspace` (bind mount) and `/tmp` (tmpfs) are writable.
   - `user = "1000:1000"`: Containers run strictly as non-root user.
   - `cap_drop = ["ALL"]`, `security_opt = ["no-new-privileges"]`.
2. **Resource Boundaries**:
   - `pids_limit = 256`: Fork bombs are contained.
   - `mem_limit = "2g"`: OOM killer catches runaway allocations.
   - Disk quota: tmpfs is capped at 1GB; disk bombs cannot exhaust host storage.
   - Execution timeout: Containers are terminated after 600s.
3. **Application & Policy Security**:
   - Prompt injection defense: Evaluation files (`evaluate.py`, `metric*`, `test_*`, `split*`, `data*`) are in `DENY_LIST`.
   - Metric-chasing rationales are rejected.
   - Secrets scrubbing removes keys and tokens from logs, reports, and SSE events.

---

## Known Limitations & Unverified Items

- **Docker Dependency**: Real reproductions require an active Docker daemon. When running in environments without Docker, `ALLOW_FAKE_SANDBOX=1` can be used for test assertions only.
- **Track B Scope**: Track B evaluation over external real-world paper suites (`benchmarks/real/`) was an optional exploration in the reference and is not part of this core build.
- **Live LLM Reproductions**: Headless benchmark measurements use deterministic cassettes/FakeLLM to measure the orchestrator, sandbox, and policy layers reproducibly without LLM nondeterminism. Live provider runs require a configured `SOLVER_API_KEY`.
