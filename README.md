# Mind

Mind is a lightweight local-first personal AI assistant runtime.

It is designed to run on your own machine, use a local model through Ollama, read files from a controlled workspace, maintain persistent memory, and expose a safe permissioned tool system for extending the assistant with custom Python capabilities.

Mind is not meant to be a thin wrapper around an API. The goal is to build a local-first assistant architecture that stays understandable, extensible, inspectable, and safe.

## Current Status

Mind is currently a v0.2 command-line prototype with a package-based internal architecture.

Implemented:

- `mind`
- `mind doctor`
- `mind ask <prompt>`
- `mind ask <prompt> --files <workspace-relative-path> [more-files...]`
- `mind ask --tools <prompt>`
- `mind ask --tools --trace <prompt>`
- `mind files`
- `mind chat`
- `mind chat --tools`
- `mind chat --tools --trace`
- `mind agent <task>`
- `mind agent --trace <task>`
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
- Strict JSON agent protocol parsing
- One retry for invalid agent protocol output
- Structured `ToolResult` objects
- Tool registry for controlled Python capabilities
- Tool permission metadata
- Configurable tool permission enforcement
- Workspace, memory, and internet tool modules
- Read-only external API tool example
- Agent trace/debug output
- Unit tests for CLI routing, context building, memory, workspace access, prompt construction, agent behavior, tool execution, and tool permissions

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
default = "gemma4:e2b"

[memory]
auto_memory = true
max_relevant_memories = 8

[context]
max_workspace_chars = 12000

[tools]
allow_external_read = true
allow_local_write = false
allow_external_write = false
allow_dangerous = false
require_confirmation = true
```

### Tool Permission Settings

Mind classifies tools by permission level. The current permission levels are:

```text
read_only
external_read
local_write
external_write
dangerous
```

Current default policy:

```text
read_only        allowed
external_read    allowed
local_write      disabled
external_write   disabled
dangerous        disabled
```

This matters because the model is not trusted to execute arbitrary actions. The model may request a tool, but Mind checks the tool registry and configured permission policy before running it.

The `[tools]` config section controls which classes of tools are allowed:

```toml
[tools]
allow_external_read = true
allow_local_write = false
allow_external_write = false
allow_dangerous = false
require_confirmation = true
```

For example, `internet.github_zen` is an `external_read` tool. If `allow_external_read = false`, Mind should block that tool and return a failed `ToolResult` instead of making the external request.

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

Start chat with tools enabled:

```bash
mind chat --tools
```

Start chat with tools and trace output enabled:

```bash
mind chat --tools --trace
```

Run the tool-using agent:

```bash
mind agent "What files are in my workspace?"
```

Run the tool-using agent with trace output:

```bash
mind agent --trace "What files are in my workspace?"
```

Run tool-enabled one-shot ask mode:

```bash
mind ask --tools "What files are in my workspace?"
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

The agent asks the local model to return one of two JSON response types.

Tool call:

```json
{"type": "tool_call", "tool": "workspace.read_file", "args": {"path": "notes.txt"}}
```

Final answer:

```json
{"type": "final", "answer": "Your answer here."}
```

When the model requests a tool, Mind:

1. Parses the model output as JSON.
2. Validates the response as either a `ToolCall` or `FinalAnswer`.
3. Looks up the requested tool in the registry.
4. Checks the tool's permission level against config.
5. Runs only the approved Python function.
6. Wraps the result in a structured `ToolResult`.
7. Feeds the result back to the model.
8. Asks for either another tool call or a final answer.

The current tool registry includes:

```text
workspace.list_files
workspace.read_file
memory.list
internet.github_zen
```

The important design rule is that the model does not directly execute arbitrary code. It may request a tool, but Python decides whether that tool exists, whether it is permitted, and how it runs.

## Agent Trace Mode

Trace mode shows intermediate agent behavior.

Example:

```bash
mind agent --trace "What files are in my workspace?"
```

Trace output may include:

```text
Agent trace:

Step 1
Action: tool_call
Tool: workspace.list_files
Args: {}
Success: yes
Result:
Workspace files:
- notes.txt

Step 2
Action: final
Answer: Your workspace contains notes.txt.
```

Trace mode is useful for debugging tool selection, permission failures, protocol failures, and agent loops.

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
mind/agent/      bounded agent loop, protocol parsing, trace output, and agent prompts
mind/tools/      tool registry, tool specs, tool results, permission checks, and tool implementations
mind/memory/     SQLite memory store and memory extraction
mind/workspace/  safe workspace file access
```

## Safety Model

Mind's current safety boundaries:

```text
- workspace-relative file access
- rejection of path traversal outside workspace
- rejection of symlink escapes outside workspace
- bounded agent loop
- explicit tool registry
- structured agent protocol validation
- structured tool results
- configurable tool permission enforcement
- no arbitrary shell execution
- no local write tools enabled yet
- no external write tools enabled yet
```

Mind is intentionally conservative. New capabilities should be added as small controlled tools, not as unrestricted model behavior.

## Testing

Run the test suite:

```bash
pytest
```

Run targeted tests:

```bash
pytest tests/test_workspace.py
pytest tests/test_tools.py
pytest tests/test_agent.py
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
- Agent protocol retry behavior
- Agent tool loop behavior
- Agent trace output
- Tool registry behavior
- Structured tool results
- Tool permission enforcement
- Workspace and memory tools

## Development Roadmap

Planned development stages:

1. Basic CLI and local model interaction
2. Safe workspace file access
3. Centralized context construction
4. Persistent memory
5. Bounded agent loop
6. Tool registry and controlled tool execution
7. Tool metadata and permission enforcement
8. Agent trace/debug mode
9. Memory review, deduplication, and schema improvements
10. Safe local write tools
11. Project/devlog/status tools
12. Optional retrieval-augmented generation over local files and memories
13. Optional integrations for GitHub, email drafts, calendar, web search, project workflows, and automation

Near-term next steps:

```text
1. Add confirmation metadata to ToolSpec.
2. Show confirmation metadata in `mind tools`.
3. Add safe workspace write tools.
4. Add safe workspace append tools.
5. Add project devlog/status tools.
6. Improve memory schema and review workflow.
```

## Design Goals

Mind should be:

- Local-first
- Understandable
- Extensible
- Safe by default
- Useful from the command line
- Built around clear internal layers
- Easy to extend with small Python tools
- Explicit about what the model can and cannot do
- Capable of growing into a more powerful personal assistant without becoming a messy wrapper script
