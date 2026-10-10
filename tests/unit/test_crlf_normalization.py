import subprocess
from pathlib import Path
from agent.state import ProjectState, PatchProposal, Edit, Approval
from tools.ingest import normalize_crlf_to_lf
from tools.patch import apply_patch

def test_crlf_normalization_and_patch_application(tmp_path):
    ws = tmp_path / "crlf_workspace"
    ws.mkdir()

    py_file = ws / "train.py"
    py_file.write_bytes(b"import os\r\n\r\ndef train():\r\n    loss = 0.5\r\n    return loss\r\n")
    
    cfg_file = ws / "config.yaml"
    cfg_file.write_bytes(b"epochs: 10\r\nlr: 0.001\r\n")

    bin_file = ws / "weights.pt"
    bin_file.write_bytes(b"\x00\x01\r\n\x02\x03")

    assert b"\r\n" in py_file.read_bytes()
    assert b"\r\n" in cfg_file.read_bytes()

    normalized_count = normalize_crlf_to_lf(ws)
    assert normalized_count >= 2

    assert b"\r\n" not in py_file.read_bytes()
    assert b"\n" in py_file.read_bytes()
    assert b"\r\n" not in cfg_file.read_bytes()

    subprocess.run(["git", "init"], cwd=str(ws), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(ws), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(ws), capture_output=True, check=True)
    subprocess.run(["git", "add", "-A"], cwd=str(ws), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(ws), capture_output=True, check=True)

    state = ProjectState(
        project_id="proj_crlf_test",
        source="custom",
        repo_url="https://github.com/test/repo",
        repo_commit="crlf_init",
        phase="PATCH_APPLY",
        budgets={"steps_used": 0, "patches_used": 0},
        claims=[],
        paper_settings=[],
        approvals=[
            Approval(id="A-1", patch_id="P-1", decision="approve", by="human", at="2026-10-08T00:00:00Z")
        ]
    )

    patch = PatchProposal(
        id="P-1",
        hypothesis_id="H-1",
        type="config_value",
        rationale="Update learning rate and loss target",
        evidence=["E-1"],
        alternatives_considered=[],
        edits=[
            Edit(
                file="train.py",
                op="replace_text",
                old="loss = 0.5",
                new="loss = 0.05"
            ),
            Edit(
                file="config.yaml",
                op="replace_text",
                old="lr: 0.001",
                new="lr: 0.0001"
            )
        ]
    )

    success = apply_patch(state, patch, str(ws), run_smoke=False)
    assert success is True

    updated_py = py_file.read_bytes()
    assert b"loss = 0.05" in updated_py
    assert b"\r\n" not in updated_py

    updated_cfg = cfg_file.read_bytes()
    assert b"lr: 0.0001" in updated_cfg
    assert b"\r\n" not in updated_cfg
