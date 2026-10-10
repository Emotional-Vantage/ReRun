import os
import ast
import re
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

ALIAS_MAP: Dict[str, List[str]] = {
    "learning_rate": ["lr", "learning_rate", "learn_rate", "base_lr", "init_lr", "lr_rate"],
    "epochs": ["epochs", "n_epochs", "num_epochs", "max_epochs", "total_epochs", "epoch"],
    "batch_size": ["batch_size", "bs", "batchsize", "train_batch_size", "batch_sz"],
    "seeds": ["seeds", "seed", "random_seed", "manual_seed"],
    "weight_decay": ["weight_decay", "wd", "w_decay", "l2"],
    "test_size": ["test_size"],
    "optimizer": ["optimizer", "opt", "optim"],
    "momentum": ["momentum", "mom"],
    "dropout": ["dropout", "drop_rate", "p_dropout"],
    "hidden_dim": ["hidden_dim", "hidden_size", "n_hidden", "d_model"]
}

def get_canonical_key(key: str) -> str:
    """Returns the canonical parameter name for any alias."""
    clean = key.strip().lower().replace("-", "_").replace(" ", "_")
    for can, aliases in ALIAS_MAP.items():
        if clean in aliases or clean == can:
            return can
    return clean

def _eval_ast_constant(node: ast.AST) -> Any:
    """Safely evaluates an AST constant, literal, or expression."""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        operand = _eval_ast_constant(node.operand)
        if isinstance(operand, (int, float)):
            return -operand
    elif isinstance(node, (ast.List, ast.Tuple)):
        return [_eval_ast_constant(elt) for elt in node.elts]
    elif isinstance(node, ast.Dict):
        res = {}
        for k, v in zip(node.keys, node.values):
            if k:
                res[_eval_ast_constant(k)] = _eval_ast_constant(v)
        return res
    elif isinstance(node, ast.Call):
        func_name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
        if func_name in ("field", "Field"):
            for kw in node.keywords:
                if kw.arg in ("default", "default_factory"):
                    return _eval_ast_constant(kw.value)
    return None

