import json
from pathlib import Path
import pytest
from agent.state import ProjectState, PatchProposal, Edit, Hypothesis, PaperSetting
from tools.policy import check, check_patch

def make_test_state(**kwargs):
    h = Hypothesis(id="H-1", text="test hypo", status="confirmed", error_class="unknown", evidence=["E-001"])
    defaults = dict(
        project_id="1", benchmark_id="b", repo_commit="c",
        phase="POLICY_CHECK", budgets={}, claims=[],
        paper_settings=[PaperSetting(key="learning_rate", value=0.5, source_ref="p.1", source_quote="learning rate = 0.5")],
        repo_profile={}, allow_high_risk=False,
        hypotheses=[h],
        evidence_ids=["E-001"]
    )
    defaults.update(kwargs)
    return ProjectState(**defaults)

def test_policy_deny_list_blocked():
    state = make_test_state(allow_high_risk=False)
    prop = PatchProposal(
        id="p1", hypothesis_id="H-1", type="code_typo", rationale="fix typo",
        evidence=["E-001"], alternatives_considered=[], edits=[
            Edit(file="evaluate.py", op="replace_text", new="abc")
        ]
    )
    res = check(state, prop)
    assert res["passed"] is False
    assert any("P2" in v for v in res["violations"])
    
def test_policy_deny_list_allowed_if_opt_in():
    state = make_test_state(allow_high_risk=True)
    prop = PatchProposal(
        id="p1", hypothesis_id="H-1", type="code_typo", rationale="fix typo",
        evidence=["E-001"], alternatives_considered=[], edits=[
            Edit(file="evaluate.py", op="replace_text", new="abc")
        ]
    )
    res = check(state, prop)
    assert res["passed"] is True
    assert res["requires_extra_confirm"] is True
    assert res["risk_class"] == "deviation"
    
def test_policy_soft_size_threshold():
    state = make_test_state()
    edits = []
    for i in range(25): # > 20 lines (soft threshold) but <= 200 lines
        edits.append(Edit(file="configs/default.yaml", op="append_line", new=f"comment_{i}: {i}"))
    
    prop = PatchProposal(
        id="p1", hypothesis_id="H-1", type="config_value", rationale="adjust config",
        evidence=["E-001"], alternatives_considered=[], edits=edits
    )
    res = check(state, prop)
    assert res["passed"] is True
    assert "large_patch" in res["flags"]
    assert res["requires_extra_confirm"] is True

def test_policy_hard_size_limit():
    state = make_test_state()
    edits = []
    for i in range(205): # > 200 lines (hard limit)
        edits.append(Edit(file="configs/default.yaml", op="append_line", new=f"comment_{i}: {i}"))
    
    prop = PatchProposal(
        id="p1", hypothesis_id="H-1", type="config_value", rationale="adjust config",
        evidence=["E-001"], alternatives_considered=[], edits=edits
    )
    res = check(state, prop)
    assert res["passed"] is False
    assert any("P3" in v for v in res["violations"])

def test_policy_sensitive_key_matching_paper():
    state = make_test_state(paper_settings=[
        PaperSetting(key="epochs", value=20, source_ref="p.1", source_quote="epochs = 20")
    ])
    prop = PatchProposal(
        id="p1", hypothesis_id="H-1", type="config_value", rationale="match paper epochs",
        evidence=["E-001"], alternatives_considered=[], edits=[
            Edit(file="configs/default.yaml", op="replace_text", old="epochs: 10", new="epochs: 20")
        ]
    )
    res = check(state, prop)
    assert res["passed"] is True
    assert "sensitive_key" in res["flags"]
    assert res["requires_extra_confirm"] is True

def test_policy_sensitive_key_not_matching_paper():
    state = make_test_state(paper_settings=[
        PaperSetting(key="epochs", value=20, source_ref="p.1", source_quote="epochs = 20")
    ])
    prop = PatchProposal(
        id="p1", hypothesis_id="H-1", type="config_value", rationale="tune epochs",
        evidence=["E-001"], alternatives_considered=[], edits=[
            Edit(file="configs/default.yaml", op="replace_text", old="epochs: 10", new="epochs: 50")
        ]
    )
    res = check(state, prop)
    assert res["passed"] is False
    assert any("sensitive_key_locked" in v for v in res["violations"])

def test_policy_sensitive_key_in_python_code():
    state = make_test_state(paper_settings=[
        PaperSetting(key="epochs", value=20, source_ref="p.1", source_quote="epochs = 20")
    ])
    prop = PatchProposal(
        id="p1", hypothesis_id="H-1", type="code_typo", rationale="change code epoch literal",
        evidence=["E-001"], alternatives_considered=[], edits=[
            Edit(file="train.py", op="replace_text", old="epochs = 10", new="epochs = 20")
        ]
    )
    res = check(state, prop)
    assert res["passed"] is False
    assert any("sensitive_key_locked" in v for v in res["violations"])

