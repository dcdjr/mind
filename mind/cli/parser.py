from __future__ import annotations

import argparse

from mind.core.config import Config, load_config
from mind.cli.commands import (
    run_files_command,
    run_home_command,
    run_doctor_command,
    run_inspect_command,
    run_remember_command,
    run_memories_command,
    run_forget_command,
    run_ask_command,
    run_chat_command,
    run_agent_command,
    run_tools_command,
    run_runs_command,
    run_run_show_command,
    run_uncensored_command,
    run_memory_confirm_command,
    run_memory_reject_command,
    run_memory_delete_command,
)


def build_parser(config: Config) -> argparse.ArgumentParser:
    """Define Mind's public command-line interface in one place."""
    parser = argparse.ArgumentParser(
        prog="mind",
        description=config.assistant.description,
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "doctor",
        help="Check whether Mind's basic environment is working.",
    )

    subparsers.add_parser(
        "inspect",
        help="Show Mind's current configuration and runtime state."
    )

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
    ask_parser.add_argument(
        "--tools",
        action="store_true",
        help="Allow this one-shot prompt to use Mind's safe internal tools.",
    )
    ask_parser.add_argument(
        "--trace",
        action="store_true",
        help="Show tool calls and intermediate steps when --tools is enabled.",
    )

    subparsers.add_parser(
        "files",
        help="List all files in Mind's workspace.",
    )

    chat_parser = subparsers.add_parser(
        "chat",
        help="Start an interactive Mind chat session.",
    )
    chat_parser.add_argument(
        "--tools",
        action="store_true",
        help="Allow each chat turn to use Mind's safe internal tools.",
    )
    chat_parser.add_argument(
        "--trace",
        action="store_true",
        help="Show tool calls and intermediate steps when --tools is enabled.",
    )

    remember_parser = subparsers.add_parser(
        "remember",
        help="Store a memory.",
    )
    remember_parser.add_argument(
        "text",
        type=str,
        help="The memory text to store.",
    )

    memories_parser = subparsers.add_parser(
        "memories",
        help="List stored memories.",
    )
    memories_parser.add_argument(
        "--status",
        choices=["confirmed", "auto_extracted", "rejected", "archived"],
        help="Only show memories with this review status.",
    )

    forget_parser = subparsers.add_parser(
        "forget",
        help="Delete a saved memory by ID.",
    )
    forget_parser.add_argument(
        "memory_id",
        type=int,
        help="The ID of the memory to delete.",
    )

    memory_parser = subparsers.add_parser(
        "memory",
        help="Review or manage individual memories.",
    )
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command")

    memory_confirm_parser = memory_subparsers.add_parser(
        "confirm",
        help="Mark a memory as confirmed.",
    )
    memory_confirm_parser.add_argument(
        "memory_id",
        type=int,
        help="The ID of the memory to confirm.",
    )

    memory_reject_parser = memory_subparsers.add_parser(
        "reject",
        help="Mark a memory as rejected.",
    )
    memory_reject_parser.add_argument(
        "memory_id",
        type=int,
        help="The ID of the memory to reject.",
    )

    memory_delete_parser = memory_subparsers.add_parser(
        "delete",
        help="Delete a memory permanently.",
    )
    memory_delete_parser.add_argument(
        "memory_id",
        type=int,
        help="The ID of the memory to delete.",
    )

    agent_parser = subparsers.add_parser(
        "agent",
        help="Alias for `mind ask --tools`.",
    )
    agent_parser.add_argument(
        "prompt",
        type=str,
        help="The one-shot tool-enabled prompt to run.",
    )
    agent_parser.add_argument(
        "--trace",
        action="store_true",
        help="Show the agent's tool calls and intermediate steps.",
    )

    subparsers.add_parser(
        "tools",
        help="List tools currently available to Mind."
    )

    subparsers.add_parser(
        "runs",
        help="List saved agent runs.",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Inspect a saved agent run.",
    )
    run_subparsers = run_parser.add_subparsers(dest="run_command")

    run_show_parser = run_subparsers.add_parser(
        "show",
        help="Show a saved agent run.",
    )
    run_show_parser.add_argument(
        "run_id",
        type=str,
        help="The saved agent run ID.",
    )

    uncensored_parser = subparsers.add_parser(
        "uncensored",
        help="Chat with Mind using an uncensored model as the inference engine.",
    )
    uncensored_parser.add_argument(
        "prompt",
        type=str,
        help="This is the prompt to give Mind's uncensored model.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, route to the selected command, and return an exit code."""
    config = load_config()
    parser = build_parser(config)
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return run_doctor_command(config)

    if args.command == "inspect":
        return run_inspect_command(config)

    if args.command == "ask":
        return run_ask_command(
            config,
            args.prompt,
            args.files,
            args.tools,
            args.trace,
        )

    if args.command == "files":
        return run_files_command(config)

    if args.command == "chat":
        return run_chat_command(config, args.tools, args.trace)

    if args.command == "remember":
        return run_remember_command(config, args.text)

    if args.command == "memories":
        return run_memories_command(config, args.status)

    if args.command == "forget":
        return run_forget_command(config, args.memory_id)

    if args.command == "memory":
        if args.memory_command == "confirm":
            return run_memory_confirm_command(config, args.memory_id)

        if args.memory_command == "reject":
            return run_memory_reject_command(config, args.memory_id)

        if args.memory_command == "delete":
            return run_memory_delete_command(config, args.memory_id)

        parser.error("memory requires a subcommand, such as `confirm`, `reject`, or `delete`.")

    if args.command == "agent":
        return run_agent_command(config, args.prompt, args.trace)

    if args.command == "tools":
        return run_tools_command(config)

    if args.command == "runs":
        return run_runs_command(config)

    if args.command == "run":
        if args.run_command == "show":
            return run_run_show_command(config, args.run_id)

        parser.error("run requires a subcommand, such as `show`.")

    if args.command == "uncensored":
        return run_uncensored_command(config, args.prompt)

    return run_home_command(config)


if __name__ == "__main__":
    raise SystemExit(main())
