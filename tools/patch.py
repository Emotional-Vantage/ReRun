import difflib
import subprocess
import os
import ast
import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional

from agent.state import Edit, PatchProposal, ProjectState
from .policy import compute_fix_signature

def apply_edits_in_memory(workspace: str, edits: List[Edit]) -> Dict[str, str]:
    """Applies a list of edits in-memory to current file contents, returning new text per file."""
    ws = Path(workspace)
    new_contents = {}
    
    # Group edits by file
    files_to_edit = {}
    for edit in edits:
        files_to_edit.setdefault(edit.file, []).append(edit)
        
    for rel_path, file_edits in files_to_edit.items():
        file_path = ws / rel_path
        if file_path.exists():
            text = file_path.read_text(encoding="utf-8")
        else:
            text = ""
            
        for edit in file_edits:
            if edit.op == "replace_text":
                if edit.old is None:
                    raise ValueError(f"replace_text requires 'old' string for {rel_path}")
                count = text.count(edit.old)
                if count != 1:
                    raise ValueError(f"replace_text failed: old text occurs {count} times (must be exactly 1) in {rel_path}")
                text = text.replace(edit.old, edit.new, 1)
                
            elif edit.op == "replace_line":
                if edit.line is None or edit.line < 1:
                    raise ValueError(f"replace_line requires 1-based line number for {rel_path}")
                lines = text.splitlines(keepends=True)
                if edit.line > len(lines):
                    raise ValueError(f"Line {edit.line} out of range in {rel_path} ({len(lines)} lines)")
                new_line = edit.new if edit.new.endswith("\n") else edit.new + "\n"
                lines[edit.line - 1] = new_line
                text = "".join(lines)
                
            elif edit.op == "append_line":
                new_line = edit.new if edit.new.endswith("\n") else edit.new + "\n"
                if text and not text.endswith("\n"):
                    text += "\n"
                text += new_line
                
            else:
                raise ValueError(f"Unknown edit operation: {edit.op}")
                
        new_contents[rel_path] = text
        
    return new_contents

def make_diff(workspace: str, new_texts: Dict[str, str]) -> str:
    """Generates unified diff between current workspace files and modified texts."""
    ws = Path(workspace)
    diff_lines = []
    
    for rel_path, new_text in new_texts.items():
        file_path = ws / rel_path
        if file_path.exists():
            old_lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
        else:
            old_lines = []
            
        new_lines = new_text.splitlines(keepends=True)
        file_diff = list(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}"
        ))
        diff_lines.extend(file_diff)
        
    return "".join(diff_lines)

_PATCH_BACKUPS: Dict[str, Dict[str, Optional[str]]] = {}

def apply_patch(state: ProjectState, patch: PatchProposal, workspace: str, run_smoke: bool = True) -> bool:
    """
    Applies an approved patch to the workspace git working copy.
    Strictly enforces Invariant I8: refuses to apply without an Approval record!
    """
    # Invariant I8 check
    matching_approval = next(
        (a for a in state.approvals if a.patch_id == patch.id and a.decision in ("approve", "edit")),
        None
    )
    if not matching_approval:
        raise PermissionError(f"Invariant I8 Violation: Refusing to apply patch {patch.id} without an explicit human approval record.")

    ws = Path(workspace)
    # 1. Apply edits in-memory first to ensure valid
    try:
        new_texts = apply_edits_in_memory(workspace, patch.edits)
    except Exception:
        return False

    # Back up original files before modifying
    backups: Dict[str, Optional[str]] = {}
    for rel_path in new_texts.keys():
        target = ws / rel_path
        if target.exists():
            backups[rel_path] = target.read_text(encoding="utf-8")
        else:
            backups[rel_path] = None
    _PATCH_BACKUPS[f"{state.project_id}_{patch.id}"] = backups

    # 2. Write files to disk
    for rel_path, new_text in new_texts.items():
        target = ws / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_text, encoding="utf-8")
        
    # 3. Syntax smoke check
    for rel_path, new_text in new_texts.items():
        if rel_path.endswith(".py"):
            try:
                ast.parse(new_text)
            except Exception:
                revert_patch(state, patch, workspace)
                return False
        elif rel_path.endswith(".yaml") or rel_path.endswith(".yml"):
            try:
                yaml.safe_load(new_text)
            except Exception:
                revert_patch(state, patch, workspace)
                return False

    patch.status = "applied"
    return True

def revert_patch(state: ProjectState, patch: PatchProposal, workspace: str) -> bool:
    """Reverts an applied patch and restores original files on disk."""
    ws = Path(workspace)
    patch.status = "reverted"
    sig = patch.fix_signature
    if sig and sig not in state.failed_fixes:
        state.failed_fixes.append(sig)

    # 1. Try git reset/checkout if in a git repository
    if (ws / ".git").exists():
        try:
            subprocess.run(["git", "checkout", "."], cwd=str(ws), capture_output=True, check=False)
            subprocess.run(["git", "clean", "-fd"], cwd=str(ws), capture_output=True, check=False)
        except Exception:
            pass

    # 2. Restore file contents from recorded backups
    key = f"{state.project_id}_{patch.id}"
    backups = _PATCH_BACKUPS.get(key)
    if backups is not None:
        for rel_path, orig_text in backups.items():
            target = ws / rel_path
            if orig_text is None:
                if target.exists():
                    target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(orig_text, encoding="utf-8")
    elif patch.edits:
        for edit in patch.edits:
            target = ws / edit.file
            if target.exists() and edit.op == "replace_text" and edit.old:
                cur = target.read_text(encoding="utf-8")
                if edit.new in cur:
                    target.write_text(cur.replace(edit.new, edit.old, 1), encoding="utf-8")

    return True
