"""Anthropic OAuth adapter — use a Claude Code subscription via the terminal-auth'd token.

When the user has run `claude login`, Claude Code writes an OAuth token to
~/.claude/.credentials.json. We can use that token as a Bearer credential against
api.anthropic.com instead of requiring a separate console.anthropic.com API key.

This module is intentionally narrow: it reads the token, refreshes it when expired,
and provides a litellm-compatible completion / stream interface for the harness.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

ANTHROPIC_OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
ANTHROPIC_OAUTH_REFRESH_URL = "https://console.anthropic.com/v1/oauth/token"
ANTHROPIC_API_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_BETA_HEADER = "oauth-2025-04-20"
ANTHROPIC_VERSION_HEADER = "2023-06-01"

# Default credential locations to try, in priority order.
_DEFAULT_CRED_PATHS = (
    Path.home() / ".claude" / ".credentials.json",
    Path.home() / ".config" / "anthropic" / "claude" / ".credentials.json",
    Path.home() / "AppData" / "Roaming" / "Claude" / ".credentials.json",
)


@dataclass
class OAuthCredentials:
    access_token: str
    refresh_token: str | None
    expires_at_ms: int | None
    subscription_type: str | None = None
    source_path: Path | None = None


def credentials_path() -> Path | None:
    """Return the first existing credentials file."""
    explicit = os.environ.get("CLAUDE_CREDENTIALS_PATH")
    if explicit:
        p = Path(explicit).expanduser()
        if p.exists():
            return p
    for p in _DEFAULT_CRED_PATHS:
        if p.exists():
            return p
    return None


def _read_keychain_credentials() -> dict[str, Any] | None:
    """Read Claude Code credentials from macOS Keychain (Claude Code 2.1+)."""
    if platform.system() != "Darwin":
        return None
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return json.loads(result.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def _parse_credentials_payload(raw: dict[str, Any], source: Path | None = None) -> OAuthCredentials | None:
    """Parse a credentials JSON object into OAuthCredentials."""
    payload = raw.get("claudeAiOauth") or raw.get("oauth") or raw
    access = payload.get("accessToken") or payload.get("access_token")
    if not access:
        return None
    refresh = payload.get("refreshToken") or payload.get("refresh_token")
    expires = payload.get("expiresAt") or payload.get("expires_at")
    if isinstance(expires, str):
        try:
            expires = int(expires)
        except ValueError:
            expires = None
    return OAuthCredentials(
        access_token=access,
        refresh_token=refresh,
        expires_at_ms=expires,
        subscription_type=payload.get("subscriptionType") or payload.get("subscription_type"),
        source_path=source,
    )


def read_credentials() -> OAuthCredentials | None:
    # Try file-based credentials first.
    p = credentials_path()
    if p is not None:
        try:
            raw = json.loads(p.read_text())
            creds = _parse_credentials_payload(raw, source=p)
            if creds:
                return creds
        except (OSError, json.JSONDecodeError):
            pass

    # Fall back to macOS Keychain (Claude Code 2.1+).
    keychain_raw = _read_keychain_credentials()
    if keychain_raw:
        return _parse_credentials_payload(keychain_raw, source=None)

    return None


def is_expired(creds: OAuthCredentials, *, leeway_seconds: int = 60) -> bool:
    if not creds.expires_at_ms:
        return False  # unknown expiry — assume valid
    now_ms = int(time.time() * 1000)
    return creds.expires_at_ms <= now_ms + leeway_seconds * 1000


async def refresh_credentials(creds: OAuthCredentials) -> OAuthCredentials | None:
    if not creds.refresh_token:
        return None
    body = {
        "grant_type": "refresh_token",
        "refresh_token": creds.refresh_token,
        "client_id": ANTHROPIC_OAUTH_CLIENT_ID,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(ANTHROPIC_OAUTH_REFRESH_URL, json=body)
        if resp.status_code != 200:
            return None
        data = resp.json()
    new_access = data.get("access_token") or data.get("accessToken")
    new_refresh = data.get("refresh_token") or data.get("refreshToken") or creds.refresh_token
    expires_in = data.get("expires_in") or data.get("expiresIn")
    expires_at_ms = (
        int(time.time() * 1000) + int(expires_in) * 1000 if expires_in else creds.expires_at_ms
    )
    if not new_access:
        return None

    updated = OAuthCredentials(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_at_ms=expires_at_ms,
        subscription_type=creds.subscription_type,
        source_path=creds.source_path,
    )

    # Best-effort write back so subsequent runs benefit.
    if creds.source_path:
        try:
            raw = json.loads(creds.source_path.read_text())
            payload_key = (
                "claudeAiOauth" if "claudeAiOauth" in raw else ("oauth" if "oauth" in raw else None)
            )
            if payload_key:
                raw[payload_key]["accessToken"] = new_access
                raw[payload_key]["refreshToken"] = new_refresh
                if expires_in:
                    raw[payload_key]["expiresAt"] = expires_at_ms
                creds.source_path.write_text(json.dumps(raw, indent=2))
        except (OSError, json.JSONDecodeError):
            pass

    return updated


async def get_valid_token() -> OAuthCredentials | None:
    creds = read_credentials()
    if creds is None:
        return None
    if is_expired(creds):
        refreshed = await refresh_credentials(creds)
        if refreshed is not None:
            return refreshed
        return creds  # try anyway; let the API tell us
    return creds


def is_oauth_model(model: str) -> bool:
    return model.startswith("anthropic_oauth/")


def split_oauth_model(model: str) -> str:
    return model.removeprefix("anthropic_oauth/")


# ---------- Translation between OpenAI-style and Anthropic-style ----------


def _translate_tools_to_anthropic(
    tools: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    out: list[dict[str, Any]] = []
    for t in tools:
        fn = t.get("function") or t
        out.append(
            {
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return out


def _translate_messages_to_anthropic(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    """Pull out the system prompt and convert messages to Anthropic message format.

    Tool results become user messages with `tool_result` content blocks.
    Assistant tool calls become assistant messages with `tool_use` content blocks.
    """
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            content = m.get("content") or ""
            if isinstance(content, list):
                content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
            system_parts.append(content)
            continue

        if role == "tool":
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.get("tool_call_id") or m.get("id") or "",
                            "content": m.get("content") or "",
                        }
                    ],
                }
            )
            continue

        if role == "assistant":
            blocks: list[dict[str, Any]] = []
            text = m.get("content")
            if isinstance(text, str) and text:
                blocks.append({"type": "text", "text": text})
            tool_calls = m.get("tool_calls") or []
            for tc in tool_calls:
                fn = tc.get("function") or {}
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id") or "",
                        "name": fn.get("name") or "",
                        "input": args or {},
                    }
                )
            if not blocks:
                blocks = [{"type": "text", "text": ""}]
            out.append({"role": "assistant", "content": blocks})
            continue

        # default → user
        content = m.get("content")
        if isinstance(content, list):
            out.append({"role": "user", "content": content})
        else:
            out.append({"role": "user", "content": content or ""})

    system = "\n\n".join(p for p in system_parts if p) or None
    return system, out


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "anthropic-version": ANTHROPIC_VERSION_HEADER,
        "anthropic-beta": ANTHROPIC_BETA_HEADER,
        "content-type": "application/json",
        # Identify as a Claude Code-style client; Anthropic gates OAuth on this.
        "user-agent": "claude-cli/1.0 (gtm-os)",
    }


def _build_payload(
    *,
    model: str,
    system: str | None,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    temperature: float | None,
    max_tokens: int,
    stream: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
        "stream": stream,
    }
    if system:
        payload["system"] = system
    if temperature is not None:
        payload["temperature"] = temperature
    anth_tools = _translate_tools_to_anthropic(tools)
    if anth_tools:
        payload["tools"] = anth_tools
    return payload


async def oauth_completion(
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    temperature: float | None,
    max_tokens: int,
    timeout: int = 120,
    max_retries: int = 5,
) -> dict[str, Any]:
    """Non-streaming completion. Returns an OpenAI-shaped message dict.

    Shape: {"role": "assistant", "content": "...", "tool_calls": [...], "usage": {...}}
    Retries on 429 (rate limit) and 529 (overloaded) with exponential backoff.
    """
    import asyncio

    creds = await get_valid_token()
    if creds is None:
        raise RuntimeError(
            "Anthropic OAuth: no Claude Code credentials found. Run `claude login` first."
        )

    system, anth_messages = _translate_messages_to_anthropic(messages)
    payload = _build_payload(
        model=split_oauth_model(model),
        system=system,
        messages=anth_messages,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )

    last_resp = None
    for attempt in range(max_retries + 1):
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                ANTHROPIC_API_MESSAGES_URL,
                headers=_headers(creds.access_token),
                json=payload,
            )
        if resp.status_code == 200:
            break
        if resp.status_code in (429, 529) and attempt < max_retries:
            retry_after = resp.headers.get("retry-after")
            wait = float(retry_after) if retry_after else min(2 ** attempt * 2, 60)
            await asyncio.sleep(wait)
            last_resp = resp
            continue
        raise RuntimeError(f"Anthropic OAuth call failed ({resp.status_code}): {resp.text[:500]}")
    else:
        raise RuntimeError(
            f"Anthropic OAuth rate limited after {max_retries} retries "
            f"({last_resp.status_code if last_resp else 'unknown'}): "
            f"{last_resp.text[:500] if last_resp else ''}"
        )
    data = resp.json()

    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for block in data.get("content", []):
        btype = block.get("type")
        if btype == "text":
            text_parts.append(block.get("text", ""))
        elif btype == "tool_use":
            tool_calls.append(
                {
                    "id": block.get("id"),
                    "type": "function",
                    "function": {
                        "name": block.get("name"),
                        "arguments": json.dumps(block.get("input") or {}),
                    },
                }
            )
    usage = data.get("usage") or {}
    return {
        "role": "assistant",
        "content": "".join(text_parts),
        "tool_calls": tool_calls or None,
        "usage": {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        },
    }


async def oauth_stream(
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    temperature: float | None,
    max_tokens: int,
    timeout: int = 120,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream completion. Yields {"type": "token", "text": "..."} for each delta and a
    final {"type": "final", "message": {...}} matching the non-streaming shape."""
    creds = await get_valid_token()
    if creds is None:
        raise RuntimeError(
            "Anthropic OAuth: no Claude Code credentials found. Run `claude login` first."
        )

    system, anth_messages = _translate_messages_to_anthropic(messages)
    payload = _build_payload(
        model=split_oauth_model(model),
        system=system,
        messages=anth_messages,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )

    text_buf: list[str] = []
    current_tool: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] = []
    input_tokens = 0
    output_tokens = 0

    async with (
        httpx.AsyncClient(timeout=timeout) as client,
        client.stream(
            "POST",
            ANTHROPIC_API_MESSAGES_URL,
            headers=_headers(creds.access_token),
            json=payload,
        ) as resp,
    ):
        if resp.status_code != 200:
            body = (await resp.aread()).decode("utf-8", "replace")
            raise RuntimeError(f"Anthropic OAuth stream failed ({resp.status_code}): {body[:500]}")

        current_event: str | None = None
        async for line in resp.aiter_lines():
            if not line:
                current_event = None
                continue
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
                continue
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw or raw == "[DONE]":
                continue
            try:
                evt = json.loads(raw)
            except json.JSONDecodeError:
                continue

            etype = evt.get("type") or current_event
            if etype == "content_block_start":
                block = evt.get("content_block") or {}
                if block.get("type") == "tool_use":
                    current_tool = {
                        "id": block.get("id"),
                        "type": "function",
                        "function": {
                            "name": block.get("name"),
                            "arguments": "",
                        },
                    }
            elif etype == "content_block_delta":
                delta = evt.get("delta") or {}
                if delta.get("type") == "text_delta":
                    token = delta.get("text", "")
                    if token:
                        text_buf.append(token)
                        yield {"type": "token", "text": token}
                elif delta.get("type") == "input_json_delta" and current_tool is not None:
                    current_tool["function"]["arguments"] += delta.get("partial_json", "")
            elif etype == "content_block_stop":
                if current_tool is not None:
                    tool_calls.append(current_tool)
                    current_tool = None
            elif etype == "message_delta":
                usage = evt.get("usage") or {}
                output_tokens = usage.get("output_tokens", output_tokens)
            elif etype == "message_start":
                msg = evt.get("message") or {}
                usage = msg.get("usage") or {}
                input_tokens = usage.get("input_tokens", input_tokens)

    yield {
        "type": "final",
        "message": {
            "role": "assistant",
            "content": "".join(text_buf),
            "tool_calls": tool_calls or None,
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        },
    }
