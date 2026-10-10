import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List

from agent.config import (
    GITHUB_REPO_URL_REGEX,
    CUSTOM_REPO_CLONE_TIMEOUT_S,
    CUSTOM_REPO_MAX_SIZE_MB,
    CUSTOM_REPO_MAX_FILES,
)

class RepoIngestError(ValueError):
    """Raised when repository cloning, validation, or ingestion fails."""
    pass

def validate_repo_url(url: str) -> None:
    r"""
    Validates GitHub URL per Stage 2 requirements:
    - Must match ^https://github\.com/[\w.-]+/[\w.-]+(\.git)?$
    - No credentials (e.g., https://user:pass@github.com/...)
    - No non-GitHub hosts (e.g. gitlab, bitbucket)
    - No file://, ssh://, git@ schemes
    """
    if not url or not isinstance(url, str):
        raise RepoIngestError("Repository URL is required.")
        
    url_stripped = url.strip()
    
    if url_stripped.startswith("file://"):
        raise RepoIngestError("file:// URLs are strictly prohibited for security.")
    if url_stripped.startswith("git@") or url_stripped.startswith("ssh://"):
        raise RepoIngestError("SSH repository URLs are not supported. Use HTTPS.")
    if not url_stripped.startswith("https://"):
        raise RepoIngestError("Repository URL must use https:// scheme.")

    if "@" in url_stripped:
        raise RepoIngestError("Repository URL must not contain user credentials or auth tokens.")

    if not re.match(GITHUB_REPO_URL_REGEX, url_stripped):
        raise RepoIngestError(
            f"Invalid repository URL '{url}'. Must be a public GitHub HTTPS URL "
            "matching format: https://github.com/owner/repository"
        )

def check_symlinks(root_dir: Path) -> None:
    """
    Recursively scans root_dir and rejects symlinks that escape the repository boundary.
    """
    root_resolved = root_dir.resolve()
    for item in root_dir.rglob("*"):
        if item.is_symlink():
            try:
                target_resolved = item.resolve()
                if root_resolved not in target_resolved.parents and target_resolved != root_resolved:
                    raise RepoIngestError(
                        f"Escaping symlink detected: '{item.relative_to(root_dir)}' points outside "
                        f"workspace to '{target_resolved}'. Rejected for security."
                    )
            except Exception as e:
                if isinstance(e, RepoIngestError):
                    raise
                raise RepoIngestError(f"Invalid or broken symlink detected at '{item}': {e}")

def normalize_crlf_to_lf(root_dir: Path) -> int:
    """
    Normalizes Windows CRLF line endings to LF across text files in root_dir.
    Returns the count of normalized files.
    """
    normalized_count = 0
    binary_exts = {
        ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".whl", ".tar", ".gz",
        ".zip", ".pyc", ".so", ".bin", ".pt", ".pth", ".ckpt", ".npy", ".npz"
    }
    
    for file_path in root_dir.rglob("*"):
        if file_path.is_file() and not file_path.is_symlink():
            if file_path.suffix.lower() in binary_exts:
                continue
            if any(part in file_path.parts for part in [".git", "__pycache__", ".site"]):
                continue
            try:
                raw_bytes = file_path.read_bytes()
                if b"\x00" in raw_bytes[:1024]:
                    continue
                if b"\r\n" in raw_bytes:
                    normalized_bytes = raw_bytes.replace(b"\r\n", b"\n")
                    file_path.write_bytes(normalized_bytes)
                    normalized_count += 1
            except Exception:
                pass
    return normalized_count

