from pathlib import Path

import sys

from mind import __version__
from mind.core.config import Config
from mind.memory import add_memory, list_memories, delete_memory
from mind.workspace import ensure_workspace, list_workspace_files
from mind.core.diagnostics import is_ollama_running
from mind.runtime.ask import ask_once
from mind.runtime.chat import run_chat
from mind.tools import TOOL_REGISTRY, ToolSpec, tool_is_allowed_to_run
from mind.runtime.confirmation import confirm_tool_run
from mind.agent import (
    list_agent_runs,
    read_agent_run_metadata,
    run_agent,
    save_agent_run,
)


def _split_agent_response_for_persistence(
    response: str,
) -> tuple[str, str | None]:
    """
    Split a run_agent() response into final answer and optional trace output.

    run_agent(trace=False) returns only the final answer.

    run_agent(trace=True) returns:
        Agent trace:
        ...

        Final answer:
        ...

    For persistence, we want final.md to contain only the final answer and
    trace.md to contain only the trace/debug section.
    """
    marker = "\n\nFinal answer:\n"

    if marker not in response:
        return response, None

    trace_output, final_answer = response.rsplit(marker, maxsplit=1)

    return final_answer.strip(), trace_output.strip() + "\n"


def _enabled(value: bool) -> str:
    """Return a consistent human-readable enabled/disabled label."""
    return "enabled" if value else "disabled"


def _status(ok: bool) -> str:
    """Return a consistent health-check status label."""
    return "OK" if ok else "not OK"


def _tool_permission_enabled(config: Config, permission: str) -> bool:
    """Return whether a tool permission level is enabled by the current config."""
    if permission == "read_only":
        return True

    if permission == "external_read":
        return config.tools.allow_external_read

    if permission == "local_write":
        return config.tools.allow_local_write

    if permission == "external_write":
        return config.tools.allow_external_write

    if permission == "dangerous":
        return config.tools.allow_dangerous

    return False


def _get_python_version() -> str:
    return (
        f"{sys.version_info.major}."
        f"{sys.version_info.minor}."
        f"{sys.version_info.micro}"
    )


def _available_agent_tools(config: Config) -> list[ToolSpec]:
    """Return tools that are visible to the agent under the current config."""
    return [
        spec
        for spec in TOOL_REGISTRY.values()
        if spec.available_to_agent and _tool_permission_enabled(config, spec.permission)
    ]


def run_files_command(config: Config) -> int:
    """Print all files inside Mind's workspace as relative paths."""
    files = list_workspace_files(config)

    if not files:
        print("Workspace is empty.")
        return 0

    print("Workspace files:")
    print()

    for file in files:
        print(file)

    return 0


def run_home_command(config: Config) -> int:
    """Show the default landing output for the bare `mind` command."""
    ensure_workspace(config.paths.workspace)

    print(f"{config.assistant.name} v{__version__}")
    print(config.assistant.description)
    print()
    print("Quick start:")
    print('  mind ask "..."')
    print("  mind chat")
    print("  mind chat --tools")
    print('  mind agent --trace "..."')
    print("  mind files")
    print("  mind memories")
    print("  mind tools")
    print("  mind doctor")
    print()
    print("Current config:")
    print(f"  Model: {config.model.provider} / {config.model.default}")
    print(f"  Workspace: {config.paths.workspace}")
    print(f"  Database: {config.paths.database}")
    print()
    print("Run `mind doctor` to check setup.")
    print("Run `mind inspect` to view detailed runtime state.")

    return 0


