import os
import ast
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple

# Share of a repository's functions that must be empty stubs before an empty body is treated
# as "this repository is unfinished" rather than an ordinary no-op hook. A single
# `def on_epoch_end(self): pass` is idiomatic in research code and must not block execution;
# a repository whose functions are *mostly* empty genuinely cannot reproduce anything.
STUB_RATIO_BLOCK_THRESHOLD = 0.5

# Known CUDA-only packages that cannot execute in CPU-only offline sandboxes
CUDA_ONLY_PACKAGES = {
    "cupy", "apex", "flash-attn", "flash_attn", "bitsandbytes",
    "triton", "deepspeed", "cutlass"
}

# Package alias mapping: pip package name -> imported module name
PACKAGE_IMPORT_ALIASES = {
    "pyyaml": "yaml",
    "scikit-learn": "sklearn",
    "pillow": "pil",
    "opencv-python": "cv2",
    "opencv-python-headless": "cv2",
    "protobuf": "google.protobuf",
    "python-dateutil": "dateutil",
    "attrs": "attr",
    "beautifulsoup4": "bs4",
    "tensorboardx": "tensorboardX",
}

# Inverted alias: imported module name -> common pip package names
MODULE_PACKAGE_ALIASES = {
    "yaml": ["pyyaml"],
    "sklearn": ["scikit-learn"],
    "pil": ["pillow"],
    "cv2": ["opencv-python", "opencv-python-headless"],
    "bs4": ["beautifulsoup4"],
    "dateutil": ["python-dateutil"],
    "attr": ["attrs"],
}

def get_stdlib_module_names() -> Set[str]:
    """Returns the set of standard library module names in Python."""
    if hasattr(sys, "stdlib_module_names"):
        return set(sys.stdlib_module_names)
    # Fallback standard library list for Python 3.10+
    return {
        "abc", "argparse", "array", "ast", "asyncio", "base64", "binascii",
        "bisect", "builtins", "calendar", "cmath", "cmd", "code", "codecs",
        "collections", "colorsys", "compileall", "concurrent", "configparser",
        "contextlib", "contextvars", "copy", "copyreg", "cProfile", "crypt",
        "csv", "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal",
        "difflib", "dis", "distutils", "doctest", "email", "encodings",
        "enum", "errno", "faulthandler", "fcntl", "filecmp", "fileinput",
        "fnmatch", "fractions", "ftplib", "functools", "gc", "getopt",
        "getpass", "gettext", "glob", "graphlib", "gzip", "hashlib", "heapq",
        "hmac", "html", "http", "idlelib", "imaplib", "imghdr", "imp",
        "importlib", "inspect", "io", "ipaddress", "itertools", "json",
        "keyword", "lib2to3", "linecache", "locale", "logging", "lzma",
        "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
        "modulefinder", "multiprocessing", "netrc", "nntplib", "numbers",
        "operator", "optparse", "os", "ossaudiodev", "pathlib", "pdb",
        "pickle", "pickletools", "pipes", "pkgutil", "platform", "plistlib",
        "poplib", "posix", "posixpath", "pprint", "profile", "pstats", "pty",
        "pwd", "py_compile", "pyclbr", "pydoc", "queue", "quopri", "random",
        "re", "readline", "reprlib", "resource", "rlcompleter", "runpy",
        "sched", "secrets", "select", "selectors", "shelve", "shlex", "shutil",
        "signal", "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver",
        "spwd", "sqlite3", "ssl", "stat", "statistics", "string", "stringprep",
        "struct", "subprocess", "sunau", "symtable", "sys", "sysconfig",
        "syslog", "tabnanny", "tarfile", "telnetlib", "tempfile", "termios",
        "textwrap", "threading", "time", "timeit", "tkinter", "token",
        "tokenize", "tomllib", "trace", "traceback", "tracemalloc", "tty",
        "turtle", "turtledemo", "types", "typing", "unicodedata", "unittest",
        "urllib", "uu", "uuid", "venv", "warnings", "wave", "weakref",
        "webbrowser", "wsgiref", "xdrlib", "xml", "xmlrpc", "zipapp",
        "zipfile", "zipimport", "zlib", "_thread"
    }

