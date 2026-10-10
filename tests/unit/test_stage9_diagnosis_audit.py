import os
import json
import pytest
from pathlib import Path
from agent.state import ProjectState, PatchProposal, Edit, Hypothesis, PaperSetting, Plan
from tools.errors import classify
from tools.policy import check as check_policy
from tools.config_audit import (
    audit as audit_config,
    scan_argparse_defaults,
    scan_dataclass_defaults,
    scan_hydra_defaults,
    extract_cli_overrides,
    extract_readme_config_snippets
)
from tools.notebook import convert_notebook_to_script, is_notebook

def test_classify_python_version_mismatch():
    log_distutils = (
        "Traceback (most recent call last):\n"
        "  File 'train.py', line 3, in <module>\n"
        "    from distutils.version import LooseVersion\n"
        "ModuleNotFoundError: No module named 'distutils'"
    )
    res = classify(log_distutils)
    assert res["error_class"] == "python_version_mismatch"
    assert res["signature_id"] == "py-version-mismatch"

    log_union_syntax = "TypeError: unsupported operand type(s) for |: 'type' and 'type'"
    res2 = classify(log_union_syntax)
    assert res2["error_class"] == "python_version_mismatch"

def test_classify_api_deprecation():
    log_np_int = (
        "Traceback (most recent call last):\n"
        "  File 'model.py', line 12, in <module>\n"
        "    x = np.int(42)\n"
        "AttributeError: module 'numpy' has no attribute 'int'"
    )
    res = classify(log_np_int)
    assert res["error_class"] == "api_deprecation"
    assert res["signature_id"] == "api-deprecation"

    log_df_append = "AttributeError: 'DataFrame' object has no attribute 'append'"
    res2 = classify(log_df_append)
    assert res2["error_class"] == "api_deprecation"

    log_scipy = "ImportError: cannot import name 'imread' from 'scipy.misc'"
    res3 = classify(log_scipy)
    assert res3["error_class"] == "api_deprecation"

def test_classify_dataset_missing():
    log_missing_data = (
        "Traceback (most recent call last):\n"
        "  File 'train.py', line 24, in <module>\n"
        "    data = pd.read_csv('data/digits.csv')\n"
        "FileNotFoundError: [Errno 2] No such file or directory: 'data/digits.csv'"
    )
    res = classify(log_missing_data)
    assert res["error_class"] == "dataset_missing"
    assert res["signature_id"] == "dataset-missing"

    log_runtime_ds = "RuntimeError: Dataset mnist not found. Please download the dataset"
    res2 = classify(log_runtime_ds)
    assert res2["error_class"] == "dataset_missing"

def test_classify_device_unavailable():
    log_no_cuda = (
        "Traceback (most recent call last):\n"
        "  File 'train.py', line 15, in <module>\n"
        "    model = model.cuda()\n"
        "RuntimeError: No CUDA GPUs are available"
    )
    res = classify(log_no_cuda)
    assert res["error_class"] == "device_unavailable"
    assert res["signature_id"] == "device-unavailable"

    log_no_driver = "RuntimeError: Found no NVIDIA driver on your system"
    res2 = classify(log_no_driver)
    assert res2["error_class"] == "device_unavailable"

def test_classify_attempt_flags_oom_and_timeout(tmp_path):
    class MockAttempt:
        exit_code = 137
        oom = True
        timed_out = False

    res_exit137 = classify(log_text="", attempt=MockAttempt())
    assert res_exit137["error_class"] == "resource_oom"

    res_oom = classify(log_text="command terminated unexpectedly", oom=True)
    assert res_oom["error_class"] == "resource_oom"

    res_timeout = classify(log_text="", timed_out=True)
    assert res_timeout["error_class"] == "resource_timeout"
    assert res_timeout["signature_id"] == "timeout"

