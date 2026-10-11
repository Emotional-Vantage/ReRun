"""
Remote GPU execution on DigitalOcean Gradient GPU Droplets.

ReRun's local sandbox cannot run a paper that requires CUDA: preflight raises
`gpu_required` and the orchestrator reports UNABLE_TO_EXECUTE without ever
running the code. That is not a bug, it is a hardware ceiling, and it rules out
most modern ML papers.

This package lifts the ceiling by renting a GPU for the minutes a run takes.
It deliberately does NOT introduce a second execution model: the droplet runs
the same container image, under the same spec built by
`sandbox.manager.build_container_spec`, through the same docker-py API pointed
at the droplet's daemon instead of the local one. What changes is the host, not
the sandbox contract.
"""

from .cost import CostEstimate, estimate_run_cost
from .sandbox import GradientSandbox

__all__ = ["GradientSandbox", "CostEstimate", "estimate_run_cost"]
