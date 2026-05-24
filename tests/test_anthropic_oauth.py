"""Tests for the Anthropic OAuth adapter (no network — translation logic only)."""

from __future__ import annotations

import json
from pathlib import Path

from gtm_os.engine import anthropic_oauth as ao


def test_split_oauth_model():
    assert ao.is_oauth_model("anthropic_oauth/claude-sonnet-4-5")
    assert not ao.is_oauth_model("anthropic/claude-sonnet-4-5")
    assert ao.split_oauth_model("anthropic_oauth/claude-sonnet-4-5") == "claude-sonnet-4-5"


def test_translate_tools_to_anthropic():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "memory_save",
                "description": "save",
                "parameters": {
                    "type": "object",
                    "properties": {"content": {"type": "string"}},
                    "required": ["content"],
                },
            },
        }
    ]
    out = ao._translate_tools_to_anthropic(tools)
    assert out and out[0]["name"] == "memory_save"
    assert out[0]["input_schema"]["properties"] == {"content": {"type": "string"}}
    assert ao._translate_tools_to_anthropic(None) is None
    assert ao._translate_tools_to_anthropic([]) is None


def test_translate_messages_round_trip():
    messages = [
        {"role": "system", "content": "be terse"},
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": "running tool",
            "tool_calls": [
                {
                    "id": "tc_1",
                    "type": "function",
                    "function": {
                        "name": "memory_search",
                        "arguments": json.dumps({"query": "x"}),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "tc_1",
            "content": json.dumps({"results": []}),
        },
        {"role": "user", "content": "go on"},
    ]
    system, anth = ao._translate_messages_to_anthropic(messages)
    assert system == "be terse"
    assert len(anth) == 4  # user / assistant / user(tool_result) / user
    assistant = anth[1]
    assert assistant["role"] == "assistant"
    blocks = assistant["content"]
    assert any(b["type"] == "text" for b in blocks)
    tool_use = next(b for b in blocks if b["type"] == "tool_use")
    assert tool_use["name"] == "memory_search"
    assert tool_use["input"] == {"query": "x"}
    tool_result = anth[2]
    assert tool_result["role"] == "user"
    assert tool_result["content"][0]["type"] == "tool_result"


def test_read_credentials_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CLAUDE_CREDENTIALS_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setattr(ao, "_DEFAULT_CRED_PATHS", ())
    assert ao.read_credentials() is None


def test_read_credentials_present(monkeypatch, tmp_path: Path):
    p = tmp_path / ".credentials.json"
    p.write_text(
        json.dumps(
            {
                "claudeAiOauth": {
                    "accessToken": "sk-ant-oat01-abc",
                    "refreshToken": "sk-ant-ort01-xyz",
                    "expiresAt": 9999999999999,
                    "subscriptionType": "max",
                }
            }
        )
    )
    monkeypatch.setenv("CLAUDE_CREDENTIALS_PATH", str(p))
    creds = ao.read_credentials()
    assert creds is not None
    assert creds.access_token == "sk-ant-oat01-abc"
    assert creds.refresh_token == "sk-ant-ort01-xyz"
    assert creds.subscription_type == "max"
    assert ao.is_expired(creds) is False


def test_expired_detection():
    creds = ao.OAuthCredentials(
        access_token="a", refresh_token="b", expires_at_ms=1, subscription_type=None
    )
    assert ao.is_expired(creds) is True
    creds2 = ao.OAuthCredentials(
        access_token="a", refresh_token="b", expires_at_ms=None, subscription_type=None
    )
    assert ao.is_expired(creds2) is False
