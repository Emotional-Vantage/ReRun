import time
import datetime
import pytest
from pathlib import Path
from agent.key_rotator import KeyRotator
from agent.config import scrub_secrets, parse_api_keys

MOCK_KEYS = [
    "AIzaSyAlphaSecretKey11111111111111",
    "AIzaSyBetaSecretKey22222222222222",
    "AIzaSyGammaSecretKey33333333333333"
]

@pytest.fixture
def temp_stats_file(tmp_path):
    return str(tmp_path / "test_key_stats.json")

@pytest.fixture
def rotator(temp_stats_file):
    rot = KeyRotator(keys=MOCK_KEYS, threshold=3, stats_path=temp_stats_file)
    rot.reset_counts()
    return rot

def test_round_robin_outside_task(rotator):
    assert rotator.get_active_key() == MOCK_KEYS[0]
    
    # 2 requests on key 0 (under threshold 3)
    rotator.record_success(MOCK_KEYS[0])
    rotator.record_success(MOCK_KEYS[0])
    assert rotator.get_active_key() == MOCK_KEYS[0]
    
    # 3rd request reaches threshold -> auto-advances to key 1
    rotator.record_success(MOCK_KEYS[0])
    assert rotator.get_active_key() == MOCK_KEYS[1]
    
    # 3 requests on key 1 -> auto-advances to key 2
    for _ in range(3):
        rotator.record_success(MOCK_KEYS[1])
    assert rotator.get_active_key() == MOCK_KEYS[2]
    
    # 3 requests on key 2 -> wraps back to key 0
    for _ in range(3):
        rotator.record_success(MOCK_KEYS[2])
    assert rotator.get_active_key() == MOCK_KEYS[0]

def test_task_boundary_holds_rotation(rotator):
    # Key 0 starts
    assert rotator.get_active_key() == MOCK_KEYS[0]
    rotator.record_success(MOCK_KEYS[0])
    rotator.record_success(MOCK_KEYS[0])
    
    # Task begins (e.g., analyze or plan phase)
    rotator.begin_task("phase_analyze")
    assert rotator.in_task is True
    
    # Exceeds threshold (threshold=3, total now 4)
    rotator.record_success(MOCK_KEYS[0])
    rotator.record_success(MOCK_KEYS[0])
    
    # Crucial check: During task, it must NOT rotate mid-task!
    assert rotator.get_active_key() == MOCK_KEYS[0]
    assert rotator.current_index == 0
    
    # Even more requests mid-task
    rotator.record_success(MOCK_KEYS[0])
    assert rotator.get_active_key() == MOCK_KEYS[0]
    
    # Task finishes -> rotator checks threshold and advances to key 1
    rotator.end_task()
    assert rotator.in_task is False
    assert rotator.get_active_key() == MOCK_KEYS[1]

def test_emergency_429_failover(rotator):
    assert rotator.get_active_key() == MOCK_KEYS[0]
    
    # Key 0 hits HTTP 429
    new_key = rotator.report_rate_limit(MOCK_KEYS[0])
    assert new_key == MOCK_KEYS[1]
    assert rotator.get_active_key() == MOCK_KEYS[1]
    
    # Key 0 should be in cooldown
    stats = rotator.get_stats()
    key0_summary = stats["key_summaries"][0]
    assert key0_summary["cooldown_active"] is True

def test_daily_reset(rotator):
    rotator.record_success(MOCK_KEYS[0])
    rotator.record_success(MOCK_KEYS[0])
    assert rotator.request_counts[MOCK_KEYS[0]] == 2
    
    # Simulate past date
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    rotator.last_reset_date = yesterday
    
    # Trigger check
    rotator._check_daily_reset()
    assert rotator.request_counts[MOCK_KEYS[0]] == 0
    assert rotator.requests_in_turn == 0
    assert rotator.last_reset_date == datetime.date.today().isoformat()

