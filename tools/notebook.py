import os
import json
import re
from typing import Optional, Dict, Any, List

def is_notebook(file_path: str) -> bool:
    """Checks whether a given file path is a Jupyter notebook."""
    return bool(file_path and file_path.lower().endswith(".ipynb"))

def convert_notebook_to_script(
    notebook_path: str,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Deterministically converts .ipynb code cells to a clean Python script.
    - Comments out IPython magics (%, !, ?, get_ipython())
    - Preserves execution order across code cells
    - Returns UNSUPPORTED_FORMAT for malformed or non-notebook files
    """
    if not os.path.exists(notebook_path):
        return {
            "success": False,
            "error": "UNSUPPORTED_FORMAT",
            "reason": f"File does not exist: {notebook_path}",
            "script": ""
        }

    try:
        with open(notebook_path, "r", encoding="utf-8") as f:
            nb_data = json.load(f)
    except Exception as e:
        return {
            "success": False,
            "error": "UNSUPPORTED_FORMAT",
            "reason": f"Invalid JSON structure in notebook: {e}",
            "script": ""
        }

    if not isinstance(nb_data, dict) or "cells" not in nb_data or not isinstance(nb_data["cells"], list):
        return {
            "success": False,
            "error": "UNSUPPORTED_FORMAT",
            "reason": "Notebook missing valid 'cells' list",
            "script": ""
        }

    script_blocks: List[str] = []
    code_cell_count = 0
    magics_commented = 0

    for idx, cell in enumerate(nb_data["cells"]):
        if not isinstance(cell, dict):
            continue
        if cell.get("cell_type") != "code":
            continue

        code_cell_count += 1
        raw_source = cell.get("source", [])
        if isinstance(raw_source, str):
            source_lines = raw_source.splitlines(keepends=True)
        elif isinstance(raw_source, list):
            source_lines = raw_source
        else:
            continue

        cell_lines: List[str] = [f"# %% [Cell {code_cell_count}]"]
        for line in source_lines:
            stripped = line.lstrip()
            if stripped.startswith(("%", "!", "?", "??")):
                indent = line[:len(line) - len(stripped)]
                commented_line = f"{indent}# [Jupyter Magic Commented]: {stripped}"
                cell_lines.append(commented_line.rstrip("\r\n"))
                magics_commented += 1
            elif "get_ipython()" in line:
                indent = line[:len(line) - len(stripped)]
                commented_line = f"{indent}# [Jupyter get_ipython() Commented]: {stripped}"
                cell_lines.append(commented_line.rstrip("\r\n"))
                magics_commented += 1
            else:
                cell_lines.append(line.rstrip("\r\n"))

        script_blocks.append("\n".join(cell_lines))

    script_content = "\n\n".join(script_blocks) + "\n"

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(script_content)

    return {
        "success": True,
        "error": None,
        "script": script_content,
        "output_path": output_path,
        "code_cell_count": code_cell_count,
        "magics_commented_count": magics_commented
    }
