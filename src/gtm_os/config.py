"""Load gtm-os.config.yaml, env vars, and defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG: dict[str, Any] = {
    "primitives_dir": "./primitives",
    "data_dir": "./data",
    "server": {"host": "127.0.0.1", "port": 3000},
    "scheduler": {
        "enabled": True,
        "poll_interval_seconds": 60,
        "max_consecutive_failures": 3,
    },
    "llm": {
        "model": "openai/gpt-4o-mini",
        "embedding_model": "openai/text-embedding-3-small",
        "temperature": 0.4,
        "max_tokens": 4096,
        "request_timeout_seconds": 120,
    },
    "budgets": {
        "default_experiment_token_budget": 200_000,
        "context_soft_trim_ratio": 0.30,
        "context_hard_clear_ratio": 0.50,
    },
}


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 3000


@dataclass
class SchedulerConfig:
    enabled: bool = True
    poll_interval_seconds: int = 60
    max_consecutive_failures: int = 3


@dataclass
class LLMConfig:
    model: str = "openai/gpt-4o-mini"
    embedding_model: str = "openai/text-embedding-3-small"
    temperature: float = 0.4
    max_tokens: int = 4096
    request_timeout_seconds: int = 120
    api_key: str | None = None


@dataclass
class BudgetConfig:
    default_experiment_token_budget: int = 200_000
    context_soft_trim_ratio: float = 0.30
    context_hard_clear_ratio: float = 0.50


@dataclass
class Config:
    """Resolved GTM-OS configuration."""

    project_root: Path
    primitives_dir: Path
    data_dir: Path
    db_path: Path
    server: ServerConfig = field(default_factory=ServerConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    budgets: BudgetConfig = field(default_factory=BudgetConfig)
    composio_api_key: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def find_project_root(start: Path | None = None) -> Path:
    """Walk up from `start` (default cwd) looking for gtm-os.config.yaml or pyproject.toml."""
    cur = (start or Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        if (parent / "gtm-os.config.yaml").exists():
            return parent
        if (parent / "pyproject.toml").exists() and (parent / "primitives").exists():
            return parent
    return cur


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from `config_path` or auto-discover."""
    root = config_path.parent if config_path else find_project_root()
    raw: dict[str, Any] = {}
    path = config_path or (root / "gtm-os.config.yaml")
    if path.exists():
        with path.open() as f:
            raw = yaml.safe_load(f) or {}

    merged = _deep_merge(DEFAULT_CONFIG, raw)

    primitives_dir = (root / merged["primitives_dir"]).resolve()
    data_dir = (root / merged["data_dir"]).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    llm_raw = merged.get("llm", {})
    llm = LLMConfig(
        model=llm_raw.get("model", "openai/gpt-4o-mini"),
        embedding_model=llm_raw.get("embedding_model", "openai/text-embedding-3-small"),
        temperature=float(llm_raw.get("temperature", 0.4)),
        max_tokens=int(llm_raw.get("max_tokens", 4096)),
        request_timeout_seconds=int(llm_raw.get("request_timeout_seconds", 120)),
        api_key=llm_raw.get("api_key") or _resolve_llm_api_key(llm_raw.get("model", "")),
    )

    server_raw = merged.get("server", {})
    server = ServerConfig(
        host=server_raw.get("host", "127.0.0.1"),
        port=int(server_raw.get("port", 3000)),
    )

    sched_raw = merged.get("scheduler", {})
    scheduler = SchedulerConfig(
        enabled=bool(sched_raw.get("enabled", True)),
        poll_interval_seconds=int(sched_raw.get("poll_interval_seconds", 60)),
        max_consecutive_failures=int(sched_raw.get("max_consecutive_failures", 3)),
    )

    budgets_raw = merged.get("budgets", {})
    budgets = BudgetConfig(
        default_experiment_token_budget=int(
            budgets_raw.get("default_experiment_token_budget", 200_000)
        ),
        context_soft_trim_ratio=float(budgets_raw.get("context_soft_trim_ratio", 0.30)),
        context_hard_clear_ratio=float(budgets_raw.get("context_hard_clear_ratio", 0.50)),
    )

    composio_key = merged.get("api_keys", {}).get("composio") if isinstance(
        merged.get("api_keys"), dict
    ) else None
    composio_key = composio_key or os.environ.get("COMPOSIO_API_KEY")

    return Config(
        project_root=root,
        primitives_dir=primitives_dir,
        data_dir=data_dir,
        db_path=data_dir / "gtm-os.db",
        server=server,
        scheduler=scheduler,
        llm=llm,
        budgets=budgets,
        composio_api_key=composio_key,
        raw=merged,
    )


def _resolve_llm_api_key(model: str) -> str | None:
    """Pick the env var that matches a litellm-style model string."""
    if not model:
        return None
    prefix = model.split("/", 1)[0].lower()
    env_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "anthropic_oauth": None,  # uses Claude Code's OAuth token; no env var needed.
        "groq": "GROQ_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "google": "GOOGLE_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "azure": "AZURE_API_KEY",
        "ollama": None,
    }
    env = env_map.get(prefix)
    if env is None:
        return None
    return os.environ.get(env)
