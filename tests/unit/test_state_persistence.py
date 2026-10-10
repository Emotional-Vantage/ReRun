"""
Regression tests for project-state persistence durability and ErrorClass validity.
"""

import json
from typing import get_args
import pytest
from pydantic import ValidationError

from agent.state import ProjectState, Attempt, ErrorClass


def _make_state(project_id: str = "p_persist", phase: str = "VALIDATE") -> ProjectState:
    return ProjectState(
        project_id=project_id,
        benchmark_id="b1_control",
        repo_commit="abc1234",
        phase=phase,
        budgets={"steps_used": 0},
        claims=[],
        paper_settings=[],
        repo_profile={},
    )


def test_metric_extraction_failed_is_a_valid_error_class():
    """The value handle_validate assigns must be a member of the literal it is typed against."""
    assert "metric_extraction_failed" in get_args(ErrorClass)


@pytest.mark.parametrize("error_class", get_args(ErrorClass))
def test_every_error_class_survives_a_json_round_trip(error_class):
    """
    Any error_class the orchestrator can assign must survive JSON serialization and deserialization.
    This is the guard preventing an unhandled error_class literal from breaking project loading.
    """
    attempt = Attempt(
        n=1,
        patches_applied=["P-1"],
        exit_code=1,
        error_class=error_class,
        started_at="2026-10-10T12:00:00Z",
    )
    dumped = attempt.model_dump_json()
    loaded_attempt = Attempt.model_validate_json(dumped)
    assert loaded_attempt.error_class == error_class

    state = _make_state()
    state.attempts.append(attempt)
    state_dumped = state.model_dump_json()
    loaded_state = ProjectState.model_validate_json(state_dumped)
    assert len(loaded_state.attempts) == 1
    assert loaded_state.attempts[0].error_class == error_class


def test_invalid_error_class_is_rejected():
    raw_attempt = {
        "n": 1,
        "patches_applied": [],
        "exit_code": 1,
        "error_class": "unregistered_bogus_error_class",
        "started_at": "now",
    }
    with pytest.raises(ValidationError):
        Attempt.model_validate(raw_attempt)