def run_doctor_command(config: Config) -> int:
    """Check whether Mind's local runtime environment is usable."""
    python_version = _get_python_version()

    workspace_ok = True
    database_ok = True
    project_root_ok = config.project.root.exists() and config.project.root.is_dir()
    ollama_ok = is_ollama_running(config)

    try:
        workspace = ensure_workspace(config.paths.workspace)
    except OSError:
        workspace_ok = False
        workspace = config.paths.workspace

    try:
        config.paths.database.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        database_ok = False

    healthy = all(
        [
            workspace_ok,
            database_ok,
            project_root_ok,
            ollama_ok,
        ]
    )

    print("Mind doctor")
    print()
    print(f"Package: OK — v{__version__}")
    print(f"Python: OK — {python_version}")
    print("Config: OK — configs/config.toml")
    print(f"Ollama: {_status(ollama_ok)} — {config.model.base_url}")
    print(f"Model: {config.model.default}")
    print(f"Workspace: {_status(workspace_ok)} — {workspace.resolve()}")
    print(f"Database: {_status(database_ok)} — {config.paths.database.resolve()}")
    print(f"Project root: {_status(project_root_ok)} — {config.project.root.resolve()}")
    print()
    print("Tool safety:")
    print(f"  external_read: {_enabled(config.tools.allow_external_read)}")
    print(f"  local_write: {_enabled(config.tools.allow_local_write)}")
    print(f"  external_write: {_enabled(config.tools.allow_external_write)}")
    print(f"  dangerous: {_enabled(config.tools.allow_dangerous)}")
    print(f"  confirmation: {_enabled(config.tools.require_confirmation)}")

    warnings = []

    if config.tools.allow_local_write:
        warnings.append(
            "local_write is enabled. Mind can modify workspace files after confirmation."
        )

    if config.tools.allow_external_write:
        warnings.append(
            "external_write is enabled. Mind may modify external services if such tools exist."
        )

    if config.tools.allow_dangerous:
        warnings.append(
            "dangerous tools are enabled. This is not recommended."
        )

    if not config.memory.auto_memory:
        warnings.append(
            "auto_memory is disabled. Mind will not extract memories during chat."
        )

    if warnings:
        print()
        print("Warnings:")
        for warning in warnings:
            print(f"  Warning: {warning}")

    if not ollama_ok:
        print()
        print("Hint: Start Ollama, then run `mind doctor` again.")

    if not project_root_ok:
        print()
        print("Hint: Check the [project] root setting in configs/config.toml.")

    print()
    print(f"Status: {'healthy' if healthy else 'needs attention'}")

    return 0 if healthy else 1


def run_inspect_command(config: Config) -> int:
    """Print Mind's current configuration and runtime state without calling the model."""
    memories = list_memories(config)
    workspace_files = list_workspace_files(config)
    available_tools = _available_agent_tools(config)

    permission_counts: dict[str, int] = {
        "read_only": 0,
        "external_read": 0,
        "local_write": 0,
        "external_write": 0,
        "dangerous": 0,
    }

    for spec in TOOL_REGISTRY.values():
        permission_counts[spec.permission] += 1

    python_version = _get_python_version()

    print("Mind inspect")
    print()
    print("Version:")
    print(f"  Mind: {__version__}")
    print(f"  Python: {python_version}")
    print()
    print("Model:")
    print(f"  Provider: {config.model.provider}")
    print(f"  Base URL: {config.model.base_url}")
    print(f"  Default model: {config.model.default}")
    print()
    print("Paths:")
    print(f"  Workspace: {config.paths.workspace}")
    print(f"  Database: {config.paths.database}")
    print(f"  Project root: {config.project.root}")
    print()
    print("Memory:")
    print(f"  Auto memory: {_enabled(config.memory.auto_memory)}")
    print(f"  Max relevant memories: {config.memory.max_relevant_memories}")
    print(f"  Stored memories: {len(memories)}")
    print()
    print("Context:")
    print(f"  Max workspace chars: {config.context.max_workspace_chars}")
    print(f"  Workspace files: {len(workspace_files)}")
    print()
    print("Tools:")
    print(f"  Registered tools: {len(TOOL_REGISTRY)}")
    print(f"  Available to agent: {len(available_tools)}")
    print(f"  read_only tools: {permission_counts['read_only']}")
    print(f"  external_read tools: {permission_counts['external_read']}")
    print(f"  local_write tools: {permission_counts['local_write']}")
    print(f"  external_write tools: {permission_counts['external_write']}")
    print(f"  dangerous tools: {permission_counts['dangerous']}")
    print()
    print("Tool permissions:")
    print("  read_only: enabled")
    print(f"  external_read: {_enabled(config.tools.allow_external_read)}")
    print(f"  local_write: {_enabled(config.tools.allow_local_write)}")
    print(f"  external_write: {_enabled(config.tools.allow_external_write)}")
    print(f"  dangerous: {_enabled(config.tools.allow_dangerous)}")
    print(f"  confirmation: {_enabled(config.tools.require_confirmation)}")
    print()

    if available_tools:
        print("Available agent tools:")
        for spec in available_tools:
            print(f"  {spec.name}")
    else:
        print("Available agent tools: none")

    return 0


def run_remember_command(config: Config, text: str) -> int:
    """Adds a memory to Mind's memory database."""
    add_result = add_memory(config, text)
    if add_result:
        print("Memory saved.")
    else: 
        print("Memory already exists.")

    return 0
   

def run_memories_command(config: Config) -> int:
    """Lists all memories currently stored in Mind's memory database."""
    memories = list_memories(config)

    if not memories:
        print("No memories stored.")
        return 0

    print("Memories:")
    print()

    for memory_id, memory_text in memories:
        print(f"{memory_id}. {memory_text}")

    return 0


def run_forget_command(config: Config, memory_id: int) -> int:
    """Deletes a memory in Mind's memory database by id."""
    deleted = delete_memory(config, memory_id)

    if not deleted:
        print(f"No memory found with ID {memory_id}.")
        return 0

    print("Memory deleted.")

    return 0


