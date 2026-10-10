import os
from unittest.mock import patch, MagicMock

import docker
from sandbox.manager import build_container_spec, probe_gpu
from pathlib import Path
from sandbox.limits import get_limits


@patch("sandbox.manager.get_limits")
@patch("sandbox.manager.probe_gpu")
def test_gpu_mode_disabled(mock_probe, mock_get_limits):
    mock_limits = MagicMock()
    mock_limits.gpu_enabled = False
    mock_limits.pids = 512
    mock_limits.mem = "1g"
    mock_limits.cpus = 1.0
    mock_get_limits.return_value = mock_limits

    spec = build_container_spec("test", Path("/workspace"), False, "echo 1")

    assert "device_requests" not in spec
    mock_probe.assert_not_called()


@patch("sandbox.manager.get_limits")
@patch("sandbox.manager.probe_gpu")
def test_gpu_mode_enabled_but_probe_fails(mock_probe, mock_get_limits):
    mock_limits = MagicMock()
    mock_limits.gpu_enabled = True
    mock_limits.pids = 512
    mock_limits.mem = "1g"
    mock_limits.cpus = 1.0
    mock_get_limits.return_value = mock_limits

    mock_probe.return_value = {"usable": False, "reason": "No nvidia runtime found", "count": 0}

    spec = build_container_spec("test", Path("/workspace"), False, "echo 1")

    assert "device_requests" not in spec
    mock_probe.assert_called_once()


@patch("sandbox.manager.get_limits")
@patch("sandbox.manager.probe_gpu")
def test_gpu_mode_enabled_and_probe_succeeds(mock_probe, mock_get_limits):
    mock_limits = MagicMock()
    mock_limits.gpu_enabled = True
    mock_limits.gpu_image = "rerun-gpu:py311"
    mock_limits.gpu_count = 1
    mock_limits.pids = 512
    mock_limits.mem = "1g"
    mock_limits.cpus = 1.0
    mock_get_limits.return_value = mock_limits

    mock_probe.return_value = {"usable": True, "reason": "GPU probe successful", "count": 1}

    spec = build_container_spec("test", Path("/workspace"), False, "echo 1")

    assert "device_requests" in spec
    assert spec["image"] == "rerun-gpu:py311"
    assert len(spec["device_requests"]) == 1
    assert spec["device_requests"][0].count == 1
    assert spec["device_requests"][0].capabilities == [["gpu"]]
    mock_probe.assert_called_once()
