"""Sandbox execution — isolated Docker-based environment for agent code/tool execution.

The agent can:
- Run shell commands in an isolated container
- Execute Python/JS/bash scripts
- Install packages in the sandbox
- Read output and iterate

Sandboxes are per-experiment and persist across ticks (files survive).
Falls back to local subprocess if Docker is not available.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from ..types import Tool

logger = logging.getLogger(__name__)

# Timeout for sandbox commands (seconds).
_CMD_TIMEOUT = 60
# Max output chars to return.
_MAX_OUTPUT = 8000
# Docker image for sandboxes.
_SANDBOX_IMAGE = "python:3.11-slim"


def _docker_available() -> bool:
    """Check if Docker is available."""
    return shutil.which("docker") is not None


async def _run_in_docker(
    command: str,
    *,
    workspace: Path,
    image: str = _SANDBOX_IMAGE,
    timeout: int = _CMD_TIMEOUT,
) -> dict[str, Any]:
    """Run a command inside a Docker container with a mounted workspace."""
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "--network=host",
        "-v",
        f"{workspace}:/workspace",
        "-w",
        "/workspace",
        "--memory=512m",
        "--cpus=1",
        image,
        "bash",
        "-c",
        command,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", "replace")
        errors = stderr.decode("utf-8", "replace")
        combined = output + ("\n--- stderr ---\n" + errors if errors else "")
        if len(combined) > _MAX_OUTPUT:
            combined = combined[:_MAX_OUTPUT] + "\n... [truncated]"
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "output": combined,
            "engine": "docker",
        }
    except TimeoutError:
        return {"ok": False, "exit_code": -1, "output": f"Timed out after {timeout}s", "engine": "docker"}
    except Exception as exc:
        return {"ok": False, "exit_code": -1, "output": f"Docker error: {exc}", "engine": "docker"}


async def _run_local(
    command: str,
    *,
    workspace: Path,
    timeout: int = _CMD_TIMEOUT,
) -> dict[str, Any]:
    """Fallback: run in a local subprocess (less isolated)."""
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workspace),
            env={**os.environ, "HOME": str(workspace)},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", "replace")
        errors = stderr.decode("utf-8", "replace")
        combined = output + ("\n--- stderr ---\n" + errors if errors else "")
        if len(combined) > _MAX_OUTPUT:
            combined = combined[:_MAX_OUTPUT] + "\n... [truncated]"
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "output": combined,
            "engine": "local",
        }
    except TimeoutError:
        return {"ok": False, "exit_code": -1, "output": f"Timed out after {timeout}s", "engine": "local"}
    except Exception as exc:
        return {"ok": False, "exit_code": -1, "output": f"Error: {exc}", "engine": "local"}


class Sandbox:
    """Per-experiment sandbox with persistent workspace."""

    def __init__(self, experiment_id: str, data_dir: Path) -> None:
        self.experiment_id = experiment_id
        self.workspace = data_dir / "sandboxes" / experiment_id
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._use_docker = _docker_available()

    async def run(self, command: str, timeout: int = _CMD_TIMEOUT) -> dict[str, Any]:
        """Execute a command in the sandbox."""
        if self._use_docker:
            return await _run_in_docker(command, workspace=self.workspace, timeout=timeout)
        return await _run_local(command, workspace=self.workspace, timeout=timeout)

    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        """Write a file into the sandbox workspace."""
        target = self.workspace / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(target), "size": len(content)}

    async def read_file(self, path: str) -> dict[str, Any]:
        """Read a file from the sandbox workspace."""
        target = self.workspace / path
        if not target.exists():
            return {"ok": False, "error": f"File not found: {path}"}
        content = target.read_text(encoding="utf-8", errors="replace")
        if len(content) > _MAX_OUTPUT:
            content = content[:_MAX_OUTPUT] + "\n... [truncated]"
        return {"ok": True, "path": path, "content": content}

    async def list_files(self) -> dict[str, Any]:
        """List files in the workspace."""
        files = []
        for p in sorted(self.workspace.rglob("*")):
            if p.is_file():
                rel = p.relative_to(self.workspace)
                files.append({"path": str(rel), "size": p.stat().st_size})
        return {"ok": True, "files": files[:100]}


# Sandbox pool keyed by experiment ID.
_sandboxes: dict[str, Sandbox] = {}


def get_sandbox(experiment_id: str, data_dir: Path) -> Sandbox:
    """Get or create a sandbox for an experiment."""
    if experiment_id not in _sandboxes:
        _sandboxes[experiment_id] = Sandbox(experiment_id, data_dir)
    return _sandboxes[experiment_id]


def build_sandbox_tools(data_dir: Path) -> list[Tool]:
    """Tools for executing code in a sandboxed environment."""

    async def _sandbox_run(
        command: str, experiment_id: str = "default", timeout: int = 60
    ) -> Any:
        sb = get_sandbox(experiment_id, data_dir)
        return await sb.run(command, timeout=int(timeout))

    async def _sandbox_write(
        path: str, content: str, experiment_id: str = "default"
    ) -> Any:
        sb = get_sandbox(experiment_id, data_dir)
        return await sb.write_file(path, content)

    async def _sandbox_read(path: str, experiment_id: str = "default") -> Any:
        sb = get_sandbox(experiment_id, data_dir)
        return await sb.read_file(path)

    async def _sandbox_files(experiment_id: str = "default") -> Any:
        sb = get_sandbox(experiment_id, data_dir)
        return await sb.list_files()

    return [
        Tool(
            name="sandbox_run",
            description=(
                "Run a shell command in an isolated sandbox environment. Use for: "
                "executing scripts, installing packages, running tools, testing code. "
                "The sandbox persists files between calls (per experiment). "
                "Uses Docker if available, falls back to local subprocess."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute (bash).",
                    },
                    "experiment_id": {
                        "type": "string",
                        "default": "default",
                        "description": "Experiment to scope the sandbox to.",
                    },
                    "timeout": {
                        "type": "integer",
                        "default": 60,
                        "description": "Max seconds to wait (1-300).",
                    },
                },
                "required": ["command"],
            },
            execute=_sandbox_run,
        ),
        Tool(
            name="sandbox_write_file",
            description=(
                "Write a file into the sandbox workspace. Use to create scripts, "
                "configs, data files that sandbox_run can then use."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative file path within sandbox (e.g. 'script.py').",
                    },
                    "content": {
                        "type": "string",
                        "description": "File content to write.",
                    },
                    "experiment_id": {
                        "type": "string",
                        "default": "default",
                        "description": "Experiment scope.",
                    },
                },
                "required": ["path", "content"],
            },
            execute=_sandbox_write,
        ),
        Tool(
            name="sandbox_read_file",
            description="Read a file from the sandbox workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative file path to read.",
                    },
                    "experiment_id": {
                        "type": "string",
                        "default": "default",
                        "description": "Experiment scope.",
                    },
                },
                "required": ["path"],
            },
            execute=_sandbox_read,
        ),
        Tool(
            name="sandbox_list_files",
            description="List all files in the sandbox workspace for an experiment.",
            parameters={
                "type": "object",
                "properties": {
                    "experiment_id": {
                        "type": "string",
                        "default": "default",
                        "description": "Experiment scope.",
                    },
                },
                "required": [],
            },
            execute=_sandbox_files,
        ),
    ]
