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


@patch("agent.llm.execute_provider_request")
@patch("agent.llm.key_rotator")
def test_critic_uses_groq_and_bypasses_key_rotation(mock_rotator, mock_exec, monkeypatch):
    from agent import llm
    monkeypatch.setattr(llm, "CRITIC_PROVIDER", "groq")
    monkeypatch.setattr(llm, "CRITIC_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(llm, "CRITIC_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setattr(llm, "CRITIC_API_KEY", "gsk_test_groq_api_key_12345")
    monkeypatch.setattr(llm, "_ACTIVE_FAKE_LLM", None)

    mock_exec.return_value = json.dumps({"name": "groq_critic", "count": 77})

    res = llm.call("critic", "test_critic_mode", {"review": "data"}, SampleModel)

    assert res.name == "groq_critic"
    assert res.count == 77

    # Ensure execute_provider_request received groq parameters and CRITIC_API_KEY directly
    mock_exec.assert_called_once()
    call_args = mock_exec.call_args[0]
    assert call_args[0] == "groq"
    assert call_args[1] == "openai/gpt-oss-120b"
    assert call_args[2] == "https://api.groq.com/openai/v1"
    assert call_args[3] == "gsk_test_groq_api_key_12345"

    # Ensure key_rotator was NOT called for critic
    mock_rotator.get_active_key.assert_not_called()
    mock_rotator.record_success.assert_not_called()
    mock_rotator.report_rate_limit.assert_not_called()


@patch("httpx.Client.post")
def test_execute_provider_request_groq_formatting(mock_post):
    from agent.llm import execute_provider_request
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps({"status": "ok"})}}]
    }
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    messages = [{"role": "user", "content": "hello"}]
    res = execute_provider_request(
        provider="groq",
        model="openai/gpt-oss-120b",
        base_url="https://api.groq.com/openai/v1",
        api_key="gsk_test_key_abc1234567890",
        messages=messages
    )

    assert res == json.dumps({"status": "ok"})
    mock_post.assert_called_once()
    post_url = mock_post.call_args[0][0]
    post_kwargs = mock_post.call_args[1]

    assert post_url == "https://api.groq.com/openai/v1/chat/completions"
    assert post_kwargs["headers"] == {"Authorization": "Bearer gsk_test_key_abc1234567890"}
    assert post_kwargs["json"]["model"] == "openai/gpt-oss-120b"
    assert post_kwargs["json"]["response_format"] == {"type": "json_object"}


def test_groq_key_secret_scrubbing():
    groq_secret = "gsk_1234567890abcdef1234567890"
    dirty = f"Error calling api with key {groq_secret}"
    cleaned = scrub_secrets(dirty)
    assert groq_secret not in cleaned
    assert "[REDACTED_SECRET]" in cleaned or "[REDACTED_API_KEY]" in cleaned

