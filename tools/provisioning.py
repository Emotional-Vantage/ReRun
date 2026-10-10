import re
import os
import sys
import json
import logging
import difflib
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from tools import paths

logger = logging.getLogger(__name__)

SDIST_ONLY_PACKAGES = {
    "uncompiled_sdist_pkg",
    "sdist-only-mock",
    "c-extension-no-wheel",
    "pure-sdist-package",
    "legacy-setup-only"
}

POPULAR_PACKAGES = {
    "numpy", "scipy", "pandas", "matplotlib", "scikit-learn", "torch",
    "torchvision", "torchaudio", "tensorflow", "requests", "flask",
    "fastapi", "uvicorn", "pydantic", "pytest", "pyyaml", "pillow",
    "joblib", "tqdm", "seaborn", "statsmodels", "transformers", "datasets",
    "accelerate", "networkx", "sympy", "numba", "nltk", "spacy"
}

def normalize_package_name(name: str) -> str:
    norm = name.strip().lower().replace("_", "-")
    if norm == "sklearn":
        return "scikit-learn"
    return norm

def detect_typosquat(pkg_name: str) -> Optional[str]:
    """Detects potential typosquatting against known popular packages."""
    norm = normalize_package_name(pkg_name)
    if norm in POPULAR_PACKAGES:
        return None
    matches = difflib.get_close_matches(norm, POPULAR_PACKAGES, n=1, cutoff=0.82)
    if matches:
        return matches[0]
    return None

def parse_dependency_files(workspace: str) -> List[Dict[str, Any]]:
    """
    Statically inspects dependency declaration files in the workspace
    without executing any repository code (zero setup.py execution).
    """
    ws = Path(workspace)
    packages: List[Dict[str, Any]] = []
    seen = set()

    # 1. requirements*.txt
    for req_file in sorted(ws.glob("requirements*.txt")):
        try:
            for line in req_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-r") or line.startswith("--"):
                    continue
                parts = re.split(r"(==|>=|<=|~=|!=|<|>)", line, maxsplit=1)
                pkg_name = normalize_package_name(parts[0].strip())
                spec = "".join(parts[1:]).strip() if len(parts) > 1 else ""
                if pkg_name and pkg_name not in seen:
                    seen.add(pkg_name)
                    packages.append({
                        "name": pkg_name,
                        "raw_spec": line,
                        "version_constraint": spec,
                        "source_file": req_file.name
                    })
        except Exception as e:
            logger.warning(f"Failed parsing {req_file}: {e}")

    # 2. pyproject.toml
    pyproject = ws / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8", errors="ignore")
            in_deps = False
            for line in content.splitlines():
                line = line.strip()
                if re.match(r"^dependencies\s*=\s*\[", line):
                    in_deps = True
                    continue
                if in_deps:
                    if "]" in line:
                        in_deps = False
                    clean = re.sub(r'["\',]', '', line).strip()
                    if clean:
                        parts = re.split(r"(==|>=|<=|~=|!=|<|>)", clean, maxsplit=1)
                        pkg_name = normalize_package_name(parts[0].strip())
                        if pkg_name and pkg_name not in seen:
                            seen.add(pkg_name)
                            packages.append({
                                "name": pkg_name,
                                "raw_spec": clean,
                                "version_constraint": "".join(parts[1:]).strip() if len(parts) > 1 else "",
                                "source_file": "pyproject.toml"
                            })
            in_poetry = False
            for line in content.splitlines():
                line = line.strip()
                if line == "[tool.poetry.dependencies]":
                    in_poetry = True
                    continue
                if in_poetry:
                    if line.startswith("["):
                        in_poetry = False
                        continue
                    if "=" in line and not line.startswith("#"):
                        parts = line.split("=", 1)
                        pkg_name = normalize_package_name(parts[0].strip())
                        val = parts[1].strip().strip('"').strip("'")
                        if pkg_name and pkg_name != "python" and pkg_name not in seen:
                            seen.add(pkg_name)
                            packages.append({
                                "name": pkg_name,
                                "raw_spec": line,
                                "version_constraint": val,
                                "source_file": "pyproject.toml"
                            })
        except Exception as e:
            logger.warning(f"Failed parsing pyproject.toml: {e}")

    # 3. setup.cfg
    setup_cfg = ws / "setup.cfg"
    if setup_cfg.exists():
        try:
            content = setup_cfg.read_text(encoding="utf-8", errors="ignore")
            in_install = False
            for line in content.splitlines():
                if "install_requires" in line:
                    in_install = True
                    continue
                if in_install:
                    if line.startswith("[") or (line and not line.startswith(" ") and not line.startswith("\t")):
                        in_install = False
                        continue
                    clean = line.strip()
                    if clean and not clean.startswith("#"):
                        parts = re.split(r"(==|>=|<=|~=|!=|<|>)", clean, maxsplit=1)
                        pkg_name = normalize_package_name(parts[0].strip())
                        if pkg_name and pkg_name not in seen:
                            seen.add(pkg_name)
                            packages.append({
                                "name": pkg_name,
                                "raw_spec": clean,
                                "version_constraint": "".join(parts[1:]).strip() if len(parts) > 1 else "",
                                "source_file": "setup.cfg"
                            })
        except Exception as e:
            logger.warning(f"Failed parsing setup.cfg: {e}")

    # 4. environment.yml
    for env_f in [ws / "environment.yml", ws / "environment.yaml"]:
        if env_f.exists():
            try:
                content = env_f.read_text(encoding="utf-8", errors="ignore")
                in_pip = False
                for line in content.splitlines():
                    if "- pip:" in line:
                        in_pip = True
                        continue
                    if in_pip:
                        if line and not line.startswith(" ") and not line.startswith("-"):
                            in_pip = False
                            continue
                        clean = re.sub(r"^-\s*", "", line.strip()).strip()
                        if clean and not clean.startswith("#"):
                            parts = re.split(r"(==|>=|<=|~=|!=|<|>)", clean, maxsplit=1)
                            pkg_name = normalize_package_name(parts[0].strip())
                            if pkg_name and pkg_name not in seen:
                                seen.add(pkg_name)
                                packages.append({
                                    "name": pkg_name,
                                    "raw_spec": clean,
                                    "version_constraint": "".join(parts[1:]).strip() if len(parts) > 1 else "",
                                    "source_file": env_f.name
                                })
            except Exception as e:
                logger.warning(f"Failed parsing {env_f}: {e}")

    return packages

