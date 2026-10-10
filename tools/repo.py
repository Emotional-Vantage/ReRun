import os
import re
from pathlib import Path
from typing import Dict, Any, List

from tools.triage import triage_report

def inspect_repository(workspace: str) -> Dict[str, Any]:
    ws = Path(workspace)
    tree = []
    readme_commands = []
    dependency_files = []
    config_files = []
    entry_points = []
    network_hints = []
    has_smoke_test = (ws / "tests" / "smoke.py").exists()

    # Run deterministic AST triage report
    triage = triage_report(workspace)

    for p in ws.rglob("*"):
        if p.is_file():
            rel = str(p.relative_to(ws)).replace("\\", "/")
            if any(ign in rel for ign in [".git/", "__pycache__/", ".pytest_cache/", ".site/"]):
                continue
            tree.append(rel)
            
            # Dependency files
            if "requirements" in rel and rel.endswith(".txt"):
                dependency_files.append(rel)
                
            # Config files
            if "config" in rel or rel.endswith((".yaml", ".yml", ".json", ".toml")):
                config_files.append(rel)
                
            # Scan text files for hints
            if rel.endswith((".py", ".md", ".txt", ".yaml", ".yml")):
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                    
                if rel.endswith(".py"):
                    if 'if __name__ == "__main__":' in text or "if __name__ == '__main__':" in text:
                        entry_points.append(rel)
                        
                    # Network hints
                    net_matches = re.finditer(r"(?i)(requests\.(get|post)|urllib|download=True|https?://)", text)
                    for m in net_matches:
                        network_hints.append({"file": rel, "text": m.group(0)})

    # README commands
    from tools.commands import extract_readme_commands
    for readme_candidate in [ws / "README.md", ws / "readme.md", ws / "README.rst", ws / "README.txt", ws / "Readme.md"]:
        if readme_candidate.exists():
            try:
                readme_text = readme_candidate.read_text(encoding="utf-8", errors="ignore")
                for cmd in extract_readme_commands(readme_text):
                    if cmd not in readme_commands:
                        readme_commands.append(cmd)
            except Exception:
                pass

    gpu_hints = []
    for u in triage.get("gpu", {}).get("unguarded", []):
        gpu_hints.append({"file": u["file"], "text": u["text"], "guarded": False})
    for cp in triage.get("gpu", {}).get("cuda_packages", []):
        gpu_hints.append({"file": "requirements.txt", "text": f"CUDA package: {cp}", "guarded": False})

    data_refs = triage.get("missing_data_refs", [])

    return {
        "tree": tree,
        "readme_commands": readme_commands,
        "dependency_files": dependency_files,
        "config_files": config_files,
        "entry_points": entry_points,
        "hints": {
            "gpu": gpu_hints,
            "network": network_hints,
            "data_refs": data_refs
        },
        "python_requires": triage.get("python_requires"),
        "has_smoke_test": has_smoke_test,
        "triage": triage
    }
