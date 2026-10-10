import pytest
import os
from backend.app.main import startup_event
from sandbox.fake import get_sandbox
from sandbox.docker_sandbox import DockerSandbox


def test_startup_refuses_fake_sandbox_without_allow_flag(monkeypatch):
    monkeypatch.setenv("SANDBOX_TYPE", "fake")
    monkeypatch.delenv("ALLOW_FAKE_SANDBOX", raising=False)
    with pytest.raises(
        RuntimeError,
        match="Refusing to start API with SANDBOX_TYPE=fake without ALLOW_FAKE_SANDBOX=1",
    ):
        startup_event()


def test_startup_allows_fake_sandbox_with_allow_flag(monkeypatch):
    monkeypatch.setenv("SANDBOX_TYPE", "fake")
    monkeypatch.setenv("ALLOW_FAKE_SANDBOX", "1")
    # Should not raise RuntimeError
    startup_event()


def test_startup_allows_default_docker_sandbox(monkeypatch):
    monkeypatch.delenv("SANDBOX_TYPE", raising=False)
    monkeypatch.delenv("ALLOW_FAKE_SANDBOX", raising=False)
    startup_event()


def test_get_sandbox_guard(monkeypatch):
    monkeypatch.setenv("SANDBOX_TYPE", "fake")
    monkeypatch.delenv("ALLOW_FAKE_SANDBOX", raising=False)
    with pytest.raises(
        RuntimeError,
        match="Refusing to select FakeSandbox without ALLOW_FAKE_SANDBOX=1",
    ):
        get_sandbox()

    monkeypatch.setenv("ALLOW_FAKE_SANDBOX", "1")
    sb = get_sandbox()
    assert type(sb).__name__ == "FakeSandbox"

    monkeypatch.delenv("SANDBOX_TYPE", raising=False)
    sb_default = get_sandbox()
    assert isinstance(sb_default, DockerSandbox)