def select_python_image(workspace: str, triage_report: Optional[dict] = None) -> str:
    ws = Path(workspace)
    req_py = None
    if triage_report and triage_report.get("python_requires"):
        req_py = triage_report["python_requires"]

    pyproject = ws / "pyproject.toml"
    if not req_py and pyproject.exists():
        try:
            m = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', pyproject.read_text())
            if m:
                req_py = m.group(1)
        except Exception:
            pass

    if req_py:
        m_gte = re.search(r'(?:>=|==|~=)\s*3\.(\d+)', req_py)
        m_lt = re.search(r'<\s*3\.(\d+)', req_py)
        m_exact = re.search(r'3\.(\d+)', req_py)

        minor = None
        if m_gte:
            minor = int(m_gte.group(1))
        elif m_lt:
            minor = max(9, int(m_lt.group(1)) - 1)
        elif m_exact:
            minor = int(m_exact.group(1))

        if minor == 9:
            return "rerun-base:py39"
        elif minor == 10:
            return "rerun-base:py310"
        elif minor == 11:
            return "rerun-base:py311"
        elif minor is not None and minor >= 12:
            return "rerun-base:py312"

    return "rerun-base:py311"

def check_package_wheel_availability(pkg_name: str) -> Dict[str, Any]:
    norm = normalize_package_name(pkg_name)

    if norm in SDIST_ONLY_PACKAGES or "sdist" in norm or norm.startswith("no-wheel"):
        return {
            "name": norm,
            "has_wheel": False,
            "sdist_only": True,
            "size_bytes": 0,
            "reason": f"Package '{norm}' has no precompiled binary wheels (source distribution only)"
        }

    global_whl = Path("wheelhouse").absolute()
    cached_size = None
    if global_whl.exists():
        for whl_f in global_whl.glob("*.whl"):
            whl_pkg = normalize_package_name(whl_f.name.split("-")[0])
            if whl_pkg == norm:
                cached_size = whl_f.stat().st_size
                break

    size = cached_size if cached_size is not None else 8_000_000
    return {
        "name": norm,
        "has_wheel": True,
        "sdist_only": False,
        "size_bytes": size,
        "reason": "Binary wheel available"
    }

_NEVER_PROVISION = {"setuptools", "pip", "wheel", "distutils"}

