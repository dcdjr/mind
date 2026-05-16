from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from mind.config import Config
from mind.memory import list_memories
from mind.workspace import list_workspace_files, read_workspace_file

import urllib.request
import urllib.error


# Defines the type of a ToolFunction.
# This means every tool function most follow the same signature.
# This allows different tools to be stored in a dictionary.
ToolFunction = Callable[[Config, dict[str, Any]], str]


def tool_workspace_list_files(config: Config, args: dict[str, Any]) -> str:
    """List files in Mind's controlled workspace."""
    files = list_workspace_files(config)

    if not files:
        return "Workspace is empty."

    lines = ["Workspace files:"]

    for file in files:
        lines.append(f"- {file}")

    return "\n".join(lines)


def tool_workspace_read_file(config: Config, args: dict[str, Any]) -> str:
    """Read a workspace-relative file path."""
    path = args.get("path")

    if not isinstance(path, str) or not path.strip():
        return "Error: workspace.read_file requires a non-empty string argument named 'path'."

    content = read_workspace_file(config, Path(path))

    return f"FILE: {path}\n---\n{content}"


def tool_memory_list(config: Config, args: dict[str, Any]) -> str:
    """List saved memories."""
    memories = list_memories(config)

    if not memories:
        return "No memories stored."

    lines = ["Saved memories:"]

    for _, memory_text in memories:
        lines.append(f"- {memory_text}")

    return "\n".join(lines)


def tool_internet_github_zen(config: Config, args: dict[str, Any]) -> str:
    """Fetch a short random phrase from GitHub's public Zen API."""
    url = "https://api.github.com/zen"

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "mind-local",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8", errors="replace").strip()
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace").strip()
        return (
            f"Error: GitHub Zen API returned HTTP {error.code} "
            f"{error.reason}. Response body: {error_body}"
        )
    except urllib.error.URLError as error:
        return f"Error: Could not reach GitHub Zen API: {error.reason}"
    except TimeoutError:
        return "Error: GitHub Zen API request timed out."

    if not body:
        return "Error: GitHub Zen API returned an empty response."

    return f"GitHub Zen: {body}"


TOOL_REGISTRY: dict[str, ToolFunction] = {
    "workspace.list_files": tool_workspace_list_files,
    "workspace.read_file": tool_workspace_read_file,
    "memory.list": tool_memory_list,
    "internet.github_zen": tool_internet_github_zen,
}


def run_tool(config: Config, tool_name: str, args: dict[str, Any] | None = None) -> str:
    """Run a known safe internal Mind tool by name."""
    if tool_name not in TOOL_REGISTRY:
        return f"Error: Unknown tool '{tool_name}'."

    safe_args = args or {}

    return TOOL_REGISTRY[tool_name](config, safe_args)


def format_available_tools() -> str:
    """Return a prompt-friendly list of available tools."""
    return "\n".join(
        [
            "- workspace.list_files: list files in the workspace. Args: {}",
            '- workspace.read_file: read a workspace-relative file. Args: {"path": "notes.txt"}',
            "- memory.list: list saved memories. Args: {}",
            "- internet.github_zen: fetch a short random phrase from GitHub's public Zen API. Args: {}",
        ]
    )