def test_policy_non_paper_param_with_error_provenance():
    state = make_test_state()
    prop = PatchProposal(
        id="p1", hypothesis_id="H-1", type="config_value", rationale="fix non-paper param based on traceback",
        evidence=["E-001"], alternatives_considered=[], edits=[
            Edit(file="configs/default.yaml", op="replace_text", old="custom_opt: 1", new="custom_opt: 2")
        ]
    )
    res = check(state, prop)
    assert res["passed"] is True
    assert "non_paper_param" in res["flags"]
    assert res["risk_class"] == "bug_fix"
    assert res["requires_extra_confirm"] is True

def test_policy_non_paper_param_without_error_provenance():
    h_mismatch = Hypothesis(id="H-2", text="config mismatch", status="confirmed", error_class="config_mismatch", evidence=["E-001"])
    state = make_test_state(hypotheses=[h_mismatch])
    prop = PatchProposal(
        id="p1", hypothesis_id="H-2", type="config_value", rationale="tweak custom_opt without error traceback",
        evidence=["E-001"], alternatives_considered=[], edits=[
            Edit(file="configs/default.yaml", op="replace_text", old="custom_opt: 1", new="custom_opt: 2")
        ]
    )
    res = check(state, prop)
    assert res["passed"] is False
    assert any("no_provenance" in v for v in res["violations"])

@pytest.mark.parametrize("proposed,should_pass", [
    ("learning_rate: 0.5", True),            # exact
    ("learning_rate: 0.50", True),           # same value, different spelling
    ("learning_rate: 5e-1", True),           # same value, scientific notation
    ("learning_rate: 0.5  # from paper", True),  # inline comment
    ("lr: 0.5", True),                       # alias of the paper key
    ("learning_rate: 0.555", False),         # contains "0.5" as a substring
    ("learning_rate: 10.567", False),        # contains "0.5" as a substring
    ("learning_rate: 0.7", False),           # plainly different
    ("learning_rate: not_a_number", False),  # unparseable fails closed
])
def test_paper_value_match_is_numeric_not_substring(proposed, should_pass):
    state = make_test_state()
    prop = PatchProposal(
        id="p1", hypothesis_id="H-1", type="config_value",
        rationale="Align learning rate with the paper-stated value",
        evidence=["E-001"], alternatives_considered=[],
        edits=[Edit(file="configs/default.yaml", op="replace_text",
                    old="learning_rate: 0.01", new=proposed)],
    )
    res = check(state, prop)
    assert res["passed"] is should_pass, (
        f"{proposed!r}: expected passed={should_pass}, got {res['passed']} "
        f"violations={res['violations']}"
    )

def test_sensitive_key_value_match_is_numeric_not_substring():
    state = make_test_state(paper_settings=[
        PaperSetting(key="epochs", value=20, source_ref="p.1", source_quote="epochs = 20")
    ])
    prop = PatchProposal(
        id="p1", hypothesis_id="H-1", type="config_value", rationale="match paper epochs",
        evidence=["E-001"], alternatives_considered=[],
        edits=[Edit(file="configs/default.yaml", op="replace_text",
                    old="epochs: 10", new="epochs: 200")],
    )
    res = check(state, prop)
    assert res["passed"] is False
    assert any("sensitive_key_locked" in v for v in res["violations"])

@pytest.mark.parametrize("fixture_name", [
    "x1_deny_list.json",
    "x3_sensitive_key_unaligned.json",
    "x4_oversized_patch.json",
    "x5_missing_evidence.json",
    "x7_unpinned_dependency.json",
    "x8_data_semantics_change.json",
    "x9_code_literal_sensitive_key.json",
])
def test_policy_adversarial_fixtures_refused(fixture_name):
    fixture_path = Path("benchmarks/adversarial") / fixture_name
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    state = make_test_state()
    prop_data = fixture["proposal"]
    edits = [Edit(**e) for e in prop_data["edits"]]
    if fixture.get("num_lines", 0) > 200:
        for i in range(fixture["num_lines"]):
            edits.append(Edit(file="configs/default.yaml", op="append_line", new=f"# pad {i}"))
    prop = PatchProposal(
        id=prop_data["id"],
        hypothesis_id=prop_data["hypothesis_id"],
        type=prop_data["type"],
        rationale=prop_data["rationale"],
        evidence=prop_data["evidence"],
        alternatives_considered=[],
        edits=edits,
    )
    res = check(state, prop)
    assert res["passed"] is False
    assert len(res["violations"]) > 0
