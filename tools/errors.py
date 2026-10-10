import re
from typing import Optional, Any, Dict

# Appendix A signature library updated for R6 (Stage 9)
SIGNATURES = [
    # 1. Python version mismatch (must precede generic dependency_missing for distutils/imp)
    (
        "python_version_mismatch",
        "py-version-mismatch",
        r"ModuleNotFoundError: No module named '(?:distutils|imp)'|"
        r"TypeError: unsupported operand type\(s\) for \|: 'type' and 'type'|"
        r"requires Python '[^']+' but the running Python is|"
        r"SyntaxError: invalid syntax.*(?:match\s+|case\s+)|"
        r"ImportError: cannot import name '(?:ParamSpec|TypeAlias)' from 'typing'"
    ),
    # 2. API Deprecations (e.g. np.int, np.float, scipy, pandas append, torch weights_only)
    (
        "api_deprecation",
        "api-deprecation",
        r"AttributeError: module 'numpy' has no attribute '(?:int|float|bool|object|complex|typeDict)'|"
        r"AttributeError: 'DataFrame' object has no attribute 'append'|"
        r"ImportError: cannot import name 'imread' from 'scipy\.misc'|"
        r"ImportError: cannot import name '[^']+' from 'sklearn\.externals'|"
        r"WeightsOnlyUnpickler|weights_only=True|"
        r"AttributeError: module 'scipy' has no attribute"
    ),
    # 3. Missing dataset files (must precede generic path_error)
    (
        "dataset_missing",
        "dataset-missing",
        r"DatasetNotFoundError|"
        r"RuntimeError: Dataset [^\n]+ not found|"
        r"FileNotFoundError:.*(?:/data/|/datasets/|\.csv|\.h5|\.parquet|\.npy|mnist|cifar)|"
        r"No such file or directory:.*(?:/data/|/datasets/|\.csv|\.h5|\.parquet|\.npy)|"
        r"Please download the dataset"
    ),
    # 4. Device unavailable / unguarded CUDA at runtime
    (
        "device_unavailable",
        "device-unavailable",
        r"No CUDA GPUs are available|"
        r"Found no NVIDIA driver on your system|"
        r"CUDA device not found|"
        r"RuntimeError: CUDA error: no kernel image|"
        r"RuntimeError: device 'cuda' is not available|"
        r"AssertionError: CUDA unavailable"
    ),
    # 5. GPU required (general CUDA dependency)
    (
        "gpu_required",
        "gpu-cuda",
        r"CUDA error|CUDA is not available|torch\.cuda|Torch not compiled with CUDA"
    ),
    # 6. Resource OOM
    (
        "resource_oom",
        "oom",
        r"MemoryError|CUDA out of memory|Out of memory|Killed: 9|exit code 137|OOMKilled"
    ),
    # 7. Resource Timeout
    (
        "resource_timeout",
        "timeout",
        r"TimeoutExpired|Command '.*' timed out|timed out after \d+ seconds"
    ),
    # 8. Missing dependencies
    (
        "dependency_missing",
        "modnotfound",
        r"ModuleNotFoundError: No module named '([\w\.]+)'|ImportError: No module named"
    ),
    # 9. Dependency conflict
    (
        "dependency_conflict",
        "pip-conflict",
        r"ResolutionImpossible|No matching distribution found|Could not find a version that satisfies|conflicting dependencies"
    ),
    # 10. Network required
    (
        "network_required",
        "net",
        r"Temporary failure in name resolution|Network is unreachable|Connection refused|URLError|ConnectionError|MaxRetryError|Name or service not known"
    ),
    # 11. Sandbox permissions
    (
        "sandbox_permission",
        "perm",
        r"PermissionError|Read-only file system|\[Errno 13\]|\[Errno 30\]"
    ),
    # 12. Generic Path error
    (
        "path_error",
        "fnf",
        r"FileNotFoundError|No such file or directory"
    ),
    # 13. Config errors
    (
        "config_error",
        "cfg",
        r"unrecognized arguments|KeyError: '|yaml\.\w+\.\w*Error"
    ),
    # 14. Numerical invalid
    (
        "numerical_invalid",
        "nan",
        r"(?i)\bnan\b|\binf\b"
    )
]

def classify(
    log_text: str = "",
    attempt: Optional[Any] = None,
    exit_code: Optional[int] = None,
    oom: bool = False,
    timed_out: bool = False
) -> Dict[str, Any]:
    """
    Classifies execution failures from logs and attempt metadata.
    Checks attempt flags (oom, timed_out, exit 137) as well as text signatures.
    """
    # 1. Attempt flag classification
    is_oom = oom or (attempt and getattr(attempt, "oom", False))
    eff_exit = exit_code if exit_code is not None else (getattr(attempt, "exit_code", None) if attempt else None)
    if is_oom or eff_exit == 137:
        return {
            "error_class": "resource_oom",
            "signature_id": "oom",
            "line_start": None,
            "line_end": None
        }

    is_timeout = timed_out or (attempt and getattr(attempt, "timed_out", False))
    if is_timeout:
        return {
            "error_class": "resource_timeout",
            "signature_id": "timeout",
            "line_start": None,
            "line_end": None
        }

    # 2. Text log classification
    lines = (log_text or "").splitlines()[-300:]
    text_to_scan = "\n".join(lines)

    for err_class, sig_id, pattern in SIGNATURES:
        match = re.search(pattern, text_to_scan)
        if match:
            # find line number roughly
            for i, line in enumerate(lines):
                if re.search(pattern, line):
                    total_lines = len((log_text or "").splitlines())
                    calc_line = max(1, total_lines - len(lines) + i + 1)
                    return {
                        "error_class": err_class,
                        "signature_id": sig_id,
                        "line_start": calc_line,
                        "line_end": calc_line
                    }
            return {
                "error_class": err_class,
                "signature_id": sig_id,
                "line_start": None,
                "line_end": None
            }

    return {
        "error_class": "unknown",
        "signature_id": "unknown",
        "line_start": None,
        "line_end": None
    }

# Alias for compatibility
classify_error = classify