def parse_declared_dependencies(root: Path) -> Set[str]:
    """Parses declared dependency names from requirements.txt, pyproject.toml, and setup.py/cfg."""
    declared = set()

    # 1. requirements*.txt
    for req_file in root.rglob("requirements*.txt"):
        if any(part in req_file.parts for part in [".git", "__pycache__", ".site"]):
            continue
        try:
            for line in req_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                # Split off version specs (==, >=, <=, ~=, <, >, ;)
                pkg = re.split(r"[><=~;]", line)[0].strip().lower()
                if pkg:
                    declared.add(pkg)
                    if pkg in PACKAGE_IMPORT_ALIASES:
                        declared.add(PACKAGE_IMPORT_ALIASES[pkg])
        except Exception:
            pass

    # 2. pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8", errors="ignore")
            deps_match = re.search(r"dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
            if deps_match:
                for item in re.findall(r"['\"]([^'\"]+)['\"]", deps_match.group(1)):
                    pkg = re.split(r"[><=~;]", item)[0].strip().lower()
                    if pkg:
                        declared.add(pkg)
                        if pkg in PACKAGE_IMPORT_ALIASES:
                            declared.add(PACKAGE_IMPORT_ALIASES[pkg])
        except Exception:
            pass

    # 3. setup.cfg
    setup_cfg = root / "setup.cfg"
    if setup_cfg.exists():
        try:
            content = setup_cfg.read_text(encoding="utf-8", errors="ignore")
            install_reqs = re.search(r"install_requires\s*=(.*?)(?:\n\[|\Z)", content, re.DOTALL)
            if install_reqs:
                for line in install_reqs.group(1).splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        pkg = re.split(r"[><=~;]", line)[0].strip().lower()
                        if pkg:
                            declared.add(pkg)
        except Exception:
            pass

    return declared

def detect_python_version_requirement(root: Path) -> Optional[str]:
    """Extracts declared Python version requirements without hard-coding."""
    # 1. runtime.txt (e.g. python-3.10.12)
    runtime_file = root / "runtime.txt"
    if runtime_file.exists():
        try:
            text = runtime_file.read_text(encoding="utf-8", errors="ignore").strip()
            m = re.search(r"python-?([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text, re.I)
            if m:
                return f">={m.group(1)}"
        except Exception:
            pass

    # 2. setup.py / setup.cfg / pyproject.toml python_requires
    for fname in ["setup.py", "setup.cfg", "pyproject.toml"]:
        p = root / fname
        if p.exists():
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r"python_requires\s*[:=]\s*['\"]([^'\"]+)['\"]", text)
                if m:
                    return m.group(1)
            except Exception:
                pass

    # 3. environment.yml (e.g. - python=3.9)
    env_yml = root / "environment.yml"
    if env_yml.exists():
        try:
            text = env_yml.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"-\s*python\s*([=><~][^#\n]+)", text)
            if m:
                return m.group(1).strip()
        except Exception:
            pass

    # 4. Dockerfile (e.g. FROM python:3.9-slim)
    for dockerfile in [root / "Dockerfile", root / "docker" / "Dockerfile"]:
        if dockerfile.exists():
            try:
                text = dockerfile.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r"FROM\s+python:([0-9]+\.[0-9]+)", text, re.I)
                if m:
                    return f">={m.group(1)}"
            except Exception:
                pass

    return None

