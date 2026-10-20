import pytest
from pathlib import Path

from agent.state import ProjectState, PatchProposal, Edit, Approval
from tools.patch import apply_patch, revert_patch, apply_edits_in_memory, make_diff

def test_apply_patch_requires_approval(tmp_path):
    ws = str(tmp_path)
    (Path(ws) / "test.txt").write_text("hello\n", encoding="utf-8")
    
    state = ProjectState(
        project_id="test_p",
        benchmark_id="b1",
        repo_commit="c",
        phase="PATCH_APPLY",
        budgets={},
        claims=[],
        paper_settings=[],
        repo_profile={},
        approvals=[] # No approval
    )
    
    patch = PatchProposal(
        id="P-1",
        hypothesis_id="H-1",
        type="code_typo",
        rationale="Fix typo",
        evidence=["E-001"],
        alternatives_considered=[],
        edits=[Edit(file="test.txt", op="replace_text", old="hello", new="world")]
    )
    
    with pytest.raises(PermissionError) as exc_info:
        apply_patch(state, patch, ws)
    assert "Invariant I8" in str(exc_info.value)

def test_apply_and_revert_patch(tmp_path):
    ws = str(tmp_path)
    target = Path(ws) / "test.py"
    target.write_text("x = 1\n", encoding="utf-8")
    
    state = ProjectState(
        project_id="test_p2",
        benchmark_id="b1",
        repo_commit="c",
        phase="PATCH_APPLY",
        budgets={},
        claims=[],
        paper_settings=[],
        repo_profile={},
        approvals=[
            Approval(id="A-1", patch_id="P-1", decision="approve", by="human", at="now")
        ]
    )
    
    patch = PatchProposal(
        id="P-1",
        hypothesis_id="H-1",
        type="code_typo",
        rationale="Update x",
        evidence=["E-001"],
        alternatives_considered=[],
        edits=[Edit(file="test.py", op="replace_text", old="x = 1", new="x = 2")],
        fix_signature="sig_p1"
    )
    
    success = apply_patch(state, patch, ws)
    assert success is True
    assert target.read_text(encoding="utf-8") == "x = 2\n"
    assert patch.status == "applied"
    
    # Revert patch
    revert_success = revert_patch(state, patch, ws)
    assert revert_success is True
    assert target.read_text(encoding="utf-8") == "x = 1\n"
    assert patch.status == "reverted"
    assert "sig_p1" in state.failed_fixes

def test_apply_patch_smoke_failure_auto_reverts(tmp_path):
    ws = str(tmp_path)
    target = Path(ws) / "bad.py"
    target.write_text("valid = True\n", encoding="utf-8")
    
    state = ProjectState(
        project_id="test_p3",
        benchmark_id="b1",
        repo_commit="c",
        phase="PATCH_APPLY",
        budgets={},
        claims=[],
        paper_settings=[],
        repo_profile={},
        approvals=[
            Approval(id="A-1", patch_id="P-1", decision="approve", by="human", at="now")
        ]
    )
    
    # Patch introduces Python syntax error
    patch = PatchProposal(
        id="P-1",
        hypothesis_id="H-1",
        type="code_typo",
        rationale="Break syntax",
        evidence=["E-001"],
        alternatives_considered=[],
        edits=[Edit(file="bad.py", op="replace_text", old="valid = True", new="def (invalid syntax")],
        fix_signature="sig_bad"
    )
    
    success = apply_patch(state, patch, ws)
    assert success is False
    assert target.read_text(encoding="utf-8") == "valid = True\n"
    assert "sig_bad" in state.failed_fixes


@pytest.mark.parametrize("file_name", ["../outside.py", "/tmp/outside.py"])
def test_apply_edits_rejects_paths_outside_workspace(tmp_path, file_name):
    (tmp_path / "inside.py").write_text("value = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="escapes workspace"):
        apply_edits_in_memory(
            str(tmp_path),
            [Edit(file=file_name, op="append_line", new="value = 2")],
        )


def test_apply_edits_rejects_symlink_escape(tmp_path):
    outside = tmp_path.parent / "rerun-outside.py"
    outside.write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "linked.py").symlink_to(outside)

    with pytest.raises(ValueError, match="escapes workspace"):
        apply_edits_in_memory(
            str(tmp_path),
            [Edit(file="linked.py", op="append_line", new="value = 2")],
        )
