from agent.state import Claim, Plan
from tools.results import validate_results

def test_validate_results_valid():
    results = {
        "test_accuracy_mean": 0.95,
        "test_accuracy_per_seed": [0.94, 0.96],
        "test_accuracy_std": 0.01
    }
    plan = Plan(command="python train.py", output_file="out.json", seeds=[1, 2])
    claim = Claim(id="c1", statement="x", metric="m", reported=0.9, result_key="test_accuracy_mean", source_ref="", source_quote="")
    
    res = validate_results(results, plan, claim)
    assert res["valid"] is True
    assert res["mean"] == 0.95

def test_validate_results_missing_key():
    results = {"other_key": 0.95}
    plan = Plan(command="python train.py", output_file="out.json", seeds=[1])
    claim = Claim(id="c1", statement="x", metric="m", reported=0.9, result_key="test_accuracy_mean", source_ref="", source_quote="")
    
    res = validate_results(results, plan, claim)
    assert res["valid"] is False
    assert "Missing result key" in res["errors"][0]

def test_validate_results_seed_mismatch():
    results = {
        "test_accuracy_mean": 0.95,
        "test_accuracy_per_seed": [0.95]
    }
    plan = Plan(command="python train.py", output_file="out.json", seeds=[1, 2])
    claim = Claim(id="c1", statement="x", metric="m", reported=0.9, result_key="test_accuracy_mean", source_ref="", source_quote="")
    
    res = validate_results(results, plan, claim)
    assert res["valid"] is False
    assert "Number of seeds run does not match plan" in res["errors"][0]