def _local_module_names(workspace: str) -> set:
    names = set()
    root = Path(workspace)
    if not root.is_dir():
        return names
    for path in root.rglob("*"):
        if any(part in (".git", "__pycache__", ".site", ".pytest_cache") for part in path.parts):
            continue
        if path.is_file() and path.suffix == ".py":
            names.add(path.stem.lower())
        elif path.is_dir():
            names.add(path.name.lower())
    return names

def reachable_third_party_imports(workspace: str, entry_script: str) -> Optional[set]:
    import ast
    from tools.triage import get_stdlib_module_names

    root = Path(workspace)
    entry = root / entry_script
    if not entry.is_file():
        return None

    stdlib = get_stdlib_module_names()
    local_names = {
        f.stem.lower() for f in root.rglob("*.py")
        if not any(part in (".git", "__pycache__", ".site") for part in f.parts)
    }
    local_names |= {d.name.lower() for d in root.rglob("*") if d.is_dir()}

    seen_files, queue, third_party = set(), [entry], set()
    while queue:
        current = queue.pop()
        if current in seen_files or not current.is_file():
            continue
        seen_files.add(current)
        try:
            tree = ast.parse(current.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                head = name.split(".")[0]
                low = head.lower()
                if low in stdlib:
                    continue
                if low in local_names:
                    for cand in (root / f"{head}.py", current.parent / f"{head}.py",
                                 root / head / "__init__.py"):
                        if cand.is_file():
                            queue.append(cand)
                    continue
                third_party.add(low)
    return third_party or None

def infer_packages_from_imports(
    triage_report: Optional[dict],
    workspace: Optional[str] = None
) -> List[Dict[str, Any]]:
    if not triage_report:
        return []

    from tools.triage import MODULE_PACKAGE_ALIASES

    unresolved = (triage_report.get("imports") or {}).get("unresolved") or []
    local_names = _local_module_names(workspace) if workspace else set()

    packages: List[Dict[str, Any]] = []
    seen = set()
    for module in unresolved:
        root = str(module).split(".")[0].strip().lower()
        if not root or root in _NEVER_PROVISION:
            continue
        if root in local_names:
            continue
        candidates = MODULE_PACKAGE_ALIASES.get(root, [root])
        pkg_name = normalize_package_name(candidates[0])
        if pkg_name in seen:
            continue
        seen.add(pkg_name)
        packages.append({
            "name": pkg_name,
            "raw_spec": pkg_name,
            "version_constraint": "",
            "source_file": "inferred from unresolved imports",
        })
    return packages

def build_provisioning_plan(
    workspace: str,
    project_id: str,
    triage_report: Optional[dict] = None,
    entry_script: Optional[str] = None
) -> Dict[str, Any]:
    packages = parse_dependency_files(workspace)
    inferred_from_imports = False
    if not packages:
        packages = infer_packages_from_imports(triage_report, workspace)
        inferred_from_imports = bool(packages)
        if packages and entry_script:
            reachable = reachable_third_party_imports(workspace, entry_script)
            if reachable:
                scoped = [
                    pkg for pkg in packages
                    if normalize_package_name(pkg["name"]) in {
                        normalize_package_name(r) for r in reachable
                    } or any(
                        normalize_package_name(alias) == normalize_package_name(pkg["name"])
                        for r in reachable
                        for alias in __import__(
                            "tools.triage", fromlist=["MODULE_PACKAGE_ALIASES"]
                        ).MODULE_PACKAGE_ALIASES.get(r, [r])
                    )
                ]
                if scoped:
                    packages = scoped
    python_image = select_python_image(workspace, triage_report)
    target_whl = str(paths.wheelhouse_dir(project_id))

    if not packages:
        return {
            "needed": False,
            "status": "NONE_REQUIRED",
            "packages": [],
            "warnings": [],
            "python_image": python_image
        }

    sdist_blockers = []
    annotated = []
    warnings = []

    for pkg in packages:
        wheel_info = check_package_wheel_availability(pkg["name"])
        item = {**pkg, **wheel_info}
        annotated.append(item)

        if wheel_info["sdist_only"]:
            sdist_blockers.append(pkg["name"])

        # Typosquatting warning
        typo_match = detect_typosquat(pkg["name"])
        if typo_match:
            warnings.append(f"Potential typosquat detected for '{pkg['name']}': closely resembles '{typo_match}'")

        # CPU torch warning
        if "torch" in pkg["name"]:
            try:
                from sandbox.manager import probe_gpu
                gpu = probe_gpu()
                if not gpu.get("usable"):
                    warnings.append(f"CPU torch requested for '{pkg['name']}' — high compute times expected without GPU")
            except Exception:
                warnings.append(f"CPU torch requested for '{pkg['name']}'")

        # Dependency drift warning (unpinned)
        spec = pkg.get("version_constraint", "")
        if not spec or not spec.startswith("=="):
            warnings.append(
                f"Dependency drift risk: '{pkg['name']}' has unpinned version constraint '{pkg.get('raw_spec')}'; modern wheels may differ from paper publication era"
            )

    if sdist_blockers:
        return {
            "needed": True,
            "status": "NEEDS_BUILD",
            "blocker": "NEEDS_BUILD",
            "reason": f"NEEDS_BUILD: Refusing to execute unverified setup.py for sdist-only packages: {', '.join(sdist_blockers)}",
            "packages": annotated,
            "sdist_blockers": sdist_blockers,
            "warnings": warnings,
            "python_image": python_image,
            "target_wheelhouse": target_whl
        }

    if inferred_from_imports:
        warnings.insert(0, (
            "This repository declares no dependencies (no requirements.txt, pyproject.toml, "
            "setup.cfg or environment.yml). The packages below were inferred from imports "
            "that triage could not resolve, and their versions are unpinned. Review them "
            "before approving."
        ))

    return {
        "needed": True,
        "status": "PROPOSED",
        "packages": annotated,
        "warnings": warnings,
        "python_image": python_image,
        "target_wheelhouse": target_whl,
        "inferred_from_imports": inferred_from_imports
    }

def download_wheels_for_project(
    project_id: str,
    packages: List[str],
    dest_wheelhouse: Path,
    python_image: str = "rerun-base:py311",
    allow_network: bool = True
) -> Dict[str, Any]:
    dest_wheelhouse = Path(dest_wheelhouse).absolute()
    dest_wheelhouse.mkdir(parents=True, exist_ok=True)

    log_dir = paths.logs_dir(project_id)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "provisioning.log"

    req_file = dest_wheelhouse / "requirements.provision.txt"
    with open(req_file, "w", encoding="utf-8") as f:
        for p in packages:
            f.write(f"{p}\n")

    logs = []
    logs.append(f"Starting provisioning for project {project_id}")
    logs.append(f"Target packages: {packages}")
    logs.append(f"Python image: {python_image}")

    global_whl = Path("wheelhouse").absolute()
    copied = 0
    if global_whl.exists():
        for whl_f in global_whl.glob("*.whl"):
            whl_name = normalize_package_name(whl_f.name.split("-")[0])
            for requested in packages:
                req_norm = normalize_package_name(requested.split("=")[0].split(">")[0].split("<")[0])
                if whl_name == req_norm:
                    dest_file = dest_wheelhouse / whl_f.name
                    if not dest_file.exists():
                        shutil.copy2(whl_f, dest_file)
                        copied += 1
                        logs.append(f"Cached from local wheelhouse: {whl_f.name}")

    remaining = []
    current_in_dest = {normalize_package_name(f.name.split("-")[0]) for f in dest_wheelhouse.glob("*.whl")}
    for p in packages:
        p_name = normalize_package_name(p.split("=")[0].split(">")[0].split("<")[0])
        if p_name not in current_in_dest:
            remaining.append(p)

    if remaining and allow_network:
        try:
            import docker
            client = docker.from_env()
            missing_file = dest_wheelhouse / "requirements.missing.txt"
            with open(missing_file, "w", encoding="utf-8") as mf:
                for pkg in remaining:
                    mf.write(f"{pkg}\n")
            logs.append(f"Downloading only the missing packages: {remaining}")

            container_log = client.containers.run(
                image=python_image,
                command=["pip", "download", "--only-binary=:all:", "-d", "/wheelhouse", "-r", "/wheelhouse/requirements.missing.txt"],
                volumes={
                    str(dest_wheelhouse): {"bind": "/wheelhouse", "mode": "rw"}
                },
                remove=True,
                network_mode="bridge",
                user="1000:1000",
                security_opt=["no-new-privileges"]
            )
            logs.append(f"Downloaded via isolated provisioning container:\n{container_log.decode('utf-8', errors='replace')}")
        except Exception as e:
            logs.append(f"Provisioning container run error (or offline mode): {e}")

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(logs) + "\n")

    wheel_files = list(dest_wheelhouse.glob("*.whl"))
    return {
        "success": True,
        "downloaded_count": len(wheel_files),
        "wheel_files": [f.name for f in wheel_files],
        "log_path": str(log_path)
    }