def test_persistence_save_and_load(temp_stats_file):
    rot1 = KeyRotator(keys=MOCK_KEYS, threshold=5, stats_path=temp_stats_file)
    rot1.reset_counts()
    rot1.record_success(MOCK_KEYS[0])
    rot1.record_success(MOCK_KEYS[0])
    rot1.record_success(MOCK_KEYS[0])
    
    # Create new instance with same stats file
    rot2 = KeyRotator(keys=MOCK_KEYS, threshold=5, stats_path=temp_stats_file)
    assert rot2.request_counts[MOCK_KEYS[0]] == 3
    assert rot2.requests_in_turn == 3
    assert rot2.current_index == 0

def test_placeholder_filtering():
    raw_env = "PLACEHOLDER_KEY_1, AIzaSyRealKey1111111111111, PLACEHOLDER_KEY_2"
    parsed = parse_api_keys(raw_env)
    assert parsed == ["AIzaSyRealKey1111111111111"]

def test_scrub_secrets_masks_keys(rotator):
    for k in MOCK_KEYS:
        masked = scrub_secrets(f"Error calling API with key {k}")
        assert k not in masked

    stats = rotator.get_stats()
    for summary in stats["key_summaries"]:
        for k in MOCK_KEYS:
            assert k != summary["key_masked"]

def test_llm_rotates_on_429_and_retries():
    from unittest.mock import patch
    from pydantic import BaseModel
    import httpx
    import agent.llm as llm_module

    class DummyModel(BaseModel):
        answer: str

    test_keys = ["AIzaSyKey111111111111111111111111", "AIzaSyKey222222222222222222222222"]
    rot = KeyRotator(keys=test_keys, threshold=100)
    rot.reset_counts()

    call_keys = []

    def fake_execute(provider, model, base_url, api_key, messages):
        call_keys.append(api_key)
        if api_key == test_keys[0]:
            request = httpx.Request("POST", "http://test")
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError("Rate limited", request=request, response=response)
        return '{"answer": "ok"}'

    with patch.object(llm_module, "key_rotator", rot), \
         patch.object(llm_module, "_ACTIVE_FAKE_LLM", None), \
         patch.object(llm_module, "SOLVER_PROVIDER", "gemini"), \
         patch.object(llm_module, "LLM_MODE", "live"), \
         patch.object(llm_module, "execute_provider_request", side_effect=fake_execute):

        result = llm_module.call("solver", "test", {"query": "hi"}, DummyModel)
        assert result.answer == "ok"
        assert call_keys == [test_keys[0], test_keys[1]]
        assert rot.request_counts[test_keys[1]] == 1

def test_loop_phase_wraps_key_rotator_task():
    loop = pytest.importorskip("agent.loop")
    from agent.state import ProjectState
    from unittest.mock import patch

    state = ProjectState(
        project_id="test_rot_proj",
        benchmark_id="b1",
        repo_commit="abc1234",
        phase="INGEST",
        budgets={},
        claims=[],
        paper_settings=[],
        repo_profile={}
    )

    rotator = KeyRotator(keys=["AIzaSyKey111111111111111111111111"], threshold=10)
    events = []

    def fake_handler(s, d):
        events.append(("in_task", rotator.in_task, rotator.current_task_name))
        s.phase = "DONE"

    with patch.dict(loop.PHASE_HANDLERS, {"INGEST": fake_handler}), \
         patch("agent.loop.key_rotator", rotator):
        loop.run_project(state)

    assert events == [("in_task", True, "phase_INGEST")]
    assert rotator.in_task is False

def test_key_stats_api_endpoint():
    try:
        from backend.app.main import app
    except (ImportError, AttributeError):
        pytest.skip("backend.app.main:app is not implemented until Stage 7")

    from fastapi.testclient import TestClient
    client = TestClient(app)
    response = client.get("/api/keys/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_keys" in data
    assert "current_index" in data
    assert "key_summaries" in data
