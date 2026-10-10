# Track A Benchmark Evaluation Results

> **How to read this:** the Rerun rows were produced with **scripted LLM replies** (FakeLLM), not a live model. They measure the orchestrator, the policy engine and the sandbox, and say nothing about model capability. Re-run with `--live-llm` for a model measurement.

**Timestamp:** 2026-10-10 17:13:42 UTC
**LLM:** scripted FakeLLM (orchestrator only, not a model measurement)
**Sandbox:** `SANDBOX_TYPE=fake` (**simulated**, not a real container)
**Repeats:** 1 per condition

## Summary Table (Counts Only)

| Case | Gold Expected | Rerun |
|---|---|---|
| `b2_dependency` | `REPRODUCED` | 1/1 (REPRODUCED) |

## Total Success Counts

- **Rerun**: 1/1 runs matched gold (100.0%)

## Detailed Per-Run Log

| Case | System | Run | Final Status | Matches Gold | Patches | Retries | Time (s) |
|---|---|---|---|---|---|---|---|
| `b2_dependency` | Rerun | 1 | `REPRODUCED` | True | 0 | 0 | 7.63 |