def test_gate_gold_patches_per_new_error_class_pass_policy(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "configs").mkdir()
    (ws / "configs" / "default.yaml").write_text("device: cuda\ndownload: false\n", encoding="utf-8")
    (ws / "model.py").write_text("import numpy as np\nx = np.int(1)\n", encoding="utf-8")

    state = ProjectState(
        project_id="proj_gate_gold",
        source="custom",
        phase="POLICY_CHECK",
        budgets={"steps_used": 1, "patches_used": 0},
        claims=[],
        paper_settings=[],
        evidence_ids=["E-001", "E-002", "E-003", "E-004"],
        hypotheses=[
            Hypothesis(id="H-1", text="distutils removed in Python 3.12", status="confirmed", evidence=["E-001"], error_class="python_version_mismatch"),
            Hypothesis(id="H-2", text="np.int deprecated in NumPy 1.24", status="confirmed", evidence=["E-002"], error_class="api_deprecation"),
            Hypothesis(id="H-3", text="Dataset not downloaded locally", status="confirmed", evidence=["E-003"], error_class="dataset_missing"),
            Hypothesis(id="H-4", text="CUDA device unavailable on CPU host", status="confirmed", evidence=["E-004"], error_class="device_unavailable"),
        ]
    )

    patch_ver = PatchProposal(
        id="P-001",
        hypothesis_id="H-1",
        type="code_api_compat",
        rationale="Replace distutils.version with packaging.version with traceback in model.py",
        evidence=["E-001"],
        alternatives_considered=[],
        edits=[Edit(file="model.py", op="replace_text", old="from distutils.version import LooseVersion", new="from packaging.version import parse as LooseVersion")]
    )
    pol_ver = check_policy(state, patch_ver, workspace=str(ws))
    assert pol_ver["passed"] is True
    assert pol_ver["risk_class"] == "bug_fix"

    patch_dep = PatchProposal(
        id="P-002",
        hypothesis_id="H-2",
        type="code_api_compat",
        rationale="Replace deprecated np.int with built-in int with traceback citing model.py:2",
        evidence=["E-002"],
        alternatives_considered=[],
        edits=[Edit(file="model.py", op="replace_text", old="np.int", new="int")]
    )
    pol_dep = check_policy(state, patch_dep, workspace=str(ws))
    assert pol_dep["passed"] is True
    assert pol_dep["risk_class"] == "bug_fix"

    patch_ds = PatchProposal(
        id="P-003",
        hypothesis_id="H-3",
        type="config_value",
        rationale="Enable dataset auto-download in default.yaml",
        evidence=["E-003"],
        alternatives_considered=[],
        edits=[Edit(file="configs/default.yaml", op="replace_text", old="download: false", new="download: true")]
    )
    pol_ds = check_policy(state, patch_ds, workspace=str(ws))
    assert pol_ds["passed"] is True
    assert pol_ds["risk_class"] in ["config_alignment", "bug_fix"]

    patch_dev = PatchProposal(
        id="P-004",
        hypothesis_id="H-4",
        type="config_value",
        rationale="Switch target device to CPU in default.yaml",
        evidence=["E-004"],
        alternatives_considered=[],
        edits=[Edit(file="configs/default.yaml", op="replace_text", old="device: cuda", new="device: cpu")]
    )
    pol_dev = check_policy(state, patch_dev, workspace=str(ws))
    assert pol_dev["passed"] is True
    assert pol_dev["risk_class"] in ["config_alignment", "bug_fix"]

def test_gate_negative_fixture_blocks_changing_evaluation_code(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "evaluate.py").write_text("acc = compute_accuracy()\n", encoding="utf-8")

    state = ProjectState(
        project_id="proj_neg_eval",
        source="custom",
        phase="POLICY_CHECK",
        budgets={"steps_used": 1, "patches_used": 0},
        claims=[],
        paper_settings=[],
        evidence_ids=["E-001"],
        hypotheses=[
            Hypothesis(id="H-1", text="Evaluation metric divergence", status="confirmed", evidence=["E-001"])
        ],
        allow_high_risk=False
    )

    bad_proposal = PatchProposal(
        id="P-MALICIOUS",
        hypothesis_id="H-1",
        type="code_api_compat",
        rationale="Change evaluation code to match the paper 95.6%",
        evidence=["E-001"],
        alternatives_considered=[],
        edits=[Edit(file="evaluate.py", op="replace_text", old="acc = compute_accuracy()", new="acc = 0.956")]
    )

    res = check_policy(state, bad_proposal, workspace=str(ws))
    assert res["passed"] is False
    assert any("blocked by deny list" in v.lower() or "evaluate.py" in v.lower() for v in res["violations"])
    assert res["risk_class"] == "deviation"

def test_code_api_compat_requires_traceback_provenance(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "train.py").write_text("x = 1\n", encoding="utf-8")

    state = ProjectState(
        project_id="proj_no_provenance",
        source="custom",
        phase="POLICY_CHECK",
        budgets={"steps_used": 1, "patches_used": 0},
        claims=[],
        paper_settings=[],
        evidence_ids=["E-001"],
        hypotheses=[
            Hypothesis(id="H-1", text="Some hypothesis", status="confirmed", evidence=["E-001"])
        ]
    )

    unproven_patch = PatchProposal(
        id="P-001",
        hypothesis_id="H-1",
        type="code_api_compat",
        rationale="Arbitrary modification without any traceback citation or file reference",
        evidence=["E-001"],
        alternatives_considered=[],
        edits=[Edit(file="train.py", op="replace_text", old="x = 1", new="x = 2")]
    )

    res = check_policy(state, unproven_patch, workspace=str(ws))
    assert res["passed"] is False
    assert any("traceback provenance" in v.lower() for v in res["violations"])

def test_config_audit_argparse_and_dataclass_ast_scan(tmp_path):
    ws = tmp_path / "ws_audit"
    ws.mkdir()

    train_py = ws / "train.py"
    train_py.write_text(
        "import argparse\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--lr', type=float, default=0.001)\n"
        "parser.add_argument('--batch-size', type=int, default=32)\n"
        "parser.add_argument('--epochs', type=int, default=25)\n",
        encoding="utf-8"
    )

    config_py = ws / "config.py"
    config_py.write_text(
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class ModelConfig:\n"
        "    hidden_dim: int = 128\n"
        "    weight_decay: float = 0.0001\n",
        encoding="utf-8"
    )

    argparse_defs = scan_argparse_defaults(str(ws))
    assert "learning_rate" in argparse_defs
    assert argparse_defs["learning_rate"]["value"] == 0.001
    assert argparse_defs["batch_size"]["value"] == 32
    assert argparse_defs["epochs"]["value"] == 25

    dc_defs = scan_dataclass_defaults(str(ws))
    assert "hidden_dim" in dc_defs
    assert dc_defs["hidden_dim"]["value"] == 128
    assert dc_defs["weight_decay"]["value"] == 0.0001

