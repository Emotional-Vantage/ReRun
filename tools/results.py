import json
import math
from typing import Any, Dict, Optional
from agent.state import Plan, Claim

def load_results(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def validate_results(results: Optional[Dict[str, Any]], plan: Optional[Plan], claim: Optional[Claim]) -> Dict[str, Any]:
    if not results:
        return {"valid": False, "errors": ["Results not found or invalid JSON"]}
    if not claim or not getattr(claim, "result_key", None):
        return {"valid": False, "errors": ["Missing claim or result_key"]}
        
    errors = []
    if claim.result_key not in results:
        errors.append(f"Missing result key {claim.result_key}")
        
    mean_val = results.get(claim.result_key)
    if mean_val is not None and not math.isfinite(mean_val):
        errors.append("Mean value is not finite")
        
    per_seed_key = claim.result_key.replace("_mean", "_per_seed") if "_mean" in claim.result_key else f"{claim.result_key}_per_seed"
    
    per_seed_vals = results.get(per_seed_key)
    std_val = results.get(claim.result_key.replace("_mean", "_std"))
    
    if plan and plan.seeds and per_seed_vals:
        if len(per_seed_vals) != len(plan.seeds):
            errors.append("Number of seeds run does not match plan")
            
        for v in per_seed_vals:
            if not math.isfinite(v):
                errors.append("Per seed value not finite")
                
        recomputed_mean = sum(per_seed_vals) / len(per_seed_vals) if len(per_seed_vals) > 0 else 0
        if mean_val is not None and abs(recomputed_mean - mean_val) > 1e-6:
            errors.append("Recomputed mean does not match reported mean")
            
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "mean": mean_val,
        "std": std_val,
        "per_seed": per_seed_vals
    }
