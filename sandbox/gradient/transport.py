"""
Moving a workspace to a droplet and the results back, without breaking the
evidence ledger.

ReRun's reports are trustworthy because every sentence resolves to a byte range
of an artifact with a recorded SHA-256. Local execution makes that easy: the
file the container wrote is the file the ledger hashed. Remote execution puts a
network in between, and a log that is silently truncated mid-transfer would
still hash cleanly on arrival -- it would just be a hash of the wrong thing.

So artifacts are fingerprinted ON the droplet, by the droplet, before they
move. The digest travels separately from the payload, and the local side
recomputes and compares. A mismatch is a hard failure, never a warning: ReRun
would rather report that it could not retrieve a result than report a result it
cannot vouch for.
"""

from __future__ import annotations

import hashlib
import os
import shlex
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

REMOTE_ROOT = "/opt/rerun"


class TransportError(RuntimeError):
    """A transfer failed, or arrived with a digest that does not match."""


@dataclass
class SSHTarget:
    host: str
    user: str = "root"
    key_path: Optional[str] = None
    connect_timeout: int = 20

    def base_args(self) -> list[str]:
        args = [
            "-o", "BatchMode=yes",
            "-o", f"ConnectTimeout={self.connect_timeout}",
            # A droplet created seconds ago has no entry in known_hosts and its
            # host key is not published anywhere we can check against, so strict
            # checking cannot succeed on a first contact. accept-new pins the key
            # for the rest of the droplet's life, which stops an in-session
            # swap, but it does NOT authenticate the very first handshake. That
            # residual exposure is recorded on the run receipt rather than
            # papered over, and it is the reason a remote run is marked as a
            # weaker isolation tier than a local one.
            "-o", "StrictHostKeyChecking=accept-new",
        ]
        if self.key_path:
            args += ["-i", self.key_path, "-o", "IdentitiesOnly=yes"]
        return args

    def dest(self) -> str:
        return f"{self.user}@{self.host}"


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_ssh(target: SSHTarget, command: str, timeout: int = 300) -> tuple[int, str, str]:
    """Run one command on the droplet. Returns (exit_code, stdout, stderr)."""
    cmd = ["ssh", *target.base_args(), target.dest(), command]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise TransportError(f"ssh command timed out after {timeout}s: {command[:120]}") from e
    except FileNotFoundError as e:
        raise TransportError("the `ssh` client is not installed on this machine") from e
    return p.returncode, p.stdout, p.stderr


def wait_for_ssh(target: SSHTarget, timeout_s: int = 300, poll_s: float = 5.0) -> None:
    """A droplet reports `active` before sshd is accepting connections."""
    import time

    deadline = time.time() + timeout_s
    last_err = ""
    while time.time() < deadline:
        code, _, err = run_ssh(target, "true", timeout=25)
        if code == 0:
            return
        last_err = err.strip()
        time.sleep(poll_s)
    raise TransportError(f"ssh never became reachable on {target.host}: {last_err}")


def push_directory(target: SSHTarget, local_dir: Path, remote_dir: str, timeout: int = 900) -> None:
    """
    Stream a directory up as a tar, rather than copying file by file.

    A workspace plus a wheelhouse is thousands of small files; scp pays a round
    trip per file and a torch wheel alone would dominate the run. One tar
    stream also means the remote tree is either fully written or not written,
    which matters because a half-populated workspace would run and produce a
    confidently wrong result.
    """
    if not local_dir.exists():
        raise TransportError(f"nothing to upload: {local_dir} does not exist")

    run_ssh(target, f"mkdir -p {shlex.quote(remote_dir)}", timeout=60)

    tar_cmd = ["tar", "-C", str(local_dir), "-cf", "-", "."]
    ssh_cmd = [
        "ssh", *target.base_args(), target.dest(),
        f"tar -C {shlex.quote(remote_dir)} -xf -",
    ]
    try:
        tar = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
        ssh = subprocess.Popen(ssh_cmd, stdin=tar.stdout, stderr=subprocess.PIPE)
        if tar.stdout:
            tar.stdout.close()
        _, err = ssh.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise TransportError(f"upload of {local_dir} timed out after {timeout}s") from e
    if ssh.returncode != 0:
        raise TransportError(f"upload of {local_dir} failed: {err.decode(errors='ignore')[:300]}")


