from __future__ import annotations


import argparse
from pathlib import Path


from mind import __version__
from mind.config import Config, load_config
from mind.llm import ask


import urllib.request
import urllib.error


def ensure_workspace(workspace: Path) -> Path:
    """Create Mind's controlled workspace if it does not already exist."""
    workspace.mkdir(exist_ok=True)
    return workspace


def is_ollama_running(config: Config) -> bool:
    try:
        # Ollama listens on 11434 by default
        with urllib.request.urlopen(config.model.base_url, timeout=2) as response:
            return response.getcode() == 200
    except (urllib.error.URLError, ConnectionRefusedError, TimeoutError):
        return False


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
    print("Database: not implemented yet")


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
        res = ask(config, args.prompt)
        print(res)
        return 0

    print_home(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
