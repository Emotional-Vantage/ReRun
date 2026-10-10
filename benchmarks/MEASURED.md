# Track A Benchmark Evaluation Results

> **How to read this:** the Rerun rows were produced with **scripted LLM replies** (FakeLLM), not a live model. They measure the orchestrator, the policy engine and the sandbox, and say nothing about model capability. Re-run with `--live-llm` for a model measurement.

**Timestamp:** 2026-10-10 20:22:10 UTC
**LLM:** scripted FakeLLM (orchestrator only, not a model measurement)
**Sandbox:** `SANDBOX_TYPE=docker` (`DockerSandbox`, image: `rerun-base:py311`, offline network)
**Repeats:** 1 per condition

## Summary Table (Counts Only)

| Case | Gold Expected | B-0 | B-2 | Rerun |
|---|---|---|---|---|
| `b1_control` | `REPRODUCED` | 1/1 (REPRODUCED) | 1/1 (REPRODUCED) | 1/1 (REPRODUCED) |
| `b2_dependency` | `REPRODUCED` | 0/1 (FAILED_TO_RUN) | 1/1 (REPRODUCED) | 1/1 (REPRODUCED) |
| `b3_silent_config` | `REPRODUCED` | 0/1 (NUMBER_MISMATCH) | 1/1 (REPRODUCED) | 1/1 (REPRODUCED) |
| `b4_combined` | `REPRODUCED` | 0/1 (FAILED_TO_RUN) | 0/1 (NUMBER_MISMATCH) | 1/1 (REPRODUCED) |
| `b5_unable` | `UNABLE_TO_EXECUTE` | 1/1 (UNABLE_TO_EXECUTE) | 1/1 (UNABLE_TO_EXECUTE) | 1/1 (UNABLE_TO_EXECUTE) |

## Total Success Counts

- **B-0**: 2/5 runs matched gold (40.0%)
- **B-2**: 4/5 runs matched gold (80.0%)
- **Rerun**: 5/5 runs matched gold (100.0%)

## Detailed Per-Run Log

| Case | System | Run | Final Status | Matches Gold | Patches | Retries | Time (s) |
|---|---|---|---|---|---|---|---|
| `b1_control` | B-0 | 1 | `REPRODUCED` | True | 0 | 0 | 4.09 |
| `b1_control` | B-2 | 1 | `REPRODUCED` | True | 0 | 0 | 3.86 |
| `b1_control` | Rerun | 1 | `REPRODUCED` | True | 0 | 0 | 11.63 |
| `b2_dependency` | B-0 | 1 | `FAILED_TO_RUN` | False | 0 | 0 | 3.63 |
| `b2_dependency` | B-2 | 1 | `REPRODUCED` | True | 1 | 1 | 7.36 |
| `b2_dependency` | Rerun | 1 | `REPRODUCED` | True | 1 | 1 | 15.08 |
| `b3_silent_config` | B-0 | 1 | `NUMBER_MISMATCH` | False | 0 | 0 | 4.37 |
| `b3_silent_config` | B-2 | 1 | `REPRODUCED` | True | 1 | 1 | 9.12 |
| `b3_silent_config` | Rerun | 1 | `REPRODUCED` | True | 1 | 1 | 15.36 |
| `b4_combined` | B-0 | 1 | `FAILED_TO_RUN` | False | 0 | 0 | 3.74 |
| `b4_combined` | B-2 | 1 | `NUMBER_MISMATCH` | False | 1 | 1 | 7.45 |
| `b4_combined` | Rerun | 1 | `REPRODUCED` | True | 2 | 2 | 17.51 |
| `b5_unable` | B-0 | 1 | `UNABLE_TO_EXECUTE` | True | 0 | 0 | 0.02 |
| `b5_unable` | B-2 | 1 | `UNABLE_TO_EXECUTE` | True | 0 | 0 | 0.02 |
| `b5_unable` | Rerun | 1 | `UNABLE_TO_EXECUTE` | True | 0 | 0 | 7.61 |