def run_ask_command(
    config: Config,
    prompt: str,
    files: list[str] | None,
    tools: bool = False,
    trace: bool = False,
) -> int:
    """Give Mind a single prompt, optionally with tool use enabled."""
    if tools:
        if files:
            print("Error: --files cannot be used with --tools yet.")
            return 1

        response = run_agent(config, prompt, trace=trace, confirm=confirm_tool_run)
        final_answer, trace_output = _split_agent_response_for_persistence(response)
        
        saved_run = save_agent_run(
            config=config,
            user_prompt=prompt,
            final_answer=final_answer,
            trace_output=trace_output,
            status="completed",
        )

        print(response)
        print()
        print(f"Saved agent run: {saved_run.run_id}")

        return 0

    if trace:
        print("Error: --trace can only be used with --tools.")
        return 1

    file_paths = [Path(file) for file in files] if files else None
    response = ask_once(config, prompt, file_paths)
    print(response)

    return 0


def run_chat_command(
    config: Config,
    tools: bool = False,
    trace: bool = False,
) -> int:
    """Run a chat session with Mind, optionally with tool use enabled."""
    if trace and not tools:
        print("Error: --trace can only be used with --tools")
        return 1

    run_chat(config, tools=tools, trace=trace)

    return 0


def run_agent_command(config: Config, prompt: str, trace: bool = False) -> int:
    """Compatibility alias for tool-enabled one-shot ask mode."""
    return run_ask_command(
        config,
        prompt,
        files=None,
        tools=True,
        trace=trace,
    )


def run_tools_command(config: Config) -> int:
    """List all tools currently available to Mind."""
    if not TOOL_REGISTRY:
        print("There are no available tools for Mind.")
        return 0

    allowed_tools = []

    for _, spec in TOOL_REGISTRY.items():
        if spec.available_to_agent and tool_is_allowed_to_run(config, spec):
            allowed_tools.append(spec)
        else:
            continue

    if not allowed_tools:
        print("There are no available tools for Mind.")
        return 0

    print("Available tools:")
    print()

    def print_tool(spec: ToolSpec) -> None:
        print(spec.name)
        print(f"  Description: {spec.description}")
        print(f"  Args: {spec.args_description}")
        print(f"  Permission: {spec.permission}")
        print(
            "  Requires confirmation: "
            f"{'yes' if spec.requires_confirmation else 'no'}"
        )
        print()
    
    for spec in allowed_tools:
        print_tool(spec)

    return 0


def run_runs_command(config: Config) -> int:
    """List saved agent runs, newest first."""
    runs = list_agent_runs(config)

    if not runs:
        print("No agent runs saved.")
        return 0

    print("Saved agent runs:")
    print()

    for run_dir in runs:
        metadata = read_agent_run_metadata(run_dir)

        if metadata is None:
            print(f"{run_dir.name} - metadata unavailable")
            continue

        status = metadata.get("status", "unknown")
        model = metadata.get("model", "unknown")
        provider = metadata.get("provider", "unknown")

        print(f"{run_dir.name}")
        print(f"  Status: {status}")
        print(f"  Model: {provider} / {model}")
        print()

    return 0


def run_run_show_command(config: Config, run_id: str) -> int:
    """Show one saved agent run by ID."""
    runs_root = config.paths.database.parent / "runs"
    run_dir = runs_root / run_id

    if not run_dir.exists() or not run_dir.is_dir():
        print(f"No agent run found with ID {run_id}.")
        return 0

    metadata = read_agent_run_metadata(run_dir)
    prompt_path = run_dir / "prompt.txt"
    final_path = run_dir / "final.md"
    trace_path = run_dir / "trace.md"

    print(f"Agent run: {run_id}")
    print()

    if metadata is not None:
        print("Metadata:")
        print(f"  Status: {metadata.get('status', 'unknown')}")
        print(f"  Model: {metadata.get('provider', 'unknown')} / {metadata.get('model', 'unknown')}")
        print(f"  Started: {metadata.get('started_at', 'unknown')}")
        print(f"  Finished: {metadata.get('finished_at', 'unknown')}")
        print()

    if prompt_path.exists():
        print("Prompt:")
        print(prompt_path.read_text(encoding="utf-8").strip())
        print()

    if final_path.exists():
        print("Final answer:")
        print(final_path.read_text(encoding="utf-8").strip())
        print()

    if trace_path.exists():
        print("Trace:")
        print(trace_path.read_text(encoding="utf-8").strip())

    return 0


def run_uncensored_command(config: Config, user_prompt: str) -> int:
    response = ask_once(
        config,
        user_prompt,
        model=config.model.uncensored,
    )

    print(response)

    return 0
