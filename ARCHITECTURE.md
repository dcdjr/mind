# Architecture

Mind is a lightweight local-first personal AI assistant runtime.

The project started as a small local CLI, but it is now organized around a package-based architecture designed to support memory, workspace context, agent loops, and safe tool execution.

## High-Level Flow

```text
CLI
↓
Runtime mode
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
Memory / Workspace / Agent Tool Context
↓
Local LLM
↓
Response
```

For agent mode, the flow is:

```text
User task
↓
Agent system prompt
↓
Local LLM returns strict JSON
↓
Agent protocol parser
↓
Tool registry
↓
Approved Python tool function
↓
Text tool result
↓
Local LLM final answer
```

## Package Layout

```text
mind/
  __init__.py

  cli/
    __init__.py
    parser.py
    commands.py

  runtime/
    __init__.py
    ask.py
    chat.py

  core/
    __init__.py
    config.py
    context.py
    diagnostics.py
    llm.py
    prompt.py

  agent/
    __init__.py
    loop.py
    protocol.py
    prompts.py

  tools/
    __init__.py
    registry.py
    workspace.py
    memory.py
    internet.py

  memory/
    __init__.py
    store.py
    extractor.py

  workspace/
    __init__.py
    files.py
```

## Package Responsibilities

### `mind/cli/`

The CLI package owns command-line parsing and command routing.

```text
mind/cli/parser.py    argparse parser and main entry point
mind/cli/commands.py  command handler functions
```

The package exposes `main` through `mind/cli/__init__.py` so the console script entry point can remain:

```toml
mind = "mind.cli:main"
```

### `mind/runtime/`

The runtime package owns user-facing assistant modes that are not strictly command parsing.

```text
mind/runtime/ask.py   one-shot prompt execution
mind/runtime/chat.py  interactive chat loop and automatic memory extraction
```

The CLI calls into runtime functions, but runtime code does not own CLI parsing.

### `mind/core/`

The core package owns shared infrastructure used by the rest of the system.

```text
mind/core/config.py       TOML config loading and typed config dataclasses
mind/core/context.py      memory/workspace context assembly
mind/core/diagnostics.py  environment checks
mind/core/llm.py          Ollama client calls
mind/core/prompt.py       base system prompt and message construction
```

This package should stay small and stable. Feature-specific logic should not be added here unless it is genuinely shared infrastructure.

### `mind/agent/`

The agent package owns the tool-using agent loop.

```text
mind/agent/loop.py      bounded agent execution loop
mind/agent/protocol.py  JSON extraction/parsing from model output
mind/agent/prompts.py   agent-specific system prompt
```

The agent uses a strict JSON protocol. The model may return either a tool call:

```json
{"type": "tool_call", "tool": "workspace.read_file", "args": {"path": "notes.txt"}}
```

or a final answer:

```json
{"type": "final", "answer": "Your answer here."}
```

The agent loop is bounded by `MAX_AGENT_STEPS` to prevent infinite tool-call loops.

### `mind/tools/`

The tools package owns Mind's controlled capability surface.

```text
mind/tools/registry.py   tool registry, public tool runner, prompt formatting
mind/tools/workspace.py  workspace-related tools
mind/tools/memory.py     memory-related tools
mind/tools/internet.py   external read-only tools
```

The current registry includes:

```text
workspace.list_files
workspace.read_file
memory.list
internet.github_zen
```

Tools follow a common function shape:

```python
def tool_name(config: Config, args: dict[str, Any]) -> str:
    ...
```

The model does not execute arbitrary Python. It requests a tool by name, and Mind only runs tools that exist in the registry.

### `mind/memory/`

The memory package owns persistent memory and memory extraction.

```text
mind/memory/store.py      SQLite-backed memory storage
mind/memory/extractor.py  model-output parsing for automatic memory extraction
```

Current memory storage is simple:

```text
id
text
created_at
```

Future memory improvements may include:

```text
kind
source
status
updated_at
deduplication
review workflow
semantic retrieval
```

### `mind/workspace/`

The workspace package owns safe local file access.

```text
mind/workspace/files.py  workspace creation, listing, and safe file reading
```

Workspace paths are interpreted relative to the configured workspace directory. The reader rejects parent-directory traversal and symlink escapes.

## Tool Execution Boundary

Mind's tool system is intentionally conservative.

```text
Model request
↓
JSON parser
↓
Tool name lookup
↓
Argument validation inside tool wrapper
↓
Approved Python function
↓
Plain text result
```

This boundary matters because the model is not trusted to execute code directly. The model can request capabilities, but Python decides what is allowed.

## Current Safety Properties

Mind currently includes these safety boundaries:

```text
- workspace-relative file access
- rejection of path traversal outside workspace
- rejection of symlink escapes outside workspace
- bounded agent loop
- explicit tool registry
- plain text tool results
- no arbitrary shell execution
- no external write tools
```

## Planned Foundation Improvements

Before adding high-impact integrations, the foundation should be strengthened in this order:

```text
1. ToolSpec metadata
2. `mind tools` command
3. agent trace mode
4. stronger agent protocol validation
5. structured ToolResult objects
6. tool permission levels
7. memory schema improvements
8. memory review and deduplication
9. safe workspace write tools
10. project status tools
```

## Long-Term Direction

Mind is intended to grow into a local-first assistant runtime.

Possible future directions include:

```text
- semantic memory retrieval
- local file RAG
- safe workspace writing
- project status generation
- GitHub tooling
- email draft creation
- calendar tools
- browser or web-search tools
- long-running task traces and checkpoints
```

The core architectural principle is that new capabilities should be added as small, controlled tools rather than as unrestricted model behavior.

