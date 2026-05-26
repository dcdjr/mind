# Architecture

Mind is a lightweight local-first personal AI assistant runtime.

The project is organized around small layers: CLI parsing, runtime modes, core infrastructure, memory, workspace/codebase access, an agent loop, and a permissioned tool registry. The central design rule is that the model may request capabilities, but Python decides what exists, what is allowed, and how it runs.

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
Memory / Workspace / Codebase / Tool Context
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
Permission check
↓
Optional confirmation callback
↓
Approved Python tool function
↓
Structured ToolResult
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
    confirmation.py

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
    trace.py

  tools/
    __init__.py
    registry.py
    spec.py
    result.py
    workspace.py
    memory.py
    codebase.py
    internet.py

  memory/
    __init__.py
    store.py
    extractor.py

  workspace/
    __init__.py
    files.py

  codebase/
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

The runtime package owns user-facing assistant modes and terminal-specific behavior.

```text
mind/runtime/ask.py            one-shot prompt execution
mind/runtime/chat.py           interactive chat loop and automatic memory extraction
mind/runtime/confirmation.py   terminal confirmation callback for confirmed tools
```

Runtime code may prompt the user. Tool registry code should not directly call `input()`.

### `mind/core/`

The core package owns shared infrastructure used by the rest of the system.

```text
mind/core/config.py       TOML config loading and typed config dataclasses
mind/core/context.py      memory/workspace context assembly
mind/core/diagnostics.py  environment checks
mind/core/llm.py          Ollama client calls
mind/core/prompt.py       base system prompt and message construction
```

`Config` currently includes assistant, path, model, memory, context, project, and tool-permission settings.

### `mind/agent/`

The agent package owns the tool-using agent loop.

```text
mind/agent/loop.py      bounded agent execution loop
mind/agent/protocol.py  JSON extraction/parsing from model output
mind/agent/prompts.py   agent-specific system prompt
mind/agent/trace.py     human-readable trace formatting
```

The agent uses a strict JSON protocol. The model may return either a tool call:

```json
{"type": "tool_call", "tool": "workspace.read_file", "args": {"path": "notes.txt"}}
```

or a final answer:

```json
{"type": "final", "answer": "Your answer here."}
```

The agent loop is bounded by `MAX_AGENT_STEPS` to prevent infinite tool-call loops. It supports one repair attempt for invalid agent JSON and can include prior chat messages when running in tool-enabled chat. Trace output previews long tool results and invalid raw model responses so debugging output remains readable.

### `mind/tools/`

The tools package owns Mind's controlled capability surface.

```text
mind/tools/registry.py   tool registry, public tool runner, prompt formatting
mind/tools/spec.py       ToolSpec and permission-level types
mind/tools/result.py     structured ToolResult object
mind/tools/workspace.py  workspace-related tools
mind/tools/codebase.py   codebase-related tools
mind/tools/memory.py     memory-related tools
mind/tools/internet.py   external read-only tools
```

The current registry includes:

```text
workspace.list_files
workspace.read_file
workspace.write_file
workspace.append_file
memory.list
codebase.list_files
codebase.read_file
internet.github_zen
project.status
project.devlog
```

Tools follow a common function shape:

```python
def tool_name(config: Config, args: dict[str, Any]) -> str:
    ...
```

The model does not execute arbitrary Python. It requests a tool by name, and Mind only runs tools that exist in the registry and pass permission checks.

### `mind/memory/`

The memory package owns persistent memory and memory extraction.

```text
mind/memory/store.py      SQLite-backed memory storage
mind/memory/extractor.py  model-output parsing for automatic memory extraction
```

Current memory storage tracks text, normalized text for deduplication, review metadata, timestamps, and basic usage fields:

```text
id
text
normalized_text
kind
source
status
confidence
created_at
updated_at
last_used_at
use_count
```

Manual memories are stored as confirmed, high-confidence memories. Auto-extracted chat memories are stored separately with `source = "chat_auto"`, `status = "auto_extracted"`, and lower confidence so a future review flow can distinguish them.

Future memory improvements may include:

```text
review workflow
semantic retrieval
usage tracking updates
```

### `mind/workspace/`

The workspace package owns safe local file access inside the configured workspace.

```text
mind/workspace/files.py  workspace creation, listing, safe reading, safe writing, and safe appending
```

Workspace paths are interpreted relative to the configured workspace directory. The reader/writer/appender reject absolute paths, parent-directory traversal, and symlink escapes. Write and append operations are size-limited.

### `mind/codebase/`

The codebase package owns read-only project inspection.

```text
mind/codebase/files.py  project file listing and safe project-relative file reading
```

Codebase tools read from the configured project root and ignore runtime/build/cache paths such as `.git`, `.venv`, `data`, `workspace`, `dist`, and `build`.

## Tool Execution Boundary

Mind's tool system is intentionally conservative.

```text
Model request
↓
JSON parser
↓
Tool name lookup
↓
Permission check
↓
Optional confirmation callback
↓
Argument validation inside tool wrapper
↓
Approved Python function
↓
Structured ToolResult
```

This boundary matters because the model is not trusted to execute code directly. The model can request capabilities, but Python decides what is allowed.

## Confirmation Boundary

Confirmed tools are handled through dependency injection:

```text
interactive CLI/runtime
↓
confirm_tool_run(spec)
↓
run_agent(..., confirm=confirm_tool_run)
↓
run_tool(..., confirm=confirm_tool_run)
```

If a tool requires confirmation and no confirmation handler is provided, `run_tool()` fails closed with a failed `ToolResult`. This keeps terminal UI behavior out of the core registry and makes tests, future APIs, and future non-terminal runtimes easier to support.

## Current Safety Properties

Mind currently includes these safety boundaries:

```text
- workspace-relative file access
- project-root-relative codebase access
- rejection of path traversal outside workspace/project root
- rejection of symlink escapes
- ignored runtime/build/cache paths for codebase tools
- default-disabled local write permission
- confirmation-required local write tools
- overwrite protection for workspace writes
- size caps on workspace writes/appends and codebase reads
- bounded agent loop
- explicit tool registry
- structured agent protocol validation
- structured ToolResult objects
- configurable tool permission enforcement
- no arbitrary shell execution
- no external write tools
```

## Planned Foundation Improvements

Before high-impact integrations, the foundation should be strengthened in this order:

```text
1. memory review workflow
2. semantic memory retrieval
3. mission/run history
4. read-only Git/project status tools
5. controlled test runner with explicit local-execute permission
6. model provider abstraction
```

## Long-Term Direction

Mind is intended to grow into a local-first assistant runtime.

Possible future directions include:

```text
- semantic memory retrieval
- local file RAG
- persistent missions/checkpoints
- richer project status generation
- GitHub tooling
- email draft creation
- calendar tools
- browser or web-search tools
- cloud/local model routing
```

The core architectural principle is that new capabilities should be added as small, controlled tools rather than as unrestricted model behavior.