def scan_argparse_defaults(workspace: str, target_file: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    ws_path = Path(workspace)
    if not ws_path.is_dir():
        return results

    py_files: List[Path] = []
    if target_file and (ws_path / target_file).is_file():
        py_files.append(ws_path / target_file)
    else:
        for p in ws_path.rglob("*.py"):
            if "test" in p.name.lower() or "venv" in str(p) or ".git" in str(p):
                continue
            py_files.append(p)

    for py_file in py_files:
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"))
            rel_file = str(py_file.relative_to(ws_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = getattr(node, "func", None)
                    if isinstance(func, ast.Attribute) and func.attr == "add_argument":
                        opt_names: List[str] = []
                        for arg in node.args:
                            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                opt_names.append(arg.value)
                        
                        default_val = None
                        has_default = False
                        for kw in node.keywords:
                            if kw.arg == "default":
                                default_val = _eval_ast_constant(kw.value)
                                has_default = True
                                break

                        if has_default and opt_names:
                            clean_name = opt_names[-1].lstrip("-").replace("-", "_").lower()
                            can_k = get_canonical_key(clean_name)
                            if can_k not in results:
                                results[can_k] = {
                                    "value": default_val,
                                    "raw_key": clean_name,
                                    "source_file": rel_file,
                                    "source_line": node.lineno,
                                    "source_type": "argparse_default"
                                }
        except Exception:
            continue

    return results

def scan_dataclass_defaults(workspace: str, target_file: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    ws_path = Path(workspace)
    if not ws_path.is_dir():
        return results

    py_files: List[Path] = []
    if target_file and (ws_path / target_file).is_file():
        py_files.append(ws_path / target_file)
    else:
        for p in ws_path.rglob("*.py"):
            if "test" in p.name.lower() or "venv" in str(p) or ".git" in str(p):
                continue
            py_files.append(p)

    for py_file in py_files:
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"))
            rel_file = str(py_file.relative_to(ws_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    is_dc = any(
                        (getattr(d, "id", "") == "dataclass" or getattr(d, "attr", "") == "dataclass")
                        for d in node.decorator_list
                    ) or "config" in node.name.lower()
                    if is_dc:
                        for body_item in node.body:
                            if isinstance(body_item, ast.AnnAssign) and body_item.value:
                                field_name = getattr(body_item.target, "id", "")
                                if field_name:
                                    val = _eval_ast_constant(body_item.value)
                                    can_k = get_canonical_key(field_name)
                                    if can_k not in results:
                                        results[can_k] = {
                                            "value": val,
                                            "raw_key": field_name,
                                            "source_file": rel_file,
                                            "source_line": body_item.lineno,
                                            "source_type": "dataclass_default"
                                        }
        except Exception:
            continue

    return results

def scan_hydra_defaults(yaml_path: str, workspace: str) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    ws_path = Path(workspace)
    abs_yaml = Path(yaml_path) if os.path.isabs(yaml_path) else ws_path / yaml_path
    if not abs_yaml.is_file():
        return merged

    try:
        content = abs_yaml.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            return merged

        defaults_list = data.get("defaults", [])
        if isinstance(defaults_list, list):
            for item in defaults_list:
                ref_sub = None
                if isinstance(item, str) and item != "_self_":
                    ref_sub = item
                elif isinstance(item, dict):
                    for group_name, sub_name in item.items():
                        if group_name != "_self_" and isinstance(sub_name, str):
                            ref_sub = f"{group_name}/{sub_name}"
                
                if ref_sub:
                    cand_paths = [
                        abs_yaml.parent / f"{ref_sub}.yaml",
                        abs_yaml.parent / f"{ref_sub}.yml",
                        ws_path / "configs" / f"{ref_sub}.yaml",
                        ws_path / "config" / f"{ref_sub}.yaml",
                        ws_path / f"{ref_sub}.yaml"
                    ]
                    for cp in cand_paths:
                        if cp.is_file():
                            try:
                                sub_data = yaml.safe_load(cp.read_text(encoding="utf-8"))
                                if isinstance(sub_data, dict):
                                    merged.update(sub_data)
                            except Exception:
                                pass
                            break

        for k, v in data.items():
            if k != "defaults":
                merged[k] = v

    except Exception:
        pass

    return merged

def extract_cli_overrides(command: str) -> Dict[str, Dict[str, Any]]:
    overrides: Dict[str, Dict[str, Any]] = {}
    if not command:
        return overrides

    tokens = command.split()
    idx = 0
    while idx < len(tokens):
        tok = tokens[idx]
        if tok.startswith("-") and "=" in tok:
            parts = tok.split("=", 1)
            raw_k = parts[0].lstrip("-").replace("-", "_")
            val_str = parts[1]
            val = _parse_val(val_str)
            can_k = get_canonical_key(raw_k)
            overrides[can_k] = {
                "value": val,
                "raw_key": raw_k,
                "source_file": "command",
                "source_line": None,
                "source_type": "cli_override"
            }
        elif tok.startswith("-") and not tok.startswith("--help"):
            raw_k = tok.lstrip("-").replace("-", "_")
            if idx + 1 < len(tokens) and not tokens[idx + 1].startswith("-"):
                val_str = tokens[idx + 1]
                val = _parse_val(val_str)
                can_k = get_canonical_key(raw_k)
                overrides[can_k] = {
                    "value": val,
                    "raw_key": raw_k,
                    "source_file": "command",
                    "source_line": None,
                    "source_type": "cli_override"
                }
                idx += 1
        elif "=" in tok and not tok.startswith("-"):
            parts = tok.split("=", 1)
            raw_k = parts[0].replace("-", "_")
            val_str = parts[1]
            val = _parse_val(val_str)
            can_k = get_canonical_key(raw_k)
            overrides[can_k] = {
                "value": val,
                "raw_key": raw_k,
                "source_file": "command",
                "source_line": None,
                "source_type": "cli_override"
            }
        idx += 1

    return overrides

def _parse_val(val_str: str) -> Any:
    val_strip = str(val_str).strip().strip("'\"")
    if val_strip.lower() == "true":
        return True
    if val_strip.lower() == "false":
        return False
    try:
        if "." in val_strip or "e" in val_strip.lower():
            return float(val_strip)
        return int(val_strip)
    except Exception:
        return val_strip

def extract_readme_config_snippets(workspace: str) -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    ws_path = Path(workspace)
    for readme_name in ("README.md", "readme.md", "README.rst"):
        rm_path = ws_path / readme_name
        if rm_path.is_file():
            text = rm_path.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"--([\w-]+)\s+([\w\.\d]+)", text):
                raw_k = m.group(1).replace("-", "_")
                val = _parse_val(m.group(2))
                results[get_canonical_key(raw_k)] = val
            for m in re.finditer(r"(?m)^\s*([\w_]+)\s*:\s*([^\n#]+)", text):
                raw_k = m.group(1).replace("-", "_")
                val = _parse_val(m.group(2))
                results[get_canonical_key(raw_k)] = val
            break
    return results

def audit(workspace: str, plan: Any, paper_settings: List[Any]) -> List[Dict[str, Any]]:
    config_diffs: List[Dict[str, Any]] = []
    ws_path = Path(workspace)

    effective_config: Dict[str, Dict[str, Any]] = {}
    has_runtime_effective = False

    eff_file = getattr(plan, "effective_config_file", None)
    if eff_file and (ws_path / eff_file).is_file():
        try:
            with open(ws_path / eff_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                if isinstance(raw_data, dict):
                    has_runtime_effective = True
                    for k, v in raw_data.items():
                        can_k = get_canonical_key(k)
                        effective_config[can_k] = {
                            "value": v,
                            "raw_key": k,
                            "source_file": eff_file,
                            "source_line": None,
                            "source_type": "runtime_effective"
                        }
        except Exception:
            pass

    cfg_file = getattr(plan, "config_file", None)
    if cfg_file and (ws_path / cfg_file).is_file():
        hydra_data = scan_hydra_defaults(cfg_file, workspace)
        for k, v in hydra_data.items():
            can_k = get_canonical_key(k)
            if can_k not in effective_config:
                effective_config[can_k] = {
                    "value": v,
                    "raw_key": k,
                    "source_file": cfg_file,
                    "source_line": None,
                    "source_type": "config_file"
                }

    if not effective_config:
        for cand_dir in [ws_path / "configs", ws_path / "config", ws_path]:
            if cand_dir.is_dir():
                for yf in list(cand_dir.glob("*.yaml")) + list(cand_dir.glob("*.yml")) + list(cand_dir.glob("*.json")):
                    rel_f = str(yf.relative_to(ws_path))
                    sub_cfg = scan_hydra_defaults(str(yf), workspace)
                    for k, v in sub_cfg.items():
                        can_k = get_canonical_key(k)
                        if can_k not in effective_config:
                            effective_config[can_k] = {
                                "value": v,
                                "raw_key": k,
                                "source_file": rel_f,
                                "source_line": None,
                                "source_type": "config_file"
                            }

    argparse_data = scan_argparse_defaults(workspace)
    for can_k, info in argparse_data.items():
        if can_k not in effective_config:
            effective_config[can_k] = info

    dataclass_data = scan_dataclass_defaults(workspace)
    for can_k, info in dataclass_data.items():
        if can_k not in effective_config:
            effective_config[can_k] = info

    cmd_str = getattr(plan, "command", "") or ""
    cli_overrides = extract_cli_overrides(cmd_str)
    for can_k, info in cli_overrides.items():
        effective_config[can_k] = info

    readme_data = extract_readme_config_snippets(workspace)
    confidence_level = "runtime" if has_runtime_effective else "static"

    for ps in paper_settings:
        ps_key = getattr(ps, "key", "")
        can_key = get_canonical_key(ps_key)
        ps_val = getattr(ps, "value", None)
        readme_val = readme_data.get(can_key)

        if can_key not in effective_config:
            config_diffs.append({
                "key": ps_key,
                "paper_value": ps_val,
                "effective_value": None,
                "source_file": None,
                "source_line": None,
                "source_type": None,
                "status": "not_found",
                "confidence": confidence_level,
                "readme_value": readme_val
            })
            continue

        eff_info = effective_config[can_key]
        eff_val = eff_info["value"]

        match = False
        try:
            if isinstance(ps_val, (int, float)) and isinstance(eff_val, (int, float)):
                match = abs(float(ps_val) - float(eff_val)) < 1e-9
            else:
                match = str(ps_val).strip().lower() == str(eff_val).strip().lower()
        except Exception:
            match = str(ps_val) == str(eff_val)

        config_diffs.append({
            "key": ps_key,
            "paper_value": ps_val,
            "effective_value": eff_val,
            "source_file": eff_info.get("source_file"),
            "source_line": eff_info.get("source_line"),
            "source_type": eff_info.get("source_type"),
            "status": "match" if match else "mismatch",
            "confidence": confidence_level,
            "readme_value": readme_val
        })

    return config_diffs
