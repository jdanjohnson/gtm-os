"""Typer CLI — `gtm-os init`, `gtm-os start`, `gtm-os status`."""

from __future__ import annotations

import asyncio
import contextlib
import importlib.resources as resources
import shutil
import webbrowser
from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import load_config
from .engine.composio_tools import ComposioIntegration
from .engine.experiment import ExperimentRunner
from .engine.loader import primitives_exist
from .engine.memory import VectorMemory
from .engine.store import Store

app = typer.Typer(add_completion=False, help="GTM-OS — autonomous GTM operating system.")
console = Console()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit."),
):
    if version:
        console.print(f"gtm-os {__version__}")
        raise typer.Exit(code=0)
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(code=0)


def _resolve_default_primitives_src() -> Path | None:
    """Locate bundled default primitives.

    Order of preference:
      1. `primitives/` next to a `pyproject.toml` going up from cwd (dev mode)
      2. `primitives/` walking up from the installed package (editable installs)
      3. `gtm_os/_default_primitives` packaged inside the wheel
    """
    cur = Path.cwd().resolve()
    for parent in [cur, *cur.parents]:
        candidate = parent / "primitives"
        if (candidate / "agents").exists():
            return candidate

    pkg_dir = Path(__file__).resolve().parent
    for parent in [pkg_dir, *pkg_dir.parents]:
        candidate = parent / "primitives"
        if (candidate / "agents").exists():
            return candidate

    try:
        ref = resources.files("gtm_os").joinpath("_default_primitives")
        if ref.is_dir():
            return Path(str(ref))
    except (ModuleNotFoundError, AttributeError):
        pass
    return None


@app.command()
def init(
    target: Path = typer.Option(
        Path.cwd(),
        "--dir",
        "-d",
        help="Directory to initialize. Defaults to current working directory.",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing primitives."),
):
    """Scaffold a primitives/ tree and gtm-os.config.yaml into the target directory."""
    target = target.resolve()
    target.mkdir(parents=True, exist_ok=True)
    dst = target / "primitives"
    if dst.exists() and not force and primitives_exist(dst):
        console.print(
            f"[yellow]primitives/ already exists at {dst} — use --force to overwrite.[/yellow]"
        )
        raise typer.Exit(code=1)

    src = _resolve_default_primitives_src()
    if src is None:
        console.print("[red]Could not locate default primitives. Reinstall gtm-os.[/red]")
        raise typer.Exit(code=2)

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    console.print(f"[green]Wrote primitives → {dst}[/green]")

    cfg_path = target / "gtm-os.config.yaml"
    if not cfg_path.exists():
        example_path = None
        for parent in [target, *target.parents]:
            cand = parent / "gtm-os.config.yaml.example"
            if cand.exists():
                example_path = cand
                break
        if example_path:
            shutil.copy(example_path, cfg_path)
        else:
            cfg_path.write_text(
                "primitives_dir: ./primitives\ndata_dir: ./data\nllm:\n  model: openai/gpt-4o-mini\n",
                encoding="utf-8",
            )
        console.print(f"[green]Wrote {cfg_path}[/green]")

    data_dir = target / "data"
    data_dir.mkdir(exist_ok=True)
    console.print(
        "[green]Ready.[/green]  Next: set OPENAI_API_KEY (or another provider) and run `gtm-os start`."
    )


@app.command()
def start(
    host: str | None = typer.Option(None, help="Override server host."),
    port: int | None = typer.Option(None, help="Override server port."),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser when ready."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on file changes (dev mode)."),
):
    """Start the GTM-OS server (FastAPI + static UI + scheduler)."""
    cfg = load_config()
    host = host or cfg.server.host
    port = port or cfg.server.port

    if not primitives_exist(cfg.primitives_dir):
        console.print(
            f"[yellow]No primitives at {cfg.primitives_dir}. Run `gtm-os init` first.[/yellow]"
        )
        raise typer.Exit(code=1)

    url = f"http://{host}:{port}/"
    console.print(f"[bold green]Starting GTM-OS at {url}[/bold green]")

    if open_browser:
        with contextlib.suppress(Exception):
            webbrowser.open(url)

    uvicorn.run(
        "gtm_os.server.app:create_app",
        factory=True,
        host=host,
        port=int(port),
        reload=reload,
    )


@app.command()
def status():
    """Show experiments, schedules, and runtime stats."""
    cfg = load_config()
    store = Store(cfg.db_path)
    composio = ComposioIntegration(cfg.composio_api_key)
    memory = VectorMemory(store, cfg.llm)
    runner = ExperimentRunner(config=cfg, store=store, memory=memory, composio=composio)

    primitives = runner.load_primitives_cached()

    info_table = Table(title="GTM-OS status", show_header=False)
    info_table.add_row("version", __version__)
    info_table.add_row("primitives", str(cfg.primitives_dir))
    info_table.add_row("data", str(cfg.data_dir))
    info_table.add_row("model", cfg.llm.model)
    info_table.add_row("composio", "configured" if composio.configured else "not configured")
    info_table.add_row("agents", ", ".join(sorted(primitives.agents.keys())) or "(none)")
    info_table.add_row("plays", str(len(primitives.plays)))
    console.print(info_table)

    experiments = store.list_experiments(limit=20)
    if experiments:
        t = Table(title="experiments")
        t.add_column("id")
        t.add_column("name")
        t.add_column("phase")
        t.add_column("tokens")
        t.add_column("plays")
        for e in experiments:
            t.add_row(
                e.id[:8],
                e.name,
                e.phase,
                f"{e.tokens_used}/{e.token_budget}",
                ",".join(e.play_ids) or "-",
            )
        console.print(t)
    else:
        console.print("[dim]No experiments yet.[/dim]")

    schedules = store.list_schedules()
    if schedules:
        t = Table(title="schedules")
        t.add_column("id")
        t.add_column("experiment_id")
        t.add_column("type")
        t.add_column("next_run_at")
        t.add_column("enabled")
        t.add_column("fails")
        for s in schedules:
            t.add_row(
                s.id[:8],
                (s.experiment_id or "-")[:8],
                s.type,
                s.next_run_at,
                "yes" if s.enabled else "no",
                str(s.consecutive_failures),
            )
        console.print(t)

    store.close()


