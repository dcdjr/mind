from __future__ import annotations

import argparse
from pathlib import Path

from mind import __version__

APP_NAME = "Mind"
APP_DESCRIPTION = "A lightweight local-first personal AI assistant."

def ensure_workspace() -> Path:
    workspace = Path("workspace")
    workspace.mkdir(exist_ok=True)
    return workspace

def print_home() -> None:
    ensure_workspace()
    print(APP_NAME)
    print(APP_DESCRIPTION)
    print()
    print(f"Status: v{__version__} skeleton installed.")

def print_doctor() -> None:
    workspace = ensure_workspace()

    print("Mind doctor")
    print("Python: OK")
    print("Package: OK")
    print(f"Workspace: OK ({workspace.resolve()})")
    print("Database: not implemented yet")
    print("Ollama: not implemented yet")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mind",
        description=APP_DESCRIPTION,
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "doctor",
        help="Check whether Mind's basic environment is working.",
    )

    return parser

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        print_doctor()
        return 0

    print_home()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
