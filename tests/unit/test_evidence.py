import os
from agent.state import ProjectState
from tools.evidence import record_evidence, verify_quote

def test_record_and_verify_evidence(tmp_path):
    data_dir = str(tmp_path / "data")
    src = tmp_path / "req.txt"
    src.write_text("numpy==1.0\npyyaml==2.0\n")
    
    state = ProjectState(project_id="test1", benchmark_id="b", repo_commit="c", phase="ANALYZE", budgets={}, claims=[], paper_settings=[], repo_profile={})
    
    ev = record_evidence(state, "file", str(src), None, None, "inspect_file", "call_1", data_dir=data_dir)
    
    assert ev.id == "E-001"
    assert "E-001" in state.evidence_ids
    assert "numpy" in ev.excerpt
    
    assert verify_quote(ev, "pyyaml==2.0") is True
    assert verify_quote(ev, "scipy") is False

def test_verify_quote_tamper(tmp_path):
    data_dir = str(tmp_path / "data")
    src = tmp_path / "test.txt"
    src.write_text("hello world")
    
    state = ProjectState(project_id="test1", benchmark_id="b", repo_commit="c", phase="ANALYZE", budgets={}, claims=[], paper_settings=[], repo_profile={})
    
    ev = record_evidence(state, "file", str(src), None, None, "inspect_file", "call_1", data_dir=data_dir)
    
    assert verify_quote(ev, "hello world") is True
    
    with open(ev.artifact_path, "w") as f:
        f.write("hello hacked")
        
    assert verify_quote(ev, "hello hacked") is False