def test_config_audit_hydra_defaults_and_cli_overrides(tmp_path):
    ws = tmp_path / "ws_hydra"
    ws.mkdir()
    (ws / "configs").mkdir()
    (ws / "configs" / "model").mkdir()

    (ws / "configs" / "model" / "resnet.yaml").write_text("learning_rate: 0.1\nepochs: 10\n", encoding="utf-8")

    main_yaml = ws / "configs" / "main.yaml"
    main_yaml.write_text(
        "defaults:\n"
        "  - model: resnet\n"
        "batch_size: 64\n",
        encoding="utf-8"
    )

    plan = Plan(
        command="python train.py --config configs/main.yaml --lr 0.05",
        config_file="configs/main.yaml",
        output_file="outputs/results.json",
        seeds=[0]
    )

    paper_settings = [
        PaperSetting(key="learning_rate", value=0.05, source_ref="p.2", source_quote="lr=0.05"),
        PaperSetting(key="batch_size", value=64, source_ref="p.2", source_quote="bs=64"),
        PaperSetting(key="epochs", value=100, source_ref="p.2", source_quote="epochs=100"),
    ]

    diffs = audit_config(str(ws), plan, paper_settings)

    assert all(d["confidence"] == "static" for d in diffs)

    lr_diff = next(d for d in diffs if d["key"] == "learning_rate")
    assert lr_diff["effective_value"] == 0.05
    assert lr_diff["status"] == "match"
    assert lr_diff["source_type"] == "cli_override"

    bs_diff = next(d for d in diffs if d["key"] == "batch_size")
    assert bs_diff["effective_value"] == 64
    assert bs_diff["status"] == "match"

    ep_diff = next(d for d in diffs if d["key"] == "epochs")
    assert ep_diff["effective_value"] == 10
    assert ep_diff["status"] == "mismatch"

def test_config_audit_runtime_confidence_when_effective_captured(tmp_path):
    ws = tmp_path / "ws_runtime"
    ws.mkdir()
    eff_cfg = ws / "effective.json"
    eff_cfg.write_text(json.dumps({"lr": 0.01, "batch_size": 32}), encoding="utf-8")

    plan = Plan(
        command="python train.py",
        effective_config_file="effective.json",
        output_file="outputs/results.json",
        seeds=[0]
    )

    paper_settings = [
        PaperSetting(key="learning_rate", value=0.01, source_ref="p.1", source_quote="lr 0.01")
    ]

    diffs = audit_config(str(ws), plan, paper_settings)
    assert len(diffs) == 1
    assert diffs[0]["confidence"] == "runtime"
    assert diffs[0]["status"] == "match"
    assert diffs[0]["source_type"] == "runtime_effective"

def test_notebook_conversion_strips_magics_deterministically(tmp_path):
    nb_dict = {
        "nbformat": 4,
        "nbformat_minor": 2,
        "cells": [
            {
                "cell_type": "markdown",
                "source": ["# Analysis Notebook\n", "This is documentation."]
            },
            {
                "cell_type": "code",
                "source": [
                    "%matplotlib inline\n",
                    "!pip install -q torch\n",
                    "import torch\n",
                    "get_ipython().run_line_magic('time', '')\n",
                    "x = torch.tensor([1, 2, 3])\n",
                    "print(x.shape)\n"
                ]
            }
        ]
    }
    nb_file = tmp_path / "experiment.ipynb"
    nb_file.write_text(json.dumps(nb_dict), encoding="utf-8")

    assert is_notebook(str(nb_file)) is True

    out_py = tmp_path / "experiment.py"
    res = convert_notebook_to_script(str(nb_file), str(out_py))

    assert res["success"] is True
    assert res["code_cell_count"] == 1
    assert res["magics_commented_count"] == 3

    script = out_py.read_text(encoding="utf-8")
    assert "# [Jupyter Magic Commented]: %matplotlib inline" in script
    assert "# [Jupyter Magic Commented]: !pip install -q torch" in script
    assert "# [Jupyter get_ipython() Commented]: get_ipython().run_line_magic('time', '')" in script
    assert "import torch" in script
    assert "print(x.shape)" in script

def test_notebook_conversion_malformed_returns_unsupported_format(tmp_path):
    bad_file = tmp_path / "corrupted.ipynb"
    bad_file.write_text("{not valid json ...", encoding="utf-8")

    res = convert_notebook_to_script(str(bad_file))
    assert res["success"] is False
    assert res["error"] == "UNSUPPORTED_FORMAT"
