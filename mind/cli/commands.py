from pathlib import Path

from mind import __version__
from mind.core.config import Config
from mind.memory import add_memory, list_memories, delete_memory
from mind.workspace import ensure_workspace, list_workspace_files
from mind.core.diagnostics import is_ollama_running
from mind.runtime.ask import ask_once
from mind.runtime.chat import run_chat
from mind.agent import run_agent
from mind.tools import TOOL_REGISTRY, ToolSpec


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

    print(config.assistant.name)
    print(config.assistant.description)
    print()
    print(f"Status: v{__version__} installed.")

    return 0


def run_doctor_command(config: Config) -> int:
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

    return 0


def run_remember_command(config: Config, text: str) -> int:
    """Adds a memory to Mind's memory database."""
    add_memory(config, text)
    print("Memory saved.")

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


def run_ask_command(config: Config, prompt: str, files: list[str] | None) -> int:
    """Give Mind a single prompt."""
    file_paths = [Path(file) for file in files] if files else None
    res = ask_once(config, prompt, file_paths)
    print(res)

    return 0


def run_chat_command(config: Config) -> int:
    """Run a chat session with Mind."""
    run_chat(config)

    return 0


def run_agent_command(config: Config, prompt: str) -> int:
    """Run Mind's agent mode with controlled tool execution."""
    response = run_agent(config, prompt)
    print(response)

    return 0


def run_tools_command() -> int:
    """List all tools currently available to Mind."""
    if not TOOL_REGISTRY:
        print("There are no available tools for Mind.")
        return 0

    print("Available tools:")
    print()

    def print_tool(spec: ToolSpec) -> None:
        print(spec.name)
        print(f"  Description: {spec.description}")
        print(f"  Args: {spec.args_description}")
        print(f"  Permission: {spec.permission}")
        print()
    
    for _, spec in TOOL_REGISTRY.items():
        if spec.available_to_agent:
            print_tool(spec)         

    return 0
