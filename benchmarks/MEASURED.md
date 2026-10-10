# Track A Benchmark Evaluation Results

> **How to read this:** the Rerun rows were produced with **scripted LLM replies** (FakeLLM), not a live model. They measure the orchestrator, the policy engine and the sandbox, and say nothing about model capability. Re-run with `--live-llm` for a model measurement.

**Timestamp:** 2026-10-10 16:44:19 UTC
**LLM:** scripted FakeLLM (orchestrator only, not a model measurement)
**Sandbox:** `SANDBOX_TYPE=docker` (`DockerSandbox`, image: `rerun-base:py311`, offline network)
**Repeats:** 1 per condition

## Summary Table (Counts Only)

| Case | Gold Expected | Rerun |
|---|---|---|
| `b5_unable` | `UNABLE_TO_EXECUTE` | 1/1 (UNABLE_TO_EXECUTE) |

## Total Success Counts

- **Rerun**: 1/1 runs matched gold (100.0%)

## Detailed Per-Run Log

| Case | System | Run | Final Status | Matches Gold | Patches | Retries | Time (s) |
|---|---|---|---|---|---|---|---|
| `b5_unable` | Rerun | 1 | `UNABLE_TO_EXECUTE` | True | 0 | 0 | 7.55 |
