"""Integrations REST API — keys, app catalog, connected accounts."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

from ...engine.composio_tools import ComposioIntegration
from ...engine.cua_tools import CUAIntegration
from ...engine.pipedream_tools import PipedreamIntegration

router = APIRouter()
logger = logging.getLogger(__name__)

COMPOSIO_API = "https://backend.composio.dev"


class IntegrationStatus(BaseModel):
    name: str
    configured: bool
    has_env_key: bool
    docs_url: str
    description: str


class IntegrationKeyUpdate(BaseModel):
    composio_api_key: str | None = None
    pipedream_api_key: str | None = None
    cua_api_key: str | None = None


class ToolKeyStatus(BaseModel):
    name: str
    label: str
    env_var: str
    configured: bool
    masked_key: str
    required_by: list[str]
    description: str


class ToolKeyUpdate(BaseModel):
    serper_api_key: str | None = None
    brave_search_api_key: str | None = None
    youtube_api_key: str | None = None


class ModelKeyUpdate(BaseModel):
    deepseek_api_key: str | None = None
    moonshot_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    groq_api_key: str | None = None
    google_api_key: str | None = None


class ModelConfigUpdate(BaseModel):
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


class ConnectRequest(BaseModel):
    toolkit_slug: str
    user_id: str = "default"
    redirect_url: str | None = None


class DisconnectRequest(BaseModel):
    connected_account_id: str


def _env_file_path(request: Request) -> Path:
    gtm = request.app.state.gtm
    return gtm.config.project_root / ".env"


def _mask_key(key: str | None) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    return key[:4] + "…" + key[-4:]


@router.get("/integrations")
async def get_integrations(request: Request) -> dict[str, Any]:
    gtm = request.app.state.gtm
    composio: ComposioIntegration = gtm.composio
    pipedream: PipedreamIntegration = gtm.pipedream
    cua: CUAIntegration = gtm.cua

    return {
        "integrations": [
            {
                "name": "composio",
                "label": "Composio",
                "configured": composio.configured,
                "masked_key": _mask_key(composio.api_key),
                "has_env_key": bool(os.environ.get("COMPOSIO_API_KEY")),
                "env_var": "COMPOSIO_API_KEY",
                "docs_url": "https://docs.composio.dev",
                "dashboard_url": "https://app.composio.dev",
                "description": (
                    "Connect 250+ apps (Gmail, Apollo, Slack, HubSpot, etc.) "
                    "for real tool discovery and execution."
                ),
            },
            {
                "name": "pipedream",
                "label": "Pipedream",
                "configured": pipedream.configured,
                "masked_key": _mask_key(pipedream.api_key),
                "has_env_key": bool(os.environ.get("PIPEDREAM_API_KEY")),
                "env_var": "PIPEDREAM_API_KEY",
                "docs_url": "https://pipedream.com/docs",
                "dashboard_url": "https://pipedream.com/apps",
                "description": (
                    "2,400+ app integrations with pre-built actions. "
                    "Run workflows and actions via API."
                ),
            },
            {
                "name": "cua",
                "label": "CUA (Computer-Use Agent)",
                "configured": cua.configured,
                "masked_key": _mask_key(cua.api_key),
                "has_env_key": bool(os.environ.get("CUA_API_KEY")),
                "env_var": "CUA_API_KEY",
                "docs_url": "https://docs.cua.ai",
                "dashboard_url": "https://cua.ai",
                "description": (
                    "Give agents their own virtual computer for browser/GUI automation. "
                    "Navigate LinkedIn, fill CRM forms, scrape dynamic pages."
                ),
            },
        ]
    }


@router.put("/integrations/keys")
async def update_integration_keys(request: Request, body: IntegrationKeyUpdate) -> dict[str, Any]:
    """Persist API keys to .env and hot-reload integrations in memory."""
    gtm = request.app.state.gtm
    env_path = _env_file_path(request)
    updated: list[str] = []

    # Read existing .env lines (preserve other keys).
    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    key_updates: dict[str, str | None] = {}
    if body.composio_api_key is not None:
        key_updates["COMPOSIO_API_KEY"] = body.composio_api_key
    if body.pipedream_api_key is not None:
        key_updates["PIPEDREAM_API_KEY"] = body.pipedream_api_key
    if body.cua_api_key is not None:
        key_updates["CUA_API_KEY"] = body.cua_api_key

    # Build new .env content.
    new_lines: list[str] = []
    seen_keys: set[str] = set()
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        eq_idx = stripped.find("=")
        if eq_idx == -1:
            new_lines.append(line)
            continue
        env_key = stripped[:eq_idx].strip()
        if env_key in key_updates:
            val = key_updates[env_key]
            if val:  # non-empty → write it
                new_lines.append(f"{env_key}={val}")
            # else: omit the line (key was cleared)
            seen_keys.add(env_key)
        else:
            new_lines.append(line)

    # Append any keys not already in the file.
    for env_key, val in key_updates.items():
        if env_key not in seen_keys and val:
            new_lines.append(f"{env_key}={val}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # Hot-reload: update the in-memory integrations.
    if body.composio_api_key is not None:
        new_key = body.composio_api_key or None
        os.environ["COMPOSIO_API_KEY"] = body.composio_api_key or ""
        gtm.composio = ComposioIntegration(new_key)
        gtm.runner.composio = gtm.composio
        gtm.config.composio_api_key = new_key
        updated.append("composio")

    if body.pipedream_api_key is not None:
        new_key = body.pipedream_api_key or None
        os.environ["PIPEDREAM_API_KEY"] = body.pipedream_api_key or ""
        gtm.pipedream = PipedreamIntegration(new_key)
        gtm.runner.pipedream = gtm.pipedream
        gtm.config.pipedream_api_key = new_key
        updated.append("pipedream")

    if body.cua_api_key is not None:
        new_key = body.cua_api_key or None
        os.environ["CUA_API_KEY"] = body.cua_api_key or ""
        gtm.cua = CUAIntegration(new_key)
        gtm.runner.cua = gtm.cua
        gtm.config.cua_api_key = new_key
        updated.append("cua")

    logger.info("Integration keys updated: %s", ", ".join(updated))
    return {"ok": True, "updated": updated}


# ---------------------------------------------------------------------------
# Research Tool API Keys
# ---------------------------------------------------------------------------

_TOOL_KEY_DEFS: list[dict[str, Any]] = [
    {
        "name": "serper",
        "label": "Serper.dev",
        "env_var": "SERPER_API_KEY",
        "required_by": ["web_search", "search_prospects"],
        "description": "Google Search API for market research and prospect discovery.",
    },
    {
        "name": "brave",
        "label": "Brave Search",
        "env_var": "BRAVE_SEARCH_API_KEY",
        "required_by": ["web_search", "search_prospects"],
        "description": "Alternative search API (used if Serper is not configured).",
    },
    {
        "name": "youtube",
        "label": "YouTube Data API",
        "env_var": "YOUTUBE_API_KEY",
        "required_by": ["youtube_search"],
        "description": "YouTube channel and video search for prospect content personalization.",
    },
]


@router.get("/integrations/tool-keys")
async def get_tool_keys() -> dict[str, Any]:
    """Return status of research tool API keys."""
    tools = []
    for defn in _TOOL_KEY_DEFS:
        env_val = os.environ.get(defn["env_var"], "")
        tools.append({
            **defn,
            "configured": bool(env_val),
            "masked_key": _mask_key(env_val) if env_val else "",
        })

    # Also report which tools work without keys.
    no_key_tools = [
        {"name": "browser_fetch", "label": "Browser Fetch", "status": "always_available"},
        {"name": "scrape_website", "label": "Web Scraper", "status": "always_available"},
        {"name": "csv_search", "label": "CSV Parser", "status": "always_available"},
        {"name": "pdf_search", "label": "PDF Parser", "status": "always_available"},
        {"name": "structured_extract", "label": "Structured Extract (TrustCall)", "status": "always_available"},
        {"name": "patch_experiment_config", "label": "Patch Config (TrustCall)", "status": "always_available"},
    ]

    return {"tool_keys": tools, "no_key_tools": no_key_tools}


@router.put("/integrations/tool-keys")
async def update_tool_keys(request: Request, body: ToolKeyUpdate) -> dict[str, Any]:
    """Persist research tool API keys to .env and hot-reload in memory."""
    env_path = _env_file_path(request)
    updated: list[str] = []

    key_updates: dict[str, str | None] = {}
    if body.serper_api_key is not None:
        key_updates["SERPER_API_KEY"] = body.serper_api_key
    if body.brave_search_api_key is not None:
        key_updates["BRAVE_SEARCH_API_KEY"] = body.brave_search_api_key
    if body.youtube_api_key is not None:
        key_updates["YOUTUBE_API_KEY"] = body.youtube_api_key

    if not key_updates:
        return {"ok": True, "updated": []}

    # Read existing .env lines.
    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    # Build new .env content.
    new_lines: list[str] = []
    seen_keys: set[str] = set()
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        eq_idx = stripped.find("=")
        if eq_idx == -1:
            new_lines.append(line)
            continue
        env_key = stripped[:eq_idx].strip()
        if env_key in key_updates:
            val = key_updates[env_key]
            if val:
                new_lines.append(f"{env_key}={val}")
            seen_keys.add(env_key)
        else:
            new_lines.append(line)

    for env_key, val in key_updates.items():
        if env_key not in seen_keys and val:
            new_lines.append(f"{env_key}={val}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # Hot-reload environment variables.
    for env_key, val in key_updates.items():
        if val:
            os.environ[env_key] = val
            updated.append(env_key)
        else:
            os.environ.pop(env_key, None)
            updated.append(env_key)

    logger.info("Tool keys updated: %s", ", ".join(updated))
    return {"ok": True, "updated": updated}


# ---------------------------------------------------------------------------
# LLM Model Provider Keys
# ---------------------------------------------------------------------------

_MODEL_KEY_DEFS: list[dict[str, Any]] = [
    {
        "name": "deepseek",
        "label": "DeepSeek",
        "env_var": "DEEPSEEK_API_KEY",
        "models": ["deepseek/deepseek-chat", "deepseek/deepseek-reasoner"],
        "description": "DeepSeek AI models — high quality, affordable reasoning and chat.",
        "docs_url": "https://platform.deepseek.com",
    },
    {
        "name": "moonshot",
        "label": "Kimi (Moonshot AI)",
        "env_var": "MOONSHOT_API_KEY",
        "models": [
            "moonshot/moonshot-v1-8k",
            "moonshot/moonshot-v1-32k",
            "moonshot/moonshot-v1-128k",
        ],
        "description": "Kimi by Moonshot AI — strong multilingual models with large context windows.",
        "docs_url": "https://platform.moonshot.cn",
    },
    {
        "name": "openai",
        "label": "OpenAI",
        "env_var": "OPENAI_API_KEY",
        "models": ["openai/gpt-4o", "openai/gpt-4o-mini", "openai/o1", "openai/o3-mini"],
        "description": "OpenAI GPT models — GPT-4o, o1, o3-mini.",
        "docs_url": "https://platform.openai.com",
    },
    {
        "name": "anthropic",
        "label": "Anthropic",
        "env_var": "ANTHROPIC_API_KEY",
        "models": [
            "anthropic/claude-sonnet-4-20250514",
            "anthropic/claude-opus-4-20250514",
            "anthropic/claude-haiku-4-5",
        ],
        "description": "Anthropic Claude models — Sonnet 4, Opus 4, Haiku 4.5.",
        "docs_url": "https://console.anthropic.com",
    },
    {
        "name": "groq",
        "label": "Groq",
        "env_var": "GROQ_API_KEY",
        "models": ["groq/llama-3.3-70b-versatile", "groq/meta-llama/llama-4-scout-17b-16e-instruct"],
        "description": "Groq inference — ultra-fast LLM inference for open models.",
        "docs_url": "https://console.groq.com",
    },
    {
        "name": "google",
        "label": "Google (Gemini)",
        "env_var": "GOOGLE_API_KEY",
        "models": ["gemini/gemini-2.5-pro", "gemini/gemini-2.5-flash"],
        "description": "Google Gemini models via AI Studio or Vertex.",
        "docs_url": "https://aistudio.google.com",
    },
]


@router.get("/integrations/model-keys")
async def get_model_keys(request: Request) -> dict[str, Any]:
    """Return status of LLM provider API keys and available models."""
    gtm = request.app.state.gtm
    providers = []
    all_models: list[dict[str, str]] = []
    for defn in _MODEL_KEY_DEFS:
        env_val = os.environ.get(defn["env_var"], "")
        configured = bool(env_val)
        providers.append({
            "name": defn["name"],
            "label": defn["label"],
            "env_var": defn["env_var"],
            "configured": configured,
            "masked_key": _mask_key(env_val) if env_val else "",
            "models": defn["models"],
            "description": defn["description"],
            "docs_url": defn["docs_url"],
        })
        if configured:
            for m in defn["models"]:
                all_models.append({"id": m, "provider": defn["label"]})
    return {
        "providers": providers,
        "available_models": all_models,
        "current_model": gtm.config.llm.model,
        "current_temperature": gtm.config.llm.temperature,
        "current_max_tokens": gtm.config.llm.max_tokens,
    }


@router.put("/integrations/model-keys")
async def update_model_keys(request: Request, body: ModelKeyUpdate) -> dict[str, Any]:
    """Persist LLM provider API keys to .env and hot-reload."""
    env_path = _env_file_path(request)
    updated: list[str] = []

    key_updates: dict[str, str | None] = {}
    if body.deepseek_api_key is not None:
        key_updates["DEEPSEEK_API_KEY"] = body.deepseek_api_key
    if body.moonshot_api_key is not None:
        key_updates["MOONSHOT_API_KEY"] = body.moonshot_api_key
    if body.openai_api_key is not None:
        key_updates["OPENAI_API_KEY"] = body.openai_api_key
    if body.anthropic_api_key is not None:
        key_updates["ANTHROPIC_API_KEY"] = body.anthropic_api_key
    if body.groq_api_key is not None:
        key_updates["GROQ_API_KEY"] = body.groq_api_key
    if body.google_api_key is not None:
        key_updates["GOOGLE_API_KEY"] = body.google_api_key

    if not key_updates:
        return {"ok": True, "updated": []}

    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    new_lines: list[str] = []
    seen_keys: set[str] = set()
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        eq_idx = stripped.find("=")
        if eq_idx == -1:
            new_lines.append(line)
            continue
        env_key = stripped[:eq_idx].strip()
        if env_key in key_updates:
            val = key_updates[env_key]
            if val:
                new_lines.append(f"{env_key}={val}")
            seen_keys.add(env_key)
        else:
            new_lines.append(line)

    for env_key, val in key_updates.items():
        if env_key not in seen_keys and val:
            new_lines.append(f"{env_key}={val}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    for env_key, val in key_updates.items():
        if val:
            os.environ[env_key] = val
            updated.append(env_key)
        else:
            os.environ.pop(env_key, None)
            updated.append(env_key)

    # Hot-reload: re-resolve the LLM API key for the current model.
    gtm = request.app.state.gtm
    from ...config import _resolve_llm_api_key

    new_api_key = _resolve_llm_api_key(gtm.config.llm.model)
    if new_api_key:
        gtm.config.llm.api_key = new_api_key

    logger.info("Model keys updated: %s", ", ".join(updated))
    return {"ok": True, "updated": updated}


@router.put("/integrations/model-config")
async def update_model_config(request: Request, body: ModelConfigUpdate) -> dict[str, Any]:
    """Switch the active model or adjust LLM parameters. Hot-reloads immediately."""
    gtm = request.app.state.gtm
    changes: list[str] = []

    if body.model is not None and body.model != gtm.config.llm.model:
        gtm.config.llm.model = body.model
        from ...config import _resolve_llm_api_key

        new_api_key = _resolve_llm_api_key(body.model)
        if new_api_key:
            gtm.config.llm.api_key = new_api_key
        changes.append(f"model={body.model}")

    if body.temperature is not None:
        gtm.config.llm.temperature = body.temperature
        changes.append(f"temperature={body.temperature}")

    if body.max_tokens is not None:
        gtm.config.llm.max_tokens = body.max_tokens
        changes.append(f"max_tokens={body.max_tokens}")

    logger.info("Model config updated: %s", ", ".join(changes))
    return {
        "ok": True,
        "changes": changes,
        "model": gtm.config.llm.model,
        "temperature": gtm.config.llm.temperature,
        "max_tokens": gtm.config.llm.max_tokens,
    }


# ---------------------------------------------------------------------------
# Composio App Catalog + Connected Accounts
# ---------------------------------------------------------------------------

def _composio_headers(api_key: str) -> dict[str, str]:
    return {"x-api-key": api_key, "Content-Type": "application/json"}


@router.get("/integrations/apps")
async def list_apps(
    request: Request,
    search: str = "",
    category: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """Return available Composio toolkits (app catalog)."""
    gtm = request.app.state.gtm
    composio: ComposioIntegration = gtm.composio
    if not composio.api_key:
        return {"apps": [], "error": "composio_not_configured"}

    params: dict[str, Any] = {
        "limit": min(limit, 100),
        "sort_by": "usage",
    }
    if search:
        params["search"] = search
    if category:
        params["category"] = category

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{COMPOSIO_API}/api/v3/toolkits",
                headers=_composio_headers(composio.api_key),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        # Composio v3 may wrap in "items", or return a bare list, or use "toolkits"
        if isinstance(data, list):
            items = data
        else:
            items = data.get("items") or data.get("toolkits") or data.get("tools") or []
        apps = [
            {
                "slug": t.get("slug") or t.get("key") or t.get("appId") or "",
                "name": t.get("name") or t.get("display_name") or t.get("slug") or "",
                "description": t.get("description") or "",
                "logo": t.get("logo") or t.get("icon") or t.get("meta", {}).get("logo", "") if isinstance(t, dict) else "",
                "categories": t.get("categories") or [],
                "auth_schemes": [
                    (s.get("type", "") if isinstance(s, dict) else str(s))
                    for s in (t.get("auth_schemes") or t.get("authSchemes") or [])
                ],
            }
            for t in items
            if isinstance(t, dict)
        ]
        return {"apps": apps}
    except httpx.HTTPStatusError as exc:
        logger.warning("Composio toolkits API error: %s", exc)
        return {"apps": [], "error": f"api_error_{exc.response.status_code}"}
    except Exception as exc:
        logger.exception("Composio toolkits list failed")
        return {"apps": [], "error": str(exc)}


@router.get("/integrations/connections")
async def list_connections(request: Request) -> dict[str, Any]:
    """Return Composio connected accounts for this project."""
    gtm = request.app.state.gtm
    composio: ComposioIntegration = gtm.composio
    if not composio.api_key:
        return {"connections": [], "error": "composio_not_configured"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{COMPOSIO_API}/api/v3/connected_accounts",
                headers=_composio_headers(composio.api_key),
                params={"limit": 100},
            )
            resp.raise_for_status()
            data = resp.json()

        items = data.get("items", data.get("data", []))
        connections = [
            {
                "id": c.get("id", ""),
                "toolkit_slug": (c.get("toolkit", {}) or {}).get("slug", c.get("appName", "")),
                "toolkit_name": (c.get("toolkit", {}) or {}).get("name", c.get("appName", "")),
                "toolkit_logo": (c.get("toolkit", {}) or {}).get("logo", ""),
                "status": c.get("status", ""),
                "created_at": c.get("createdAt", c.get("created_at", "")),
                "user_id": c.get("member", {}).get("id", "") if c.get("member") else "",
            }
            for c in items
        ]
        return {"connections": connections}
    except httpx.HTTPStatusError as exc:
        logger.warning("Composio connections API error: %s", exc)
        return {"connections": [], "error": f"api_error_{exc.response.status_code}"}
    except Exception as exc:
        logger.exception("Composio connections list failed")
        return {"connections": [], "error": str(exc)}


@router.post("/integrations/connect")
async def initiate_connection(request: Request, body: ConnectRequest) -> dict[str, Any]:
    """Start a Composio connection flow. Returns a redirect URL for OAuth toolkits."""
    gtm = request.app.state.gtm
    composio: ComposioIntegration = gtm.composio
    if not composio.api_key:
        return {"ok": False, "error": "composio_not_configured"}

    try:
        # First, get auth configs for this toolkit to find the right auth_config_id.
        async with httpx.AsyncClient(timeout=30) as client:
            configs_resp = await client.get(
                f"{COMPOSIO_API}/api/v3/auth_configs",
                headers=_composio_headers(composio.api_key),
                params={"toolkit_slug": body.toolkit_slug, "limit": 10},
            )
            configs_resp.raise_for_status()
            configs_data = configs_resp.json()

        configs = configs_data.get("items", [])
        if not configs:
            return {
                "ok": False,
                "error": "no_auth_config",
                "message": f"No auth config found for {body.toolkit_slug}",
            }

        auth_config_id = configs[0].get("id", "")
        auth_scheme = configs[0].get("type", "")

        # Use the link endpoint for OAuth-based connections.
        link_body: dict[str, Any] = {
            "auth_config_id": auth_config_id,
            "user_id": body.user_id,
        }
        if body.redirect_url:
            link_body["callback_url"] = body.redirect_url

        async with httpx.AsyncClient(timeout=30) as client:
            link_resp = await client.post(
                f"{COMPOSIO_API}/api/v3/connected_accounts/link",
                headers=_composio_headers(composio.api_key),
                json=link_body,
            )
            link_resp.raise_for_status()
            link_data = link_resp.json()

        return {
            "ok": True,
            "redirect_url": link_data.get("url", link_data.get("redirect_url", "")),
            "connection_id": link_data.get("id", link_data.get("connectedAccountId", "")),
            "auth_scheme": auth_scheme,
            "status": link_data.get("status", ""),
        }
    except httpx.HTTPStatusError as exc:
        logger.warning("Composio connect error: %s %s", exc, exc.response.text[:500])
        return {"ok": False, "error": f"api_error_{exc.response.status_code}", "detail": exc.response.text[:300]}
    except Exception as exc:
        logger.exception("Composio connect failed")
        return {"ok": False, "error": str(exc)}


@router.delete("/integrations/connections/{connection_id}")
async def disconnect(request: Request, connection_id: str) -> dict[str, Any]:
    """Remove a Composio connected account."""
    gtm = request.app.state.gtm
    composio: ComposioIntegration = gtm.composio
    if not composio.api_key:
        return {"ok": False, "error": "composio_not_configured"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                f"{COMPOSIO_API}/api/v3/connected_accounts/{connection_id}",
                headers=_composio_headers(composio.api_key),
            )
            resp.raise_for_status()
        return {"ok": True, "disconnected": connection_id}
    except httpx.HTTPStatusError as exc:
        logger.warning("Composio disconnect error: %s", exc)
        return {"ok": False, "error": f"api_error_{exc.response.status_code}"}
    except Exception as exc:
        logger.exception("Composio disconnect failed")
        return {"ok": False, "error": str(exc)}
