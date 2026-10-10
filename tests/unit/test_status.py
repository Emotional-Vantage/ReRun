from agent.state import ProjectState, Attempt, Claim
from tools.status import compute_status

def test_status_unable_preflight():
    state = ProjectState(project_id="1", benchmark_id="b", repo_commit="c", phase="STATUS", budgets={}, claims=[], paper_settings=[], repo_profile={})
    state.preflight = {"blockers": ["gpu_required"]}
    res = compute_status(state)
    assert res["status"] == "UNABLE_TO_EXECUTE"
    assert res["reason"] == "gpu_required"

def test_status_inconclusive_no_claim():
    state = ProjectState(project_id="1", benchmark_id="b", repo_commit="c", phase="STATUS", budgets={}, claims=[], paper_settings=[], repo_profile={})
    res = compute_status(state)
    assert res["status"] == "INCONCLUSIVE"
    assert res["reason"] == "no claim confirmed"

def test_status_reproduced():
    c = Claim(id="c1", statement="x", metric="m", reported=1.0, source_ref="p", source_quote="q", confirmed_by_human=True)
    state = ProjectState(project_id="1", benchmark_id="b", repo_commit="c", phase="STATUS", budgets={}, claims=[c], paper_settings=[], repo_profile={})
    
    att = Attempt(n=1, patches_applied=[], exit_code=0, started_at="now", comparison=[{"claim_id": "c1", "within_tolerance": True}])
    state.attempts.append(att)
    
    res = compute_status(state)
    assert res["status"] == "REPRODUCED"

def test_status_not_reproduced():
    c = Claim(id="c1", statement="x", metric="m", reported=1.0, source_ref="p", source_quote="q", confirmed_by_human=True)
    state = ProjectState(project_id="1", benchmark_id="b", repo_commit="c", phase="STATUS", budgets={}, claims=[c], paper_settings=[], repo_profile={})
    
    att = Attempt(n=1, patches_applied=[], exit_code=0, started_at="now", comparison=[{"claim_id": "c1", "within_tolerance": False}], metrics={"test_accuracy_std": 0.0})
    state.attempts.append(att)
    
    res = compute_status(state)
    assert res["status"] == "NOT_REPRODUCED"