@app.command(name="run-tick")
def run_tick(experiment_id: str):
    """Run one experiment tick manually (useful for debugging)."""
    cfg = load_config()
    store = Store(cfg.db_path)
    composio = ComposioIntegration(cfg.composio_api_key)
    memory = VectorMemory(store, cfg.llm)
    runner = ExperimentRunner(config=cfg, store=store, memory=memory, composio=composio)
    outcome = asyncio.run(runner.run_tick(experiment_id))
    store.close()

    console.print(
        f"[bold]{'ok' if outcome.ok else 'failed'}[/bold] — phase={outcome.phase} "
        f"tokens={outcome.tokens_used} error={outcome.error}"
    )
    if outcome.message:
        console.print()
        console.print(outcome.message)


@app.command()
def setup():
    """Interactive setup wizard (WS4A) — walks through LLM, API keys, and brand config."""
    console.print("[bold]GTM-OS Setup Wizard[/bold]\n")

    # Step 1: LLM provider
    console.print("[bold]1. LLM Provider[/bold]")
    console.print("   Options: openai, anthropic, ollama (local)")
    provider = typer.prompt("   Provider", default="openai")
    model_defaults = {
        "openai": "openai/gpt-4o-mini",
        "anthropic": "anthropic/claude-3-5-sonnet-20241022",
        "ollama": "ollama/llama3.1",
    }
    model = typer.prompt("   Model", default=model_defaults.get(provider, "openai/gpt-4o-mini"))

    # Step 2: API key
    api_key_env = ""
    if provider != "ollama":
        console.print("\n[bold]2. API Key[/bold]")
        env_var = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
        console.print(f"   Set {env_var} in your environment (or enter it now).")
        import os

        existing = os.environ.get(env_var, "")
        if existing:
            console.print(f"   [green]✓ {env_var} already set[/green]")
        else:
            api_key_env = typer.prompt(f"   {env_var}", default="", hide_input=True)
            if api_key_env:
                os.environ[env_var] = api_key_env

    # Step 3: Composio
    console.print("\n[bold]3. Composio (GTM tool integrations)[/bold]")
    console.print("   Optional — connects Gmail, Apollo, HubSpot, Slack, etc.")
    import os

    composio_key = os.environ.get("COMPOSIO_API_KEY", "")
    if composio_key:
        console.print("   [green]✓ COMPOSIO_API_KEY already set[/green]")
    else:
        composio_key = typer.prompt("   COMPOSIO_API_KEY (or press Enter to skip)", default="")
        if composio_key:
            os.environ["COMPOSIO_API_KEY"] = composio_key

    # Step 4: Brand setup
    console.print("\n[bold]4. Brand[/bold]")
    company_name = typer.prompt("   Company name", default="My Company")
    company_desc = typer.prompt("   One-line description", default="")

    # Write config
    target = Path.cwd().resolve()
    cfg_path = target / "gtm-os.config.yaml"
    import yaml

    config_data = {
        "primitives_dir": "./primitives",
        "data_dir": "./data",
        "llm": {
            "model": model,
            "embedding_model": "openai/text-embedding-3-small",
            "temperature": 0.4,
            "max_tokens": 4096,
        },
        "scheduler": {"enabled": True, "poll_interval_seconds": 60},
    }
    if composio_key:
        config_data["api_keys"] = {"composio": composio_key}

    cfg_path.write_text(yaml.dump(config_data, default_flow_style=False), encoding="utf-8")
    console.print(f"\n[green]Wrote config → {cfg_path}[/green]")

    # Update brand if primitives exist
    brand_path = target / "primitives" / "brand" / "BRAND.md"
    if brand_path.parent.exists():
        brand_content = (
            f"# {company_name}\n\n"
            f"{company_desc}\n\n"
            "## Voice & Tone\n\n"
            "- Professional but approachable\n"
            "- Data-driven, cite numbers when possible\n"
            "- Concise — respect the reader's time\n"
        )
        brand_path.write_text(brand_content, encoding="utf-8")
        console.print(f"[green]Updated brand → {brand_path}[/green]")

    console.print("\n[bold green]Setup complete![/bold green]")
    console.print("Run `gtm-os start` to launch.")


@app.command(name="decay-memory")
def decay_memory():
    """Apply memory decay (reduce confidence of old memories)."""
    cfg = load_config()
    store = Store(cfg.db_path)
    memory = VectorMemory(store, cfg.llm)
    count = memory.apply_decay()
    store.close()
    console.print(f"[green]Decayed {count} memories.[/green]")


@app.command(name="promote-rules")
def promote_rules():
    """Promote high-confidence learnings to standing rule files."""
    cfg = load_config()
    store = Store(cfg.db_path)
    memory = VectorMemory(store, cfg.llm)
    rules_dir = cfg.primitives_dir / "rules"
    written = memory.write_corrections_to_rules(rules_dir)
    store.close()
    if written:
        console.print(f"[green]Promoted {len(written)} learnings to rules:[/green]")
        for p in written:
            console.print(f"  {p}")
    else:
        console.print("[dim]No learnings met promotion threshold yet.[/dim]")


if __name__ == "__main__":  # pragma: no cover
    app()
