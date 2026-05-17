# Mind

Mind is a lightweight local-first personal AI assistant runtime.

It is designed to run on your own machine, use a local model through Ollama, read files from a controlled workspace, maintain persistent memory, and expose a safe tool system for extending the assistant with custom Python capabilities.

Mind is not meant to be a thin wrapper around an API. The goal is to build a local-first assistant architecture that stays understandable, extensible, inspectable, and safe.

## Current Status

Mind is currently a v0.1 command-line prototype with a package-based internal architecture.

Implemented:

- `mind`
- `mind doctor`
- `mind ask <prompt>`
- `mind ask <prompt> --files <workspace-relative-path> [more-files...]`
- `mind files`
- `mind chat`
- `mind agent <task>`
- `mind remember <text>`
- `mind memories`
- `mind forget <memory-id>`
- `mind tools`
- Basic assistant identity prompt
- Config-driven local model settings
- Workspace-relative file access
- Safe workspace file reading
- Centralized context building
- SQLite-backed persistent memory
- Memory context injection into prompts
- Experimental automatic memory extraction during chat
- Bounded tool-using agent loop
- Tool registry for controlled Python capabilities
- Workspace, memory, and internet tool modules
- Read-only external API tool example
- Unit tests for CLI routing, context building, memory, workspace access, prompt construction, agent behavior, and tool execution

## Requirements

- Python 3.11+
- Ollama running locally
- A configured local model available through Ollama

The default model is configured in:

```text
configs/config.toml
```

## Installation

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Configuration

Mind uses a TOML config file:

```text
configs/config.toml
```

Example:

```toml
[assistant]
name = "Mind"
description = "A lightweight local-first personal AI assistant."

[paths]
workspace = "workspace"
database = "data/mind.db"

[model]
provider = "ollama"
base_url = "http://localhost:11434"
default = "gemma4:e4b"

[memory]
auto_memory = true
max_relevant_memories = 8

[context]
max_workspace_chars = 12000
```

## Usage

Show the default home output:

```bash
mind
```

Check basic environment status:

```bash
mind doctor
```

Ask a one-shot question:

```bash
mind ask "What should I work on next?"
```

Ask using one or more files from the workspace as context:

```bash
mind ask "Summarize this file" --files notes.txt
```

List files inside the controlled workspace:

```bash
mind files
```

Start an interactive chat session:

```bash
mind chat
```

Run the tool-using agent:

```bash
mind agent "What files are in my workspace?"
```

Run the tool-using agent with trace output:

```bash
mind agent --trace "What files are in my workspace?"
```

Store a manual memory:

```bash
mind remember "The project is named Mind."
```

List saved memories:

```bash
mind memories
```

Delete a memory by ID:

```bash
mind forget 1
```

List available tools:

```bash
mind tools
```

## Workspace

Mind only reads files from the configured workspace directory:

```text
workspace/
```

File paths passed to `--files` are interpreted as workspace-relative paths.

For example:

```bash
mind ask "Summarize this" --files project-notes.md
```

reads:

```text
workspace/project-notes.md
```

Mind rejects paths that attempt to escape the workspace, including parent-directory traversal and symlink escapes.

## Memory

Mind supports persistent memory through SQLite.

The database path is configured in:

```toml
[paths]
database = "data/mind.db"
```

Manual memory commands:

```bash
mind remember "User prefers concise explanations."
mind memories
mind forget 1
```

During chat, Mind can also attempt experimental automatic memory extraction. After each assistant response, Mind asks the local model to extract durable facts from the conversation turn. Extracted memories are stored in SQLite and can be injected into future prompts.

Automatic memory extraction is controlled by:

```toml
[memory]
auto_memory = true
max_relevant_memories = 8
```

This feature is experimental. It currently uses simple recent-memory retrieval, not semantic search or embeddings.

## Agent and Tools

Mind includes a simple bounded agent loop.

The agent asks the local model to return one of two JSON response types:

```json
{"type": "tool_call", "tool": "workspace.read_file", "args": {"path": "notes.txt"}}
```

or:

```json
{"type": "final", "answer": "Your answer here."}
```

When the model requests a tool, Mind checks the tool name against a known registry, validates the basic argument shape, runs the approved Python function, feeds the text result back to the model, and then asks for either another tool call or a final answer.

The current tool registry includes:

```text
workspace.list_files
workspace.read_file
memory.list
internet.github_zen
```

The important design rule is that the model does not directly execute arbitrary code. It may request a tool, but Python decides whether that tool exists and how it runs.

## Architecture

Mind is currently organized around a package-based architecture:

```text
CLI
↓
Runtime modes
  - ask
  - chat
  - agent
↓
Core infrastructure
  - config
  - context
  - prompts
  - diagnostics
  - LLM client
↓
Agent loop
↓
Tool registry
↓
Tools
  - workspace
  - memory
  - internet
↓
Workspace / SQLite / External APIs
```

Current package responsibilities:

```text
mind/cli/        CLI parser and command handlers
mind/runtime/    ask and chat runtime flows
mind/core/       config, context, prompts, diagnostics, and LLM client
mind/agent/      bounded agent loop, protocol parsing, and agent prompts
mind/tools/      tool registry and tool implementations
mind/memory/     SQLite memory store and memory extraction
mind/workspace/  safe workspace file access
```

## Testing

Run the test suite:

```bash
pytest
```

The tests currently cover:

- CLI command routing
- Context building
- Ask runtime behavior
- Chat loop behavior
- Manual memory storage
- Memory deletion
- Memory formatting
- Automatic memory extraction parsing
- Workspace file listing
- Safe workspace file reading
- Prompt construction
- Config loading
- Agent JSON parsing
- Agent tool loop behavior
- Tool registry behavior
- Workspace and memory tools

## Development Roadmap

Planned development stages:

1. Basic CLI and local model interaction
2. Safe workspace file access
3. Centralized context construction
4. Persistent memory
5. Bounded agent loop
6. Tool registry and controlled tool execution
7. Tool metadata and permissions
8. Agent trace/debug mode
9. Memory review, deduplication, and schema improvements
10. Safe local write tools
11. Optional retrieval-augmented generation over local files and memories
12. Optional integrations for email, web search, project workflows, and automation

## Design Goals

Mind should be:

- Local-first
- Understandable
- Extensible
- Safe by default
- Useful from the command line
- Built around clear internal layers
- Easy to extend with small Python tools
- Capable of growing into a more powerful personal assistant without becoming a messy wrapper script
