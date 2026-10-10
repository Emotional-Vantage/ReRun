from pathlib import Path
from typing import Dict, Any, List

def preflight_check(
    workspace: str,
    repo_profile: Dict[str, Any],
    gpu_enabled: bool = False,
    gpu_usable: bool = False,
    gpu_detail: str = ""
) -> Dict[str, Any]:
    """
    Decides whether the repository can be executed in this sandbox.

    `gpu_enabled` / `gpu_usable` must reflect the real host. They used to be passed as
    hardcoded False by the orchestrator, so a GPU repository was blocked even on a machine
    with a working GPU and GPU_ENABLED=true. `gpu_detail` carries the probe's reason so the
    blocker can say *why* the GPU is unavailable instead of a generic resource error.
    """
    ws = Path(workspace)
    blockers = []
    warnings = []
    
    triage = repo_profile.get("triage", {})
    if triage:
        for b in triage.get("blockers", []):
            if b == "gpu_required":
                if gpu_enabled and gpu_usable:
                    warnings.append("repo uses GPU and host GPU is usable")
                else:
                    if "gpu_required" not in blockers:
                        blockers.append("gpu_required")
            elif b not in blockers:
                blockers.append(b)
        warnings.extend(triage.get("warnings", []))
    else:
        gpu_hints = repo_profile.get("hints", {}).get("gpu", [])
        if gpu_hints:
            if gpu_enabled and gpu_usable:
                warnings.append("repo uses GPU and host GPU is usable")
            else:
                blockers.append("gpu_required")
                
        data_refs = repo_profile.get("hints", {}).get("data_refs", [])
        for dref in data_refs:
            if not (ws / dref).exists() and not (ws / "data" / Path(dref).name).exists():
                blockers.append("data_unavailable")
                break

    net_hints = repo_profile.get("hints", {}).get("network", [])
    if net_hints:
        warnings.append("potential network requests detected in repository code")

    result = {
        "blockers": sorted(list(set(blockers))),
        "warnings": sorted(list(set(warnings))),
        "triage_verdict": triage.get("verdict", "FEASIBLE"),
        "triage_reason": triage.get("reason", "")
    }
    if "gpu_required" in result["blockers"]:
        result["gpu_enabled"] = gpu_enabled
        result["gpu_usable"] = gpu_usable
        result["gpu_detail"] = gpu_detail or (
            "GPU mode is disabled (set GPU_ENABLED=true to opt in)" if not gpu_enabled
            else "GPU requested but not usable by the sandbox"
        )
    return result
