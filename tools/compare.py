import math

def compare(claim, observed_mean):
    if observed_mean is None or math.isnan(observed_mean):
        return {
            "claim_id": claim.id,
            "reported": claim.reported,
            "observed": observed_mean,
            "abs_gap": None,
            "rel_gap": None,
            "tolerance": claim.tolerance.model_dump(),
            "within_tolerance": None
        }
        
    reported = claim.reported
    abs_gap = abs(reported - observed_mean)
    rel_gap = abs_gap / abs(reported) if reported != 0 else float('inf')
    
    tol_val = claim.tolerance.value + 1e-9
    
    if claim.tolerance.type == "abs":
        within = abs_gap <= tol_val
    else:
        within = rel_gap <= tol_val
        
    return {
        "claim_id": claim.id,
        "reported": reported,
        "observed": observed_mean,
        "abs_gap": abs_gap,
        "rel_gap": rel_gap,
        "tolerance": claim.tolerance.model_dump(),
        "within_tolerance": within
    }

def recommend_tolerance(reported: float, std: float | None = None, raw_paper_str: str | None = None) -> dict:
    """
    Deterministic tolerance advisor (§R4):
    - paper gives a ± s -> max(s, rounding)
    - 2 decimals -> ±0.005
    - 1 decimal -> ±0.05
    - else suggest ±1 point (±0.01 for <=1.0 or ±1.0)
    """
    import re
    s_val = None
    if std is not None:
        s_val = float(std)
    elif raw_paper_str and "±" in raw_paper_str:
        m = re.search(r"±\s*(\d+(?:\.\d+)?)", raw_paper_str)
        if m:
            try:
                s_val = float(m.group(1))
            except Exception:
                pass

    rep_str = f"{reported:.8f}".rstrip("0")
    decimals = 0
    if "." in rep_str:
        decimals = len(rep_str.split(".")[1])

    if decimals >= 2:
        rounding = 0.005 if decimals == 2 else 0.5 * (10 ** (-decimals))
    elif decimals == 1:
        rounding = 0.05
    else:
        rounding = 0.5

    if s_val is not None:
        rec = max(s_val, rounding)
        reason = f"Derived from paper uncertainty (±{s_val}) bounded by rounding ({rounding})"
    elif decimals == 2:
        rec = 0.005
        reason = "Derived from 2-decimal reported precision (±0.005)"
    elif decimals == 1:
        rec = 0.05
        reason = "Derived from 1-decimal reported precision (±0.05)"
    else:
        rec = 0.01 if reported <= 1.0 else 1.0
        reason = "Suggested 1-point default tolerance"

    return {
        "type": "abs",
        "value": round(rec, 6),
        "reason": reason
    }
