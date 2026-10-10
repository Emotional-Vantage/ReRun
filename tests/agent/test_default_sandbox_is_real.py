import os
import pytest
from sandbox.fake import get_sandbox

def test_default_sandbox_is_not_fake(monkeypatch):
    """Stage 1/5 gate: default sandbox must be DockerSandbox when SANDBOX_TYPE is unset."""
    monkeypatch.delenv("SANDBOX_TYPE", raising=False)
    monkeypatch.delenv("ALLOW_FAKE_SANDBOX", raising=False)
    sb = get_sandbox()
    assert type(sb).__name__ == "DockerSandbox", (
        f"Default sandbox must be DockerSandbox in the live app path, got {type(sb).__name__}."
    )

def test_fake_sandbox_requires_allow_flag(monkeypatch):
    """Refuse to select FakeSandbox without ALLOW_FAKE_SANDBOX=1."""
    monkeypatch.setenv("SANDBOX_TYPE", "fake")
    monkeypatch.delenv("ALLOW_FAKE_SANDBOX", raising=False)
    with pytest.raises(RuntimeError, match="Refusing to select FakeSandbox without ALLOW_FAKE_SANDBOX=1"):
        get_sandbox()

def test_fake_sandbox_allowed_with_explicit_flag(monkeypatch):
    """FakeSandbox allowed only when explicitly flagged."""
    monkeypatch.setenv("SANDBOX_TYPE", "fake")
    monkeypatch.setenv("ALLOW_FAKE_SANDBOX", "1")
    sb = get_sandbox()
    assert type(sb).__name__ == "FakeSandbox"