class GuardedCUDAVisitor(ast.NodeVisitor):
    """
    Scans Python AST for CUDA usage and distinguishes:
    - unguarded hard-coded CUDA (blocker)
    - guarded device selection (warning)
    """
    def __init__(self, rel_path: str):
        self.rel_path = rel_path
        self.unguarded_cuda: List[Dict[str, Any]] = []
        self.guarded_cuda: List[Dict[str, Any]] = []
        self._guard_depth = 0

    def _is_cuda_guard_test(self, node: ast.AST) -> bool:
        """Checks if a conditional test checks torch.cuda.is_available() or similar."""
        test_str = ast.unparse(node) if hasattr(ast, "unparse") else ""
        return "is_available" in test_str or "cuda" in test_str

    def visit_If(self, node: ast.If):
        is_guard = self._is_cuda_guard_test(node.test)
        if is_guard:
            self._guard_depth += 1
            for b in node.body:
                self.visit(b)
            self._guard_depth -= 1
            for b in node.orelse:
                self.visit(b)
        else:
            self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp):
        is_guard = self._is_cuda_guard_test(node.test)
        if is_guard:
            self._guard_depth += 1
            self.visit(node.body)
            self._guard_depth -= 1
            self.visit(node.orelse)
        else:
            self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        call_str = ast.unparse(node) if hasattr(ast, "unparse") else ""
        # Detect .cuda() calls
        if isinstance(node.func, ast.Attribute) and node.func.attr == "cuda":
            evidence = {
                "file": self.rel_path,
                "line": getattr(node, "lineno", 0),
                "text": ".cuda() call"
            }
            if self._guard_depth > 0 or "is_available" in call_str:
                self.guarded_cuda.append(evidence)
            else:
                self.unguarded_cuda.append(evidence)

        # Detect .to("cuda") or torch.device("cuda")
        elif re.search(r"\b(to|device)\s*\(.*['\"]cuda['\"]", call_str):
            evidence = {
                "file": self.rel_path,
                "line": getattr(node, "lineno", 0),
                "text": call_str[:80]
            }
            if self._guard_depth > 0 or "is_available" in call_str:
                self.guarded_cuda.append(evidence)
            else:
                self.unguarded_cuda.append(evidence)

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        try:
            assign_str = ast.unparse(node) if hasattr(ast, "unparse") else ""
            if "is_available" in assign_str and "cuda" in assign_str:
                self.guarded_cuda.append({
                    "file": self.rel_path,
                    "line": getattr(node, "lineno", 0),
                    "text": assign_str[:80]
                })
            elif isinstance(node.value, ast.Constant) and node.value.value == "cuda":
                evidence = {
                    "file": self.rel_path,
                    "line": getattr(node, "lineno", 0),
                    "text": "device = 'cuda'"
                }
                if self._guard_depth > 0:
                    self.guarded_cuda.append(evidence)
                else:
                    self.unguarded_cuda.append(evidence)
        except Exception:
            pass
        self.generic_visit(node)

class CodeCompletenessVisitor(ast.NodeVisitor):
    """
    Scans AST for implementation stubs:
    - raise NotImplementedError
    - body with only pass or ...
    """
    def __init__(self, rel_path: str):
        self.rel_path = rel_path
        self.stubs: List[Dict[str, Any]] = []
        self.function_count: int = 0

    def visit_Raise(self, node: ast.Raise):
        if node.exc:
            exc_str = ast.unparse(node.exc) if hasattr(ast, "unparse") else ""
            if "NotImplementedError" in exc_str:
                self.stubs.append({
                    "file": self.rel_path,
                    "line": getattr(node, "lineno", 0),
                    "type": "not_implemented_error",
                    "text": f"raise {exc_str}"
                })
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.function_count += 1
        self._check_empty_body(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.function_count += 1
        self._check_empty_body(node)
        self.generic_visit(node)

    def _check_empty_body(self, node):
        # Skip abstract methods
        for decorator in node.decorator_list:
            dec_str = ast.unparse(decorator) if hasattr(ast, "unparse") else ""
            if "abstractmethod" in dec_str or "overload" in dec_str:
                return

        # Ignore docstrings
        body_stmts = [
            stmt for stmt in node.body
            if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str))
        ]

        if len(body_stmts) == 1:
            first = body_stmts[0]
            # pass statement
            if isinstance(first, ast.Pass):
                self.stubs.append({
                    "file": self.rel_path,
                    "line": getattr(node, "lineno", 0),
                    "type": "pass_stub",
                    "text": f"def {node.name}(...): pass"
                })
            # Ellipsis (...) statement
            elif isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and first.value.value is Ellipsis:
                self.stubs.append({
                    "file": self.rel_path,
                    "line": getattr(node, "lineno", 0),
                    "type": "ellipsis_stub",
                    "text": f"def {node.name}(...): ..."
                })