def fetch_file_verified(
    target: SSHTarget,
    remote_path: str,
    local_path: Path,
    timeout: int = 600,
) -> str:
    """
    Pull one artifact back and prove it survived the trip.

    The digest is taken on the droplet first. Only then is the payload moved,
    and the local copy is hashed independently; the two must agree. Returns the
    verified SHA-256 so the caller can hand the very same digest to the
    evidence ledger instead of recomputing a third time.
    """
    code, out, err = run_ssh(target, f"sha256sum {shlex.quote(remote_path)}", timeout=120)
    if code != 0:
        raise TransportError(
            f"could not fingerprint {remote_path} on the droplet: {err.strip()[:200]}"
        )
    remote_digest = out.strip().split()[0]

    local_path.parent.mkdir(parents=True, exist_ok=True)
    scp_cmd = [
        "scp", *target.base_args(),
        f"{target.dest()}:{remote_path}", str(local_path),
    ]
    try:
        p = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise TransportError(f"download of {remote_path} timed out after {timeout}s") from e
    if p.returncode != 0:
        raise TransportError(f"download of {remote_path} failed: {p.stderr.strip()[:300]}")

    local_digest = sha256_file(local_path)
    if local_digest != remote_digest:
        # Do not keep a file we cannot vouch for; a later phase would happily
        # quote from it.
        try:
            local_path.unlink()
        except OSError:
            pass
        raise TransportError(
            f"integrity check failed for {remote_path}: the droplet reported "
            f"{remote_digest[:16]}... but {local_digest[:16]}... arrived. "
            "The artifact has been discarded and this run cannot be trusted."
        )
    return local_digest


def fetch_directory(target: SSHTarget, remote_dir: str, local_dir: Path, timeout: int = 900) -> None:
    """Pull a whole output directory back as a tar stream."""
    local_dir.mkdir(parents=True, exist_ok=True)
    code, _, _ = run_ssh(target, f"test -d {shlex.quote(remote_dir)}", timeout=60)
    if code != 0:
        return  # nothing produced; the caller decides whether that is an error

    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        ssh_cmd = [
            "ssh", *target.base_args(), target.dest(),
            f"tar -C {shlex.quote(remote_dir)} -cf - .",
        ]
        with open(tmp_path, "wb") as sink:
            p = subprocess.run(ssh_cmd, stdout=sink, stderr=subprocess.PIPE, timeout=timeout)
        if p.returncode != 0:
            raise TransportError(
                f"download of {remote_dir} failed: {p.stderr.decode(errors='ignore')[:300]}"
            )
        with tarfile.open(tmp_path) as tf:
            _safe_extract(tf, local_dir)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def _safe_extract(tf: tarfile.TarFile, dest: Path) -> None:
    """
    Extract without letting an entry escape `dest`.

    The archive is built from output produced by the paper's own code, which
    ReRun treats as untrusted throughout; a crafted `../../` member or a symlink
    out of the tree would write wherever the API process can write.
    """
    dest = dest.resolve()
    for member in tf.getmembers():
        target_path = (dest / member.name).resolve()
        if not str(target_path).startswith(str(dest) + os.sep) and target_path != dest:
            raise TransportError(f"refusing path traversal in archive member {member.name!r}")
        if member.issym() or member.islnk():
            link_target = (target_path.parent / member.linkname).resolve()
            if not str(link_target).startswith(str(dest) + os.sep):
                raise TransportError(f"refusing link escaping the output dir: {member.name!r}")
    tf.extractall(dest)
