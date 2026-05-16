from __future__ import annotations

import argparse

from mind.config import Config, load_config
from mind.commands import (
    run_files_command,
    run_home_command,
    run_doctor_command,
    run_remember_command,
    run_memories_command,
    run_forget_command,
    run_ask_command,
    run_chat_command,
)


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
        help="This is the prompt to give Mind.",
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
        return run_doctor_command(config)

    if args.command == "ask":
        return run_ask_command(config, args.prompt, args.files)

    if args.command == "files":
        return run_files_command(config)

    if args.command == "chat":
        return run_chat_command(config)

    if args.command == "remember":
        return run_remember_command(config, args.text)
    
    if args.command == "memories":
        return run_memories_command(config)

    if args.command == "forget":
        return run_forget_command(config, args.memory_id)
    
    return run_home_command(config)


if __name__ == "__main__":
    raise SystemExit(main())
