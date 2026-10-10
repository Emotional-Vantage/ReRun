def compute_status(state):
    preflight_blockers = state.preflight.get("blockers", [])
    
    # 1. environmental failures
    env_failed = False
    if preflight_blockers:
        env_failed = True
        
    last_valid_run = None
    if not env_failed:
        for att in reversed(state.attempts):
            if att.exit_code == 0 and att.comparison is not None:
                last_valid_run = att
                break
        
        # If no valid run and max patches applied (or out of budget)
        if last_valid_run is None and state.phase == "STATUS":
            if any(att.error_class and att.error_class != "metric_extraction_failed" for att in state.attempts):
                return {
                    "status": "UNABLE_TO_EXECUTE",
                    "reason": "run never completed successfully",
                    "after_n_fixes": 0,
                    "confidence_factors": {}
                }
    
    if env_failed:
        triage_verdict = state.preflight.get("triage_verdict")
        reason = triage_verdict if triage_verdict and triage_verdict != "FEASIBLE" else (preflight_blockers[0] if preflight_blockers else "unknown environment error")

        detail = state.preflight.get("gpu_detail") if "gpu_required" in preflight_blockers else None
        if detail:
            reason = f"{reason}: {detail}"

        return {
            "status": "UNABLE_TO_EXECUTE",
            "reason": reason,
            "after_n_fixes": 0,
            "confidence_factors": {},
            "blockers": preflight_blockers
        }
        
    primary_claims = [c for c in state.claims if c.primary and c.confirmed_by_human]
    
    # 2. no confirmed claim
    if not primary_claims:
        return {
            "status": "INCONCLUSIVE",
            "reason": "no claim confirmed",
            "after_n_fixes": 0,
            "confidence_factors": {}
        }
        
    # 3. run completed but results invalid/unparseable (handled by no valid run finding)
    if not last_valid_run:
        failed_ext = any(att.error_class == "metric_extraction_failed" for att in state.attempts)
        reason = "metric extraction failed" if failed_ext else "results invalid or unparseable"
        return {
            "status": "INCONCLUSIVE",
            "reason": reason,
            "after_n_fixes": 0,
            "confidence_factors": {"variance": "unknown"}
        }

    # 4. Check comparisons
    within_count = 0
    comparisons = last_valid_run.comparison or []
    comp_map = {c["claim_id"]: c for c in comparisons}
    
    for c in primary_claims:
        comp = comp_map.get(c.id)
        if comp and comp.get("within_tolerance"):
            within_count += 1
            
    patches_applied_count = len([p for p in state.patches if p.status == "applied"])
    deviation_patch = any(p.risk_class == "deviation" for p in state.patches if p.status == "applied")
    seeds_run = len(state.plan.seeds) if state.plan and state.plan.seeds else 1
    confidence_factors = {}
    if seeds_run <= 1:
        confidence_factors["variance"] = "n=1, variance unknown"
    
    if within_count == len(primary_claims):
        if deviation_patch:
            return {
                "status": "PARTIALLY_REPRODUCED",
                "reason": "reproduced only under a deviation",
                "after_n_fixes": patches_applied_count,
                "confidence_factors": confidence_factors
            }
        else:
            return {
                "status": "REPRODUCED",
                "reason": "all primary claims within tolerance",
                "after_n_fixes": patches_applied_count,
                "confidence_factors": confidence_factors
            }
            
    elif 0 < within_count < len(primary_claims):
        return {
            "status": "PARTIALLY_REPRODUCED",
            "reason": f"{within_count} of {len(primary_claims)} claims within tolerance",
            "after_n_fixes": patches_applied_count,
            "confidence_factors": confidence_factors
        }
        
    else: # none within
        high_variance = False
        std_across_seeds = 0.0
        if last_valid_run.metrics:
            std_across_seeds = (
                last_valid_run.metrics.get(f"{primary_claims[0].metric}_std") or
                last_valid_run.metrics.get(f"{primary_claims[0].id}_std") or
                last_valid_run.metrics.get("test_accuracy_std", 0.0)
            )
        tol_abs = primary_claims[0].tolerance.value
        
        if std_across_seeds > tol_abs or (seeds_run < 3 and state.plan and len(state.plan.seeds) >= 3):
            high_variance = True
            
        has_mismatch = any(d.get("status") == "mismatch" for d in state.config_diff)
        ambiguous = len(state.unresolved_issues) > 0 or has_mismatch
        
        if high_variance or ambiguous:
            return {
                "status": "INCONCLUSIVE",
                "reason": "high variance or ambiguous state",
                "after_n_fixes": patches_applied_count,
                "confidence_factors": confidence_factors
            }
        else:
            return {
                "status": "NOT_REPRODUCED",
                "reason": "outside tolerance with confidence",
                "after_n_fixes": patches_applied_count,
                "confidence_factors": confidence_factors
            }
