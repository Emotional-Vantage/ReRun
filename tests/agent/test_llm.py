import json
import pytest
from pydantic import BaseModel
from pathlib import Path
from unittest.mock import patch

from agent.llm import call, LLMOutputInvalid
from agent.config import scrub_secrets

class SampleModel(BaseModel):
    name: str
    count: int

def mock_response(content):
    return content

@patch("agent.llm.execute_provider_request")
def test_llm_call_success(mock_call):
    mock_call.return_value = mock_response(json.dumps({"name": "test_agent", "count": 42}))
    
    res = call("solver", "test_mode", {"foo": "bar"}, SampleModel)
    assert isinstance(res, SampleModel)
    assert res.name == "test_agent"
    assert res.count == 42

@patch("agent.llm.execute_provider_request")
def test_llm_reprompt_on_invalid_json(mock_call):
    # First response invalid json, second response valid
    mock_call.side_effect = [
        mock_response("This is not json at all!"),
        mock_response(json.dumps({"name": "fixed_agent", "count": 10}))
    ]
    
    res = call("solver", "test_mode", {"foo": "bar"}, SampleModel)
    assert res.name == "fixed_agent"
    assert res.count == 10

@patch("agent.llm.execute_provider_request")
def test_llm_fails_after_reprompt(mock_call):
    # Both responses invalid
    mock_call.side_effect = [
        mock_response("Invalid first"),
        mock_response("Invalid second")
    ]
    
    with pytest.raises(LLMOutputInvalid):
        call("solver", "test_mode", {"foo": "bar"}, SampleModel)

def test_secret_scrubbing():
    dirty_text = "Here is my secret: sk-1234567890abcdef12345678 and token = 'secret12345'"
    clean_text = scrub_secrets(dirty_text)
    assert "sk-1234567890abcdef12345678" not in clean_text
    assert "[REDACTED_SECRET]" in clean_text

def test_replay_mode_miss(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MODE", "replay")
    monkeypatch.setenv("CASSETTE_DIR", str(tmp_path))
    
    import agent.config as config
    monkeypatch.setattr(config, "LLM_MODE", "replay")
    monkeypatch.setattr(config, "CASSETTE_DIR", str(tmp_path))
    
    from agent import llm
    monkeypatch.setattr(llm, "LLM_MODE", "replay")
    monkeypatch.setattr(llm, "CASSETTE_DIR", str(tmp_path))
    monkeypatch.setattr(llm, "_ACTIVE_FAKE_LLM", None)

    with pytest.raises(RuntimeError, match="Cassette miss"):
        call("solver", "unknown_mode", {"a": 1}, SampleModel)

@patch("agent.llm.execute_provider_request")
def test_cassette_record_and_replay(mock_call, tmp_path, monkeypatch):
    cassette_dir = str(tmp_path / "cassettes")
    from agent import llm
    
    # 1. Record mode
    monkeypatch.setattr(llm, "LLM_MODE", "record")
    monkeypatch.setattr(llm, "CASSETTE_DIR", cassette_dir)
    
    mock_call.return_value = mock_response(json.dumps({"name": "saved_agent", "count": 99}))
    
    res = call("solver", "record_test", {"test_key": "val"}, SampleModel, benchmark_id="test_bench")
    assert res.name == "saved_agent"
    
    # 2. Replay mode
    monkeypatch.setattr(llm, "LLM_MODE", "replay")
    mock_call.side_effect = RuntimeError("Should not be called in replay mode")
    
    replayed = call("solver", "record_test", {"test_key": "val"}, SampleModel, benchmark_id="test_bench")
    assert replayed.name == "saved_agent"
    assert replayed.count == 99

@patch("agent.llm.execute_provider_request")
def test_fallback_provider_on_primary_failure(mock_call, monkeypatch):
    from agent import llm
    monkeypatch.setattr(llm, "SOLVER_PROVIDER", "gemini")
    monkeypatch.setattr(llm, "FALLBACK_PROVIDER", "openai_compat")
    monkeypatch.setattr(llm, "_ACTIVE_FAKE_LLM", None)
    
    events = []
    llm.set_event_listener(lambda ev, meta: events.append((ev, meta)))
    
    def side_effect(provider, model, base_url, api_key, messages):
        if provider == "gemini":
            raise RuntimeError("Primary gemini connection failed")
        return json.dumps({"name": "fallback_agent", "count": 123})
        
    mock_call.side_effect = side_effect
    
    res = call("solver", "fallback_test", {"q": 1}, SampleModel)
    assert res.name == "fallback_agent"
    assert res.count == 123
    assert any(ev == "llm_fallback" for ev, _ in events)
    
    llm.set_event_listener(None)
