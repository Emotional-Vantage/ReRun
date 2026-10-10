import os
import json
from agent.state import Plan, PaperSetting
from tools.config_audit import audit

def test_audit_match(tmp_path):
    ws = str(tmp_path)
    eff_path = tmp_path / "eff.json"
    eff_path.write_text(json.dumps({"learning_rate": 0.01, "epochs": 20}))
    
    plan = Plan(command="python train.py", output_file="out.json", effective_config_file="eff.json", seeds=[1])
    ps1 = PaperSetting(key="learning_rate", value=0.01, source_ref="p", source_quote="q")
    ps2 = PaperSetting(key="epochs", value=20, source_ref="p", source_quote="q")
    
    diffs = audit(ws, plan, [ps1, ps2])
    
    assert len(diffs) == 2
    for d in diffs:
        assert d["status"] == "match"

def test_audit_mismatch(tmp_path):
    ws = str(tmp_path)
    eff_path = tmp_path / "eff.json"
    eff_path.write_text(json.dumps({"learning_rate": 0.1}))
    
    plan = Plan(command="python train.py", output_file="out.json", effective_config_file="eff.json", seeds=[1])
    ps1 = PaperSetting(key="learning_rate", value=0.01, source_ref="p", source_quote="q")
    
    diffs = audit(ws, plan, [ps1])
    
    assert len(diffs) == 1
    assert diffs[0]["status"] == "mismatch"
    assert diffs[0]["effective_value"] == 0.1

def test_audit_not_found(tmp_path):
    ws = str(tmp_path)
    plan = Plan(command="python train.py", output_file="out.json", seeds=[1])
    ps1 = PaperSetting(key="learning_rate", value=0.01, source_ref="p", source_quote="q")
    
    diffs = audit(ws, plan, [ps1])
    
    assert len(diffs) == 1
    assert diffs[0]["status"] == "not_found"
