import os
import re
import shlex
from pathlib import Path
from typing import Dict, Any, List, Optional

FORBIDDEN_SHELL_PATTERNS = [
    (r"\|\|", "command chaining (||) is not permitted"),
    (r"\|", "pipes (|) are not permitted; execute commands directly as argv"),
    (r">>", "output redirection (>>) is not permitted"),
    (r">", "output redirection (>) is not permitted"),
    (r"<", "input redirection (<) is not permitted"),
    (r";", "command chaining (;) is not permitted"),
    (r"&&", "command chaining (&&) is not permitted"),
    (r"\$\(", "command substitution $() is not permitted"),
    (r"`", "backtick command substitution is not permitted"),
    (r"&", "background operator (&) is not permitted"),
    (r"[\r\n]", "multiline commands are not permitted")
]

UNSUPPORTED_COMMANDS = {
    "make": "Unsupported command runner 'make'. Only python and bash scripts are currently supported.",
    "torchrun": "Unsupported distributed command runner 'torchrun'. Multi-GPU distributed runners are not supported.",
    "deepspeed": "Unsupported distributed command runner 'deepspeed'. Distributed training runners are not supported.",
    "accelerate": "Unsupported distributed command runner 'accelerate'.",
    "jupyter": "Unsupported command 'jupyter'. Notebook execution is not supported directly.",
    "pytest": "Unsupported command 'pytest'. Test runners are not execution entry points for paper claims."
}

def validate_command(cmd_str: str, workspace: Optional[str] = None) -> Dict[str, Any]:
    """
    Validates execution commands for security and compliance (R4).
    Enforces that commands execute strictly as argv lists, never sh -c.
    Rejects pipes, redirects, chaining, substitutions, and unsupported runners.
    """
    if not cmd_str or not cmd_str.strip():
        return {
            "valid": False,
            "reason": "Command string cannot be empty",
            "argv": [],
            "command": ""
        }

    clean_cmd = cmd_str.strip()

    # 1. Check forbidden shell injection tokens
    for pat, desc in FORBIDDEN_SHELL_PATTERNS:
        if re.search(pat, clean_cmd):
            return {
                "valid": False,
                "reason": f"Command contains forbidden shell operator: {desc}",
                "argv": [],
                "command": clean_cmd
            }

    # 2. Tokenize with shlex
    try:
        argv = shlex.split(clean_cmd)
    except Exception as e:
        return {
            "valid": False,
            "reason": f"Failed to parse command arguments: {e}",
            "argv": [],
            "command": clean_cmd
        }

    if not argv:
        return {
            "valid": False,
            "reason": "Command has no arguments",
            "argv": [],
            "command": clean_cmd
        }

    binary = argv[0].lower()

    # 3. Check explicitly unsupported commands
    if binary in UNSUPPORTED_COMMANDS:
        return {
            "valid": False,
            "reason": UNSUPPORTED_COMMANDS[binary],
            "argv": argv,
            "command": clean_cmd
        }

    # 4. Validate allowed runners (python / python3 / bash / sh)
    if binary in ("python", "python3"):
        if len(argv) < 2:
            return {
                "valid": False,
                "reason": "Python command must specify a script file or module (-m)",
                "argv": argv,
                "command": clean_cmd
            }

        if argv[1] == "-m":
            if len(argv) < 3:
                return {
                    "valid": False,
                    "reason": "python -m requires a module name",
                    "argv": argv,
                    "command": clean_cmd
                }
            return {
                "valid": True,
                "reason": "Valid python -m module invocation",
                "argv": argv,
                "command": clean_cmd
            }
        elif argv[1].startswith("-"):
            # Command flags e.g. python -u script.py
            script_idx = None
            for i, arg in enumerate(argv[1:], start=1):
                if not arg.startswith("-"):
                    script_idx = i
                    break
            if script_idx and workspace and Path(workspace).is_dir():
                script_path = Path(workspace) / argv[script_idx]
                if not script_path.exists():
                    return {
                        "valid": False,
                        "reason": f"Target script '{argv[script_idx]}' not found in workspace",
                        "argv": argv,
                        "command": clean_cmd
                    }
            return {
                "valid": True,
                "reason": "Valid python script invocation with flags",
                "argv": argv,
                "command": clean_cmd
            }
        else:
            script_name = argv[1]
            if workspace and Path(workspace).is_dir():
                ws_path = Path(workspace)
                script_path = ws_path / script_name
                if not script_path.exists():
                    return {
                        "valid": False,
                        "reason": f"Target script '{script_name}' not found in workspace",
                        "argv": argv,
                        "command": clean_cmd
                    }
            return {
                "valid": True,
                "reason": "Valid python script invocation",
                "argv": argv,
                "command": clean_cmd
            }

    elif binary in ("bash", "sh"):
        if len(argv) < 2:
            return {
                "valid": False,
                "reason": f"{binary} command must specify a script file",
                "argv": argv,
                "command": clean_cmd
            }
        if "-c" in argv:
            return {
                "valid": False,
                "reason": f"Execution via '{binary} -c' is not permitted; execute commands directly as argv lists",
                "argv": argv,
                "command": clean_cmd
            }
        script_name = argv[1]
        if workspace and Path(workspace).is_dir():
            ws_path = Path(workspace)
            script_path = ws_path / script_name
            if not script_path.exists():
                return {
                    "valid": False,
                    "reason": f"Target shell script '{script_name}' not found in workspace",
                    "argv": argv,
                    "command": clean_cmd
                }
        return {
            "valid": True,
            "reason": f"Valid {binary} script invocation",
            "argv": argv,
            "command": clean_cmd
        }

    else:
        return {
            "valid": False,
            "reason": f"Unsupported runner '{binary}'. Only 'python' and 'bash' scripts are supported.",
            "argv": argv,
            "command": clean_cmd
        }

def extract_readme_commands(readme_text: str) -> List[str]:
    """
    Extracts candidate execution commands from README text.
    Handles `$ ` prompts, bash scripts, python -m, and code fences.
    """
    commands = []
    seen = set()

    # Extract code blocks
    code_block_pats = [
        r"```(?:bash|sh|shell|python)?\s*\n(.*?)\n```",
        r"~~~(?:bash|sh|shell|python)?\s*\n(.*?)\n~~~"
    ]
    code_snippets = []
    for pat in code_block_pats:
        for m in re.finditer(pat, readme_text, re.DOTALL):
            code_snippets.append(m.group(1))

    # Inline code spans
    inline_spans = re.findall(r"`([^`\n]{3,300})`", readme_text)

    # Examine all lines
    all_lines = list(readme_text.splitlines())
    for block in code_snippets:
        all_lines.extend(block.splitlines())
    all_lines.extend(inline_spans)

    for line in all_lines:
        sline = line.strip()
        # Strip shell prompt characters
        sline = re.sub(r"^[\$\#\>]\s*", "", sline).strip()
        if not sline or sline.startswith("#"):
            continue

        if sline.startswith(("python ", "python3 ", "bash ", "sh ", "make ", "torchrun ")):
            norm = " ".join(sline.split())
            if norm not in seen:
                seen.add(norm)
                commands.append(norm)

    return commands
