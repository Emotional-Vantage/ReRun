# Rebuild Status

## Current position
- Current stage: 2 — Sandbox & Isolation
- Stage status: COMPLETE
- Next stage to execute: 3 — Benchmark Fixtures & Expected Outcomes (./rebuild-plan/04_STAGE_3.md)
- Do not start the next stage until explicitly asked.

## Completed stages
| Stage | Name | Completed | Verified by |
|---|---|---|---|
| 1 | Foundation & contracts | 2026-10-10 | `pytest tests/unit -q` → 24 passed |
| 2 | Sandbox & isolation | 2026-10-10 | `dev.py hardened-smoke` passed, `wheelhouse` 30 wheels (torch-2.5.1+cpu), `pytest tests -q` → 44 passed, 1 skipped |

## Git
- Target: branch main, working directory updated with Stage 2 implementations
- Reference: clean working tree (`Black-bot/` unmodified)

## Files created this stage
- sandbox/limits.py
- sandbox/manager.py
- sandbox/docker_sandbox.py
- sandbox/fake.py
- sandbox/cleanup.py
- sandbox/images/Dockerfile.base
- sandbox/images/requirements.base.txt
- sandbox/images/requirements.wheelhouse.txt
- scripts/make_wheelhouse.py
- backend/app/main.py
- tests/unit/test_docker_sandbox_adapter.py
- tests/unit/test_fake_sandbox_guard.py
- tests/unit/test_gpu_mode.py
- tests/security/__init__.py
- tests/security/escape_repo/attempt.py
- tests/security/test_hardening_and_bombs.py
- tests/security/test_selftest.py
- tests/integration/test_stage4_docker_abort.py

## Files modified this stage
- scripts/dev.py (implemented `images`, `wheelhouse`, `hardened-smoke`, `cleanup`)
- sandbox/__init__.py (exported sandbox symbols and classes)
- .gitignore (added `wheelhouse/`)
- rebuild-plan/PATHS.md (recorded resolved workspace paths)

## Commands executed and their ACTUAL results
| Command | Result |
|---|---|
| `python3 scripts/dev.py images` | `Successfully built d3cae49dd1ea` / `Successfully tagged rerun-base:py311` |
| `python3 scripts/dev.py hardened-smoke` | All 5 checks PASSED (Network blocked, Read-only root, Non-root uid 1000, PIDs limit enforced, Disk bomb contained) |
| `python3 scripts/dev.py wheelhouse` | Successfully downloaded torch, numpy, PyYAML, autograd, imageio, scipy, scikit-learn, pandas, matplotlib, etc. |
| `ls wheelhouse \| wc -l` | `30` (including `torch-2.5.1+cpu-cp311-cp311-linux_x86_64.whl` ~167 MB) |
| `python3 scripts/dev.py cleanup` | `Cleaning up orphan rerun containers... Cleanup complete.` |
| `pytest tests/unit -q` | `34 passed in 0.17s` |
| `pytest tests/security -q` | `10 passed in 10.22s` |
| `pytest -k fake_sandbox_guard -q` | `4 passed, 41 deselected in 0.26s` |
| `pytest tests -q` | `44 passed, 1 skipped in 10.24s` |
| `python3 scripts/dev.py test` | `44 passed, 1 skipped in 10.03s` |
| `make test` | `44 passed, 1 skipped in 10.27s` |
| `git status` in Black-bot | `nothing to commit, working tree clean` |

## Tests
- Passed:
  - Contract & persistence tests (24 passed)
  - test_docker_sandbox_interface
  - test_fake_sandbox_interface_matches
  - test_fake_sandbox_execution_return_type
  - test_startup_refuses_fake_sandbox_without_allow_flag
  - test_startup_allows_fake_sandbox_with_allow_flag
  - test_startup_allows_default_docker_sandbox
  - test_get_sandbox_guard
  - test_gpu_mode_disabled
  - test_gpu_mode_enabled_but_probe_fails
  - test_gpu_mode_enabled_and_probe_succeeds
  - test_container_spec_hardening_attributes
  - test_container_network_unreachable
  - test_container_write_outside_workspace_fails
  - test_container_runs_as_uid_1000
  - test_container_fork_bomb_capped
  - test_container_disk_bomb_contained
  - test_container_timeout_killed
  - test_sandbox_security
  - test_sandbox_timeout
  - test_sandbox_oom
- Skipped:
  - test_stage4_docker_abort (skipped gracefully: backend API and persistence routes are implemented in Stage 7)
- Failed: none
- Blocked: none

## Known issues / open questions
none

## Implementation decisions
- `TMPDIR` bind-mount: In install containers, bind-mount `data/runs/<project_id>/pip_tmp` to `/pip_tmp` and set `TMPDIR=/pip_tmp` so wheel unpacking (notably torch ~800MB) does not exhaust RAM-backed tmpfs.
- Secret scrubbing: `scrub_secrets` is applied to streaming container output chunks before saving to disk.
- Docker 409 conflict resilience: `_safe_remove` catches APIError with "already in progress" / "is being removed" and retries up to 3 times without failing the run.
- File ownership & permissions: `_make_tree_group_writable` walks filesystem via Python `os.chmod` preserving executable bits and ensuring host accessibility without shell interpolation.
- Fake sandbox guard: `FakeSandbox` selection is guarded by `ALLOW_FAKE_SANDBOX=1` via `get_sandbox()` and `startup_event()`, preventing unintentional simulated runs.
- Wheelhouse build: `make_wheelhouse.py` runs inside `rerun-base:py311` container with PyTorch CPU index `--extra-index-url https://download.pytorch.org/whl/cpu` to download exact Python 3.11 Linux wheels into `./wheelhouse/`.

## Deviations from the original
none

## Expected starting state for the next stage
- Base image `rerun-base:py311` built and present in Docker.
- Offline `wheelhouse/` populated with 30 wheels including CPU-only PyTorch.
- Full sandbox package implemented in `./ReRun/sandbox/` (`limits.py`, `manager.py`, `docker_sandbox.py`, `fake.py`, `cleanup.py`).
- Security hardening proven by `dev.py hardened-smoke` and unit/security test suites (`44 passed, 1 skipped`).
- Ready to proceed to Stage 3 (`rebuild-plan/04_STAGE_3.md`).