def ingest_custom_repo(
    repo_url: str,
    repo_ref: Optional[str],
    workspace_path: str,
    timeout_s: int = CUSTOM_REPO_CLONE_TIMEOUT_S,
    max_size_mb: int = CUSTOM_REPO_MAX_SIZE_MB,
    max_files: int = CUSTOM_REPO_MAX_FILES
) -> Dict[str, Any]:
    """
    Clones a remote GitHub repository safely:
    - Shallow clone (--depth 1, --no-tags, --no-recurse-submodules, LFS filters disabled)
    - Checked out to repo_ref if provided
    - Audits size cap & file count cap
    - Rejects escaping symlinks
    - Copies into workspace as a fresh git init (drops remote, hooks, origin history)
    - Normalizes CRLF -> LF
    - Returns commit metadata
    """
    validate_repo_url(repo_url)
    ws = Path(workspace_path)
    ws.mkdir(parents=True, exist_ok=True)
    
    with tempfile.TemporaryDirectory(prefix="rerun_clone_") as temp_dir:
        clone_dest = Path(temp_dir) / "repo"
        
        clone_cmd = [
            "git",
            "-c", "filter.lfs.smudge=",
            "-c", "filter.lfs.clean=",
            "-c", "filter.lfs.process=",
            "clone",
            "--depth", "1",
            "--no-tags",
            "--no-recurse-submodules"
        ]
        
        if repo_ref:
            clone_cmd.extend(["--branch", repo_ref])
            
        clone_cmd.extend([repo_url, str(clone_dest)])
        
        clone_env = os.environ.copy()
        clone_env["GIT_TERMINAL_PROMPT"] = "0"
        clone_env["GIT_ASKPASS"] = "true"

        try:
            res = subprocess.run(
                clone_cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
                env=clone_env
            )
        except subprocess.TimeoutExpired:
            raise RepoIngestError(f"Clone timed out after {timeout_s} seconds.")
            
        if res.returncode != 0:
            err_msg = res.stderr.strip() or res.stdout.strip()
            raise RepoIngestError(f"Failed to clone repository: {err_msg}")
            
        rev_cmd = ["git", "rev-parse", "HEAD"]
        rev_res = subprocess.run(rev_cmd, cwd=str(clone_dest), capture_output=True, text=True, check=False)
        commit_sha = rev_res.stdout.strip() if rev_res.returncode == 0 else "unknown"
        
        total_size = 0
        total_files = 0
        for p in clone_dest.rglob("*"):
            if ".git" in p.parts:
                continue
            if p.is_file():
                total_files += 1
                try:
                    total_size += p.stat().st_size
                except Exception:
                    pass
                    
        total_size_mb = total_size / (1024 * 1024)
        if total_size_mb > max_size_mb:
            raise RepoIngestError(
                f"Repository size ({total_size_mb:.1f} MB) exceeds maximum allowed cap of {max_size_mb} MB."
            )
        if total_files > max_files:
            raise RepoIngestError(
                f"Repository contains {total_files} files, exceeding maximum limit of {max_files} files."
            )
            
        check_symlinks(clone_dest)
        
        for item in ws.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
                
        for item in clone_dest.iterdir():
            if item.name == ".git":
                continue
            dest_item = ws / item.name
            if item.is_dir():
                shutil.copytree(item, dest_item, symlinks=True)
            else:
                shutil.copy2(item, dest_item, follow_symlinks=False)
                
        check_symlinks(ws)
        
        crlf_count = normalize_crlf_to_lf(ws)
        
        subprocess.run(["git", "init"], cwd=str(ws), capture_output=True, check=False)
        subprocess.run(["git", "config", "user.email", "rerun@local"], cwd=str(ws), capture_output=True, check=False)
        subprocess.run(["git", "config", "user.name", "Rerun"], cwd=str(ws), capture_output=True, check=False)
        subprocess.run(["git", "add", "-A"], cwd=str(ws), capture_output=True, check=False)
        subprocess.run(["git", "commit", "-m", f"Initial ingest from {repo_url} at {commit_sha}"], cwd=str(ws), capture_output=True, check=False)
        
        return {
            "commit_sha": commit_sha,
            "files_count": total_files,
            "size_bytes": total_size,
            "crlf_normalized_count": crlf_count,
            "repo_url": repo_url,
            "repo_ref": repo_ref
        }
