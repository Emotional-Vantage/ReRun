# Rebuild Status

## Current position
- Current stage: 1 — Foundation & Contracts
- Stage status: COMPLETE
- Next stage to execute: 2 — Sandbox & Isolation (./rebuild-plan/03_STAGE_2.md)
- Do not start the next stage until explicitly asked.

## Completed stages
| Stage | Name | Completed | Verified by |
|---|---|---|---|
| 1 | Foundation & contracts | 2026-10-10 | `pytest tests -q` → 24 passed |

## Git
- Commit: no git history initialised

## Files created this stage
- .gitignore
- .env.example
- requirements.txt
- requirements-dev.txt
- pytest.ini
- Makefile
- README.md
- REBUILD_STATUS.md
- agent/__init__.py
- agent/state.py
- agent/config.py
- tools/__init__.py
- tools/errors.py
- tools/paths.py
- backend/__init__.py
- backend/app/__init__.py
- sandbox/__init__.py
- benchmarks/__init__.py
- scripts/dev.py
- tests/__init__.py
- tests/conftest.py
- tests/unit/__init__.py
- tests/unit/test_contracts.py
- tests/unit/test_state_persistence.py

## Files modified this stage
- ../rebuild-plan/PATHS.md (recorded resolved workspace paths)

## Commands executed and their ACTUAL results
| Command | Result |
|---|---|
| `python3 -m pytest tests -q` | `24 passed in 0.10s` |
| `python3 scripts/dev.py bench` | Exited 1 with `not implemented until Stage 3` |
| `python3 scripts/dev.py test` | `24 passed in 0.08s` |
| `make test` | `24 passed in 0.08s` |
| `git status` in reference | `nothing to commit, working tree clean` |

## Tests
- Passed:
  - test_minimal_construction_of_every_model
  - test_project_state_json_roundtrip
  - test_literal_fields_reject_invalid_values
  - test_tools_paths_functions_and_redirection
  - test_conftest_scratch_runs_root_is_isolated_and_on_disk
  - test_metric_extraction_failed_is_a_valid_error_class
  - test_every_error_class_survives_a_json_round_trip [17 ErrorClass variants]
  - test_invalid_error_class_is_rejected
- Failed: none
- Blocked: none

## Known issues / open questions
none

## Implementation decisions
- `Hypothesis` model handles both `text` and `statement` attributes seamlessly via Pydantic model validator, preserving backward and cross-module compatibility.
- `ProjectState` exposes `.reviews` alias property pointing to `.critic_reviews`.
- `conftest` sets session runs root isolation under `data/.pytest-runs` on disk rather than `/tmp` to prevent disk/RAM quota exhaustion during wheel installation in later stages.
- `backend.app.db` isolation fixture no-ops gracefully until Stage 7 implements the database module.

## Deviations from the original
none

## Expected starting state for the next stage
- A clean, verified Stage 1 skeleton in `./ReRun/` with all contracts and run paths defined.
- `rebuild-plan/PATHS.md` records `./Black-bot/` as reference and `./ReRun/` as target.
- All unit tests pass (`24 passed`).
