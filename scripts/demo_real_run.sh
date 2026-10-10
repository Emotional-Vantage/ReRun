#!/usr/bin/env bash
# =============================================================================
# RERUN — Live Real Docker Demonstration Script
# Demonstrates an autonomous verification run in a real network-isolated container.
# =============================================================================

set -e

echo "======================================================================"
echo "  RERUN — AUTONOMOUS SCIENTIFIC REPRODUCIBILITY DEMO"
echo "  Executing in real isolated Docker container (rerun-base:py311)"
echo "======================================================================"

# 1. Check Docker availability
if ! docker info >/dev/null 2>&1; then
    echo "❌ Error: Docker daemon is not running. Please start Docker and retry."
    exit 1
fi

echo "✅ Docker daemon active."

# 2. Check base image
if ! docker images | grep -q "rerun-base:py311"; then
    echo "Building rerun-base:py311 base image..."
    python3 scripts/dev.py images
fi
echo "✅ Base sandbox image rerun-base:py311 ready."

# 3. Execute real benchmark case B2 (dependency repair with visible logs)
echo ""
echo "----------------------------------------------------------------------"
echo "  Running Benchmark Case: b2_dependency (Offline Dependency Recovery)"
echo "----------------------------------------------------------------------"
python3 scripts/dev.py run --case b2_dependency

# 4. Run Track B Real-Repo Evaluation Demo (if bench-real exists)
if [ -f "scripts/run_real_bench.py" ]; then
    echo ""
    echo "----------------------------------------------------------------------"
    echo "  Running Track B Real-Repo Evaluation Sweep (6 Real ML Papers)"
    echo "----------------------------------------------------------------------"
    python3 scripts/dev.py bench-real || true
fi

echo ""
echo "======================================================================"
echo "  DEMONSTRATION COMPLETE"
echo "======================================================================"
