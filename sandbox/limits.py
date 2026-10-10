import os
from dataclasses import dataclass


@dataclass
class SandboxLimits:
    cpus: float
    mem: str
    pids: int
    run_timeout_s: int
    install_timeout_s: int
    log_cap_bytes: int
    gpu_enabled: bool
    gpu_count: int
    gpu_image: str


def get_limits() -> SandboxLimits:
    """Load sandbox limits from environment variables with defaults."""
    return SandboxLimits(
        cpus=float(os.getenv("SANDBOX_CPUS", "2")),
        mem=os.getenv("SANDBOX_MEM", "2g"),
        pids=int(os.getenv("SANDBOX_PIDS", "256")),
        run_timeout_s=int(os.getenv("RUN_TIMEOUT_S", "600")),
        install_timeout_s=int(os.getenv("INSTALL_TIMEOUT_S", "300")),
        log_cap_bytes=int(os.getenv("LOG_CAP_BYTES", "2000000")),
        gpu_enabled=os.getenv("GPU_ENABLED", "false").lower() == "true",
        gpu_count=int(os.getenv("GPU_COUNT", "1")),
        gpu_image=os.getenv("GPU_IMAGE", "rerun-gpu:py311"),
    )


