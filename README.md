# Rerun

Rerun is an AI agent that reproduces the results claimed in research papers inside isolated Docker sandboxes.

## Architecture

- **20-Phase Orchestration State Machine**: `INGEST` to `DONE` with parked human gates.
- **Authority Chain**: `Human > Policy (deterministic Python) > Critic (LLM) > Solver (LLM)`.
- **Sandbox Isolation**: Containers run with dropped capabilities, read-only root filesystems, non-root user, offline wheelhouse installations, and strict resource limits.
- **Evidence Ledger**: Cryptographic SHA-256 artifact verification for every claim, patch, and attempt.

## Quick Start

```bash
# Setup dependencies
make setup

# Run test suite
make test
```
