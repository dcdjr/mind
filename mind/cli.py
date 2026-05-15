from __future__ import annotations

import argparse

from pathlib import Path

import urllib.request
import urllib.error

from mind import __version__
from mind.config import Config, load_config
from mind.llm import ask
from mind.workspace import ensure_workspace, list_workspace_files
from mind.memory import add_memory, delete_memory, list_memories
from mind.context import build_context
from mind.chat import run_chat


def is_ollama_running(config: Config) -> bool:
    try:
        # Ollama listens on 11434 by default
        with urllib.request.urlopen(config.model.base_url, timeout=2) as response:
            return response.getcode() == 200
    except (urllib.error.URLError, ConnectionRefusedError, TimeoutError):
        return False


def print_workspace_files(config: Config) -> None:
    """Print all files inside Mind's workspace as relative paths."""
    files = list_workspace_files(config)

    if not files:
        print("Workspace is empty.")
        return

    print("Workspace files:")
    print()

    for file in files:
        print(file)


def print_home(config: Config) -> None:
    """Show the default landing output for the bare `mind` command."""
    ensure_workspace(config.paths.workspace)

    print(config.assistant.name)
    print(config.assistant.description)
    print()
    print(f"Status: v{__version__} skeleton installed.")


def print_doctor(config: Config) -> None:
    """Show basic setup checks without depending on future features."""
    workspace = ensure_workspace(config.paths.workspace)
    
    ollama_ok = "Ollama: OK" if is_ollama_running(config) else "Ollama: not reachable"

    print("Mind doctor")
    print("Python: OK")
    print("Package: OK")
    print("Config: OK")
    print(ollama_ok)
    print(f"Default model: {config.model.default}")
    print(f"Workspace: OK ({workspace.resolve()})")
    print(f"Database: OK ({config.paths.database.resolve()})")


def build_parser(config: Config) -> argparse.ArgumentParser:
    """Define Mind's public command-line interface in one place."""
    parser = argparse.ArgumentParser(
        prog="mind",
        description=config.assistant.description,
    )

    subparsers = parser.add_subparsers(dest="command")
    
    # Add doctor command
    subparsers.add_parser(
        "doctor",
        help="Check whether Mind's basic environment is working.",
    )

    # Add ask command
    ask_parser = subparsers.add_parser(
        "ask",
        help="Give Mind a single prompt.",
    )
    ask_parser.add_argument(
        "prompt",
        type=str,
        help="This is the prompt to give Mind."
    )
    ask_parser.add_argument(
        "--files",
        nargs="+",
        type=str,
        help=(
            "Optional workspace-relative file paths to add as context. "
            "Example: --files notes.txt plan.md"
        ),
    )

    # Add files command
    subparsers.add_parser(
        "files",
        help="List all files in Mind's workspace.",
    )

    # Add chat command
    subparsers.add_parser(
        "chat",
        help="Start an interactive Mind chat session.",
    )

    # Add remember command
    remember_parser = subparsers.add_parser(
        "remember",
        help="Store a memory.",
    )
    remember_parser.add_argument(
        "text",
        type=str,
        help="The memory text to store.",
    )

    # Add memories command
    subparsers.add_parser(
        "memories",
        help="List stored memories.",
    )

    # Add forget command
    forget_parser = subparsers.add_parser(
    "forget",
    help="Delete a saved memory by ID.",
    )
    forget_parser.add_argument(
        "memory_id",
        type=int,
        help="The ID of the memory to delete.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, route to the selected command, and return an exit code."""
    config = load_config()
    parser = build_parser(config)
    args = parser.parse_args(argv)

    if args.command == "doctor":
        print_doctor(config)
        return 0

    if args.command == "ask":
        file_paths = [Path(file) for file in args.files] if args.files else None
        context = build_context(config, file_paths)

        res = ask(
            config,
            args.prompt,
            context.workspace_context,
            context.memory_context,
        )
        print(res)
        return 0

    if args.command == "files":
        print_workspace_files(config)
        return 0

    if args.command == "chat":
        run_chat(config)
        return 0

    if args.command == "remember":
        add_memory(config, args.text)
        print("Memory saved.")
        return 0
    
    if args.command == "memories":
        memories = list_memories(config)

        if not memories:
            print("No memories stored.")
            return 0

        print("Memories:")
        print()

        for memory_id, memory_text in memories:
            print(f"{memory_id}. {memory_text}")

        return 0

    if args.command == "forget":
        deleted = delete_memory(config, args.memory_id)

        if deleted:
            print("Memory deleted.")
        else:
            print(f"No memory found with ID {args.memory_id}.")

        return 0
    
    print_home(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