def triage_report(workspace: str) -> Dict[str, Any]:
    """
    Deterministic triage and code-completeness analysis.
    Executes ZERO repository code (pure AST and static inspection).
    Returns complete triage profile and verdict.
    """
    root = Path(workspace).resolve()
    stdlib = get_stdlib_module_names()
    declared_deps = parse_declared_dependencies(root)

    # 1. Discover all files and local modules
    py_files: List[Path] = []
    ipynb_files: List[Path] = []
    all_files: Set[str] = set()
    local_modules: Set[str] = set()

    for p in root.rglob("*"):
        if p.is_file():
            rel = str(p.relative_to(root)).replace("\\", "/")
            if any(ign in rel for ign in [".git/", "__pycache__/", ".pytest_cache/", ".site/"]):
                continue
            all_files.add(rel)
            if rel.endswith(".py"):
                py_files.append(p)
                parts = p.relative_to(root).parts
                if len(parts) == 1:
                    local_modules.add(parts[0][:-3])
                else:
                    local_modules.add(parts[0])
            elif rel.endswith(".ipynb"):
                ipynb_files.append(p)

    # Check for Notebook-only repository
    if len(ipynb_files) > 0 and len(py_files) == 0:
        return {
            "verdict": "UNSUPPORTED_FORMAT",
            "reason": "Notebook-only repository (contains .ipynb with no runnable Python scripts)",
            "evidence": [f"{ipynb_files[0].relative_to(root)}:1"],
            "blockers": ["notebook_only"],
            "warnings": [],
            "imports": {"stdlib": [], "declared": [], "local": [], "unresolved": []},
            "missing_local_modules": [],
            "stubs": [],
            "missing_data_refs": [],
            "gpu": {"unguarded": [], "guarded": [], "cuda_packages": []},
            "python_requires": None,
            "frameworks": []
        }

    # 2. AST Completeness & Import Classification
    imports_stdlib: Set[str] = set()
    imports_declared: Set[str] = set()
    imports_local: Set[str] = set()
    imports_unresolved: Set[str] = set()
    missing_local_modules: List[Dict[str, Any]] = []
    stubs: List[Dict[str, Any]] = []
    syntax_errors: List[Dict[str, Any]] = []
    total_functions: int = 0
    has_entry_point: bool = False

    unguarded_cuda_list: List[Dict[str, Any]] = []
    guarded_cuda_list: List[Dict[str, Any]] = []
    cuda_packages_found: List[str] = []

    frameworks: Set[str] = set()
    data_refs_referenced: Set[str] = set()
    pretrained_weights_refs: List[Dict[str, Any]] = []
    distributed_hints: List[Dict[str, Any]] = []

    # Check declared deps for CUDA-only packages
    for pkg in declared_deps:
        if pkg in CUDA_ONLY_PACKAGES:
            cuda_packages_found.append(pkg)

    # Scan python files
    for p in py_files:
        rel_str = str(p.relative_to(root)).replace("\\", "/")
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # Look for TODO/FIXME in text
        for line_no, line in enumerate(content.splitlines(), start=1):
            if re.search(r"#.*(TODO|FIXME)", line, re.I):
                stubs.append({
                    "file": rel_str,
                    "line": line_no,
                    "type": "todo_comment",
                    "text": line.strip()
                })

        # Scan for direct hardcoded device="cuda" string regex in non-parsed or parsed
        if re.search(r"device\s*=\s*['\"]cuda['\"]", content) and "torch.cuda.is_available" not in content:
            m = re.search(r"device\s*=\s*['\"]cuda['\"]", content)
            line_no = content[:m.start()].count("\n") + 1 if m else 1
            if not any(u["file"] == rel_str and u["line"] == line_no for u in unguarded_cuda_list):
                unguarded_cuda_list.append({
                    "file": rel_str,
                    "line": line_no,
                    "text": "device = 'cuda'"
                })

        # Parse AST
        try:
            tree = ast.parse(content, filename=rel_str)
        except SyntaxError as se:
            syntax_errors.append({
                "file": rel_str,
                "line": se.lineno or 1,
                "text": f"SyntaxError: {se.msg}"
            })
            continue

        # Check CUDA guards with visitor
        cuda_vis = GuardedCUDAVisitor(rel_str)
        cuda_vis.visit(tree)
        for u in cuda_vis.unguarded_cuda:
            if not any(x["file"] == u["file"] and x["line"] == u["line"] for x in unguarded_cuda_list):
                unguarded_cuda_list.append(u)
        guarded_cuda_list.extend(cuda_vis.guarded_cuda)

        # Check stubs with visitor
        stub_vis = CodeCompletenessVisitor(rel_str)
        stub_vis.visit(tree)
        stubs.extend(stub_vis.stubs)
        total_functions += stub_vis.function_count
        if '__name__' in content and '__main__' in content:
            has_entry_point = True

        # Check imports & references
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    root_pkg = name.split(".")[0].lower()
                    if root_pkg in stdlib:
                        imports_stdlib.add(name)
                    elif root_pkg in local_modules:
                        imports_local.add(name)
                    elif root_pkg in declared_deps or any(alias_name in declared_deps for alias_name in MODULE_PACKAGE_ALIASES.get(root_pkg, [])):
                        imports_declared.add(name)
                    else:
                        imports_unresolved.add(name)

                    if root_pkg in CUDA_ONLY_PACKAGES:
                        cuda_packages_found.append(root_pkg)

                    if root_pkg in ["torch", "torchvision", "torchaudio"]:
                        frameworks.add("pytorch")
                    elif root_pkg in ["tensorflow", "keras"]:
                        frameworks.add("tensorflow")
                    elif root_pkg in ["jax", "flax"]:
                        frameworks.add("jax")
                    elif root_pkg in ["sklearn"]:
                        frameworks.add("scikit-learn")

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_pkg = node.module.split(".")[0].lower()
                    if node.level > 0:
                        imports_local.add(node.module)
                        cur_dir = p.parent
                        rel_module_path = cur_dir / (node.module.replace(".", "/") + ".py")
                        rel_pkg_path = cur_dir / node.module.replace(".", "/") / "__init__.py"
                        if not rel_module_path.exists() and not rel_pkg_path.exists():
                            missing_local_modules.append({
                                "file": rel_str,
                                "line": getattr(node, "lineno", 1),
                                "module": node.module,
                                "text": f"from {'.' * node.level}{node.module} import ..."
                            })
                    elif root_pkg in stdlib:
                        imports_stdlib.add(node.module)
                    elif root_pkg in local_modules:
                        imports_local.add(node.module)
                    elif root_pkg in declared_deps or any(alias_name in declared_deps for alias_name in MODULE_PACKAGE_ALIASES.get(root_pkg, [])):
                        imports_declared.add(node.module)
                    else:
                        imports_unresolved.add(node.module)

                    if root_pkg in CUDA_ONLY_PACKAGES:
                        cuda_packages_found.append(root_pkg)

                    if root_pkg in ["torch", "torchvision", "torchaudio"]:
                        frameworks.add("pytorch")
                    elif root_pkg in ["tensorflow", "keras"]:
                        frameworks.add("tensorflow")
                    elif root_pkg in ["jax", "flax"]:
                        frameworks.add("jax")
                    elif root_pkg in ["sklearn"]:
                        frameworks.add("scikit-learn")
                elif node.level > 0 and node.names:
                    for alias in node.names:
                        sub_file = p.parent / f"{alias.name}.py"
                        sub_dir = p.parent / alias.name
                        if not sub_file.exists() and not sub_dir.exists():
                            missing_local_modules.append({
                                "file": rel_str,
                                "line": getattr(node, "lineno", 1),
                                "module": alias.name,
                                "text": f"from {'.' * node.level} import {alias.name}"
                            })

            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                sval = node.value.strip()
                if any(sval.endswith(ext) for ext in [".csv", ".tsv", ".npy", ".npz", ".pt", ".pth", ".parquet", ".jsonl"]):
                    data_refs_referenced.add(sval)
                if any(ext in sval for ext in [".ckpt", ".safetensors", "from_pretrained"]):
                    pretrained_weights_refs.append({
                        "file": rel_str,
                        "line": getattr(node, "lineno", 1),
                        "ref": sval
                    })

        if "torchrun" in content or "DistributedDataParallel" in content or "torch.distributed" in content:
            distributed_hints.append({
                "file": rel_str,
                "text": "Distributed training code detected"
            })

    # 3. Scan README and configs for referenced scripts and data files
    readme_scripts_missing: List[str] = []
    readme_path = root / "README.md"
    if readme_path.exists():
        try:
            rm_text = readme_path.read_text(encoding="utf-8", errors="ignore")
            for line in rm_text.splitlines():
                line = line.strip()
                m_py = re.search(r"\bpython3?\s+([\w./-]+\.py)", line)
                if m_py:
                    script_name = m_py.group(1).lstrip("./")
                    if script_name not in all_files:
                        readme_scripts_missing.append(script_name)
                for m_data in re.findall(r"[\w./-]+\.(?:csv|npy|pt|tsv|parquet|jsonl)", line):
                    data_refs_referenced.add(m_data.lstrip("./"))
        except Exception:
            pass

    # 4. Check data references existence
    missing_data_refs: List[str] = []
    for dref in sorted(data_refs_referenced):
        if dref.startswith("http://") or dref.startswith("https://"):
            continue
        target = root / dref
        if not target.exists() and not (root / "data" / Path(dref).name).exists():
            missing_data_refs.append(dref)

    # 5. Determine Python version
    python_req = detect_python_version_requirement(root)

    # 6. Formulate Verdict & Evidence
    blockers: List[str] = []
    warnings: List[str] = []
    evidence: List[str] = []

    findings: List[Tuple[int, str, str, str]] = []

    # Priority 1: Incomplete repository
    if syntax_errors:
        findings.append((1, "INCOMPLETE_REPO", f"Syntax errors detected in {len(syntax_errors)} files.", "syntax_error"))
        for err in syntax_errors:
            evidence.append(f"{err['file']}:{err['line']} - {err['text']}")

    if missing_local_modules:
        findings.append((1, "INCOMPLETE_REPO", f"Missing local module imports: {missing_local_modules[0]['module']}", "missing_local_module"))
        for mlm in missing_local_modules:
            evidence.append(f"{mlm['file']}:{mlm['line']} - missing local module '{mlm['module']}'")

    if readme_scripts_missing:
        findings.append((1, "INCOMPLETE_REPO", f"README-mentioned script '{readme_scripts_missing[0]}' does not exist.", "missing_readme_script"))
        evidence.append(f"README.md: script '{readme_scripts_missing[0]}' not found on disk")

    not_implemented = [st for st in stubs if st["type"] == "not_implemented_error"]
    empty_body_stubs = [st for st in stubs if st["type"] in ("pass_stub", "ellipsis_stub")]

    if not_implemented:
        findings.append((1, "INCOMPLETE_REPO", "Unimplemented stubs (not_implemented_error) found in code.", "unimplemented_stubs"))
        for st in not_implemented:
            evidence.append(f"{st['file']}:{st['line']} - {st['text']}")

    if empty_body_stubs:
        stub_ratio = (len(empty_body_stubs) / total_functions) if total_functions else 1.0
        dominates = stub_ratio >= STUB_RATIO_BLOCK_THRESHOLD
        if dominates and not has_entry_point:
            findings.append((
                1, "INCOMPLETE_REPO",
                f"Unimplemented stubs ({empty_body_stubs[0]['type']}) make up "
                f"{len(empty_body_stubs)}/{total_functions} functions with no entry point.",
                "unimplemented_stubs"
            ))
            for st in empty_body_stubs:
                evidence.append(f"{st['file']}:{st['line']} - {st['text']}")
        else:
            warnings.append(
                f"Repository contains {len(empty_body_stubs)} empty function "
                f"{'body' if len(empty_body_stubs) == 1 else 'bodies'} out of {total_functions} "
                f"functions (likely no-op hooks, not blocking): "
                + ", ".join(f"{st['file']}:{st['line']}" for st in empty_body_stubs[:5])
            )

    # Priority 2: hard GPU requirement
    if unguarded_cuda_list or cuda_packages_found:
        findings.append((2, "NEEDS_GPU", "Hard GPU requirement detected (unguarded CUDA calls or CUDA-only packages).", "gpu_required"))
        for u in unguarded_cuda_list:
            evidence.append(f"{u['file']}:{u['line']} - {u['text']}")
        for cp in cuda_packages_found:
            evidence.append(f"requirements.txt: CUDA-only package '{cp}'")

    # Priority 3: resources the sandbox cannot supply
    if missing_data_refs:
        findings.append((3, "NEEDS_LARGE_RESOURCES", f"Required data files missing from repository ({len(missing_data_refs)} files).", "data_unavailable"))
        for d in missing_data_refs[:5]:
            evidence.append(f"data_refs: '{d}' referenced but not found")

    if distributed_hints:
        findings.append((3, "NEEDS_LARGE_RESOURCES", "Distributed multi-GPU training required.", "distributed_required"))
        for dh in distributed_hints:
            evidence.append(f"{dh['file']}: {dh['text']}")

    for _prio, _verdict, _reason, blocker_name in findings:
        if blocker_name and blocker_name not in blockers:
            blockers.append(blocker_name)

    if findings:
        findings.sort(key=lambda f: f[0])
        _prio, verdict, reason, _blocker = findings[0]
    elif imports_unresolved or len(declared_deps) > 2:
        verdict = "FEASIBLE_WITH_PROVISIONING"
        reason = "Repository is feasible but requires dependency provisioning."
        if imports_unresolved:
            warnings.append(f"Unresolved imports may need provisioning: {list(imports_unresolved)[:5]}")
    else:
        verdict = "FEASIBLE"
        reason = "Repository structure is complete, CPU-compatible, and runnable."

    if guarded_cuda_list and not unguarded_cuda_list:
        warnings.append(f"Repository contains {len(guarded_cuda_list)} guarded torch.cuda.is_available() checks (safe on CPU).")

    return {
        "verdict": verdict,
        "reason": reason,
        "evidence": evidence,
        "blockers": blockers,
        "warnings": warnings,
        "imports": {
            "stdlib": sorted(list(imports_stdlib)),
            "declared": sorted(list(imports_declared)),
            "local": sorted(list(imports_local)),
            "unresolved": sorted(list(imports_unresolved))
        },
        "missing_local_modules": missing_local_modules,
        "stubs": stubs,
        "missing_data_refs": missing_data_refs,
        "gpu": {
            "unguarded": unguarded_cuda_list,
            "guarded": guarded_cuda_list,
            "cuda_packages": cuda_packages_found
        },
        "python_requires": python_req,
        "frameworks": sorted(list(frameworks))
    }
