# Mind

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Mind is a lightweight local-first personal AI assistant runtime.

It is designed to run on your own machine, use a local model through Ollama, read and write files only through controlled local boundaries, maintain persistent memory, and expose a safe permissioned tool system for extending the assistant with custom Python capabilities.

Mind is not meant to be a thin wrapper around an API. The goal is to build a local-first assistant architecture that stays understandable, extensible, inspectable, and safe.

## Current Status

Mind is currently a v0.3 command-line prototype with a package-based internal architecture.

Implemented:

- `mind`
- `mind doctor`
- `mind inspect`
- `mind ask <prompt>`
- `mind ask <prompt> --files <workspace-relative-path> [more-files...]`
- `mind ask --uncensored <prompt>`
- `mind ask --tools <prompt>`
- `mind ask --tools --trace <prompt>`
- `mind files`
- `mind chat`
- `mind chat --uncensored`
- `mind chat --tools`
- `mind chat --tools --trace`
- `mind agent <task>`
- `mind agent --trace <task>`
- `mind remember <text>`
- `mind memories`
- `mind memories --status <confirmed|auto_extracted|rejected|archived>`
- `mind forget <memory-id>`
- `mind memory confirm <memory-id>`
- `mind memory reject <memory-id>`
- `mind memory archive <memory-id>`
- `mind memory delete <memory-id>`
- `mind memory backfill`
- `mind tools`
- `mind runs`
- `mind run show <run-id>`
- `mind uncensored <prompt>`
- Basic assistant identity prompt
- Config-driven local model settings
- Workspace-relative file access
- Safe workspace file reading
- Safe workspace file writing and appending
- Project-root-relative codebase reading tools
- Centralized context building
- SQLite-backed persistent memory
- Memory context injection into prompts
- Experimental automatic memory extraction during chat
- Semantic memory embedding backfill
- Bounded tool-using agent loop
- Tool-enabled chat history
- File-based agent run persistence
- Strict JSON agent protocol parsing
- One repair attempt for invalid agent protocol output
- Structured `ToolResult` objects
- Tool registry for controlled Python capabilities
- Tool permission metadata
- Configurable tool permission enforcement
- Confirmation metadata for higher-impact tools
- Interactive confirmation callback for confirmed tools
- Workspace, codebase, memory, and internet tool modules
- Read-only external API tool example
- Project status and devlog tools
- Read-only Git status tool
- Agent trace/debug output
- Unit tests for CLI routing, context building, memory, workspace access, codebase access, prompt construction, agent behavior, project tools, tool execution, and tool permissions

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
default = "qwen3-coder:30b"
cloud = "gpt-oss:120b-cloud"
uncensored = "oroboroslabs/qwen3.5-abliterated-47-4:latest"
small = "qwen2.5:1.5b"

[memory]
auto_extract = true
inject_context = true
max_relevant_memories = 8
min_similarity = 0.3

[embeddings]
provider = "ollama"
model = "nomic-embed-text"
enabled = true

[context]
max_workspace_chars = 12000

[project]
root = "."

[tools]
allow_external_read = true
allow_local_write = true
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
local_write      allowed, with confirmation for confirmed tools
external_write   disabled
dangerous        disabled
```

This matters because the model is not trusted to execute arbitrary actions. The model may request a tool, but Mind checks the tool registry and configured permission policy before running it.

The `[tools]` config section controls which classes of tools are allowed:

```toml
[tools]
allow_external_read = true
allow_local_write = true
allow_external_write = false
allow_dangerous = false
require_confirmation = true
```

For example, `internet.github_zen` is an `external_read` tool. If `allow_external_read = false`, Mind blocks that tool and returns a failed `ToolResult` instead of making the external request.

`world.omens` is also an `external_read` tool. It reads fixed public Earth and space monitoring APIs and accepts an optional `max_items` integer.

`workspace.write_file`, `workspace.append_file`, and `project.devlog` are `local_write` tools. In the default config they are allowed, but they still require confirmation when `require_confirmation = true`.

## Usage

Show the default home output:

```bash
mind
```

Check basic environment status:

```bash
mind doctor
```

Print Mind's config and runtime state without calling the model:

```bash
mind inspect
```

Ask a one-shot question:

```bash
mind ask "What should I work on next?"
```

Ask using the configured uncensored model:

```bash
mind ask --uncensored "What should I work on next?"
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

In normal chat, Mind starts with a base system message and refreshes saved-memory
context before each user turn. That means semantic memory retrieval uses the
latest message as the query instead of injecting unrelated recent memories at
session startup.

Start chat using the configured uncensored model:

```bash
mind chat --uncensored
```

Start chat with tools enabled:

```bash
mind chat --tools
```

Tool-enabled chat sends each turn through the bounded agent loop and preserves
prior turns as agent context.

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

List memories by review status:

```bash
mind memories --status auto_extracted
```

Delete a memory by ID:

```bash
mind forget 1
```

Review, backfill, or remove memory data:

```bash
mind memory confirm 1
mind memory reject 2
mind memory archive 3
mind memory delete 3
mind memory backfill
```

List available tools:

```bash
mind tools
```

List saved agent runs:

```bash
mind runs
```

Show a saved agent run:

```bash
mind run show 20260603-120000-deadbeef
```

Mind can run an explicitly configured alternate model:

```bash
mind uncensored "prompt"
```

## Workspace

Mind reads, writes, and appends files only inside the configured workspace directory:

```text
workspace/
```

File paths passed to `--files` and workspace tools are interpreted as workspace-relative paths.

For example:

```bash
mind ask "Summarize this" --files project-notes.md
```

reads:

```text
workspace/project-notes.md
```

Mind rejects paths that attempt to escape the workspace, including absolute paths, parent-directory traversal, and symlink escapes.

Workspace write tools are conservative:

```text
workspace.write_file
workspace.append_file
```

Safety behavior:

```text
- write/append tools require confirmation when confirmation is enabled
- write refuses to overwrite existing files unless overwrite=true
- append can create missing files only when create=true
- content size is capped
- parent directories are created only after the target path passes workspace-boundary checks
```

## Codebase Tools

Mind has read-only codebase tools for inspecting the configured project root:

```text
codebase.list_files
codebase.read_file
```

The project root is configured with:

```toml
[project]
root = "."
```

Codebase tools ignore runtime/build/cache paths such as:

```text
.git
.venv
__pycache__
.pytest_cache
data
workspace
build
dist
*.egg-info
```

These tools are intended to let Mind inspect its own repo without arbitrary shell access.

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
mind memories --status auto_extracted
mind forget 1
mind memory confirm 1
mind memory reject 2
mind memory archive 3
mind memory delete 3
```

Memories are stored with normalized text for deduplication plus metadata for kind, source, review status, confidence, timestamps, and use counts. Storage helpers can resolve a normalized memory back to its database ID so derived data such as embeddings can be attached after insertion. Valid statuses are `confirmed`, `auto_extracted`, `rejected`, and `archived`. `mind memories` shows all stored memory records with metadata, while prompt injection and semantic retrieval use only active memories with `confirmed` or `auto_extracted` status.

The database also has a `memory_embeddings` table keyed by memory id and embedding model so semantic retrieval can store vectors without duplicating memory rows. The single-memory indexing helper resolves an existing memory ID, generates its embedding, and stores the vector using the configured model. When embeddings are enabled, `mind remember` indexes newly saved manual memories immediately. Embedding failures do not discard the saved memory; Mind prints a warning and `mind memory backfill` remains the recovery path. Embedding helpers can also store or replace one vector per memory/model pair, list active memories with vectors, and list active memories still missing vectors for a specific model. Retrieval embeds the query with the configured embedding model, ranks stored memory vectors by cosine similarity, and returns the highest-ranked memory IDs and text. Manual memories are saved as `source = "manual"`, `status = "confirmed"`, and `confidence = 1.0`.

During chat, Mind can also attempt experimental automatic memory extraction. After each assistant response, Mind asks the local model to extract durable facts from the conversation turn. Extracted memories are stored as `source = "chat_auto"`, `status = "auto_extracted"`, and `confidence = 0.6`. When embeddings are enabled, newly stored extracted memories are indexed immediately; duplicate memories are skipped, and indexing failures do not interrupt chat. Extracted memories can then be injected into future prompts when `inject_context` is enabled. Normal chat starts with a base system message, then refreshes saved-memory context before each user turn using that turn's text as the retrieval query. Query-specific prompts prefer semantic retrieval when embeddings are enabled, and fall back to recent memories if retrieval is unavailable.

Automatic memory extraction and prompt injection are controlled separately by:

```toml
[memory]
auto_extract = true
inject_context = true
max_relevant_memories = 8
min_similarity = 0.3
```

`min_similarity` prevents semantic retrieval from injecting memories whose cosine
similarity score is below the configured threshold. If retrieval itself fails,
Mind falls back to recent memories.

Semantic embedding generation is configured separately:

```toml
[embeddings]
provider = "ollama"
model = "nomic-embed-text"
enabled = true
```

The embedding helper currently supports Ollama and returns one numeric vector for each input text. It validates empty input, disabled embeddings, unsupported providers, provider failures, and malformed embedding responses before semantic retrieval consumes the vector.

## Agent and Tools

Mind includes a bounded agent loop. Tool calls, total model calls, and invalid
protocol repairs have separate limits so retries and future reasoning stages
cannot create an unbounded run. The current defaults allow 10 tool calls, 20
total model calls, and 3 protocol repair retries.

The agent asks the local model to return one of two JSON response types.

Tool call:

```json
{"type": "tool_call", "tool": "<available_tool_name>", "args": {"<arg_name>": "<arg_value>"}}
```

Final answer:

```json
{"type": "final", "answer": "<final-answer-text>"}
```

When the model requests a tool, Mind:

1. Parses the model output as JSON.
2. Validates the response as either a `ToolCall` or `FinalAnswer`.
3. Looks up the requested tool in the registry.
4. Checks the tool's permission level against config.
5. Runs confirmation if the tool requires it and confirmation is enabled.
6. Runs only the approved Python function.
7. Wraps the result in a structured `ToolResult`.
8. Feeds the result back to the model.
9. Asks for either another tool call or a final answer.

The current tool registry includes:

```text
workspace.list_files
workspace.read_file
workspace.write_file
workspace.append_file
memory.list
codebase.list_files
codebase.read_file
internet.github_zen
world.omens
project.status
project.devlog
git.status
```

`project.status` returns a read-only project summary, including version, configured model, workspace/database/project paths, workspace file count, memory count, tool counts, and configured tool safety flags.

`project.devlog` appends a dated Markdown entry to `workspace/devlog.md`. It takes a required `summary` string and an optional `next_steps` list of strings, uses the same controlled workspace append boundary as `workspace.append_file`, and requires local-write permission plus confirmation.

`git.status` returns read-only `git status --short --branch` output for the configured project root. It accepts no arguments, does not expose arbitrary command execution, and truncates very large status output to 20,000 characters.

The important design rule is that the model does not directly execute arbitrary code. It may request a tool, but Python decides whether that tool exists, whether it is permitted, whether it needs confirmation, and how it runs.

## Agent Run History

Tool-enabled one-shot prompts are saved under the data directory:

```text
data/runs/<run-id>/
```

Each saved run contains:

```text
metadata.json
prompt.txt
final.md
trace.md
```

Use `mind runs` to list saved runs and `mind run show <run-id>` to inspect the prompt, final answer, trace output, and metadata. When trace mode is disabled, `trace.md` records that no trace was enabled for the run.

## Confirmation Model

Confirmed tools do not call `input()` from the tool registry. Instead, interactive runtimes pass a confirmation callback into the agent/tool runner.

```text
CLI/runtime confirmation callback
↓
run_agent(..., confirm=confirm_tool_run)
↓
run_tool(..., confirm=confirm_tool_run)
```

If a confirmed tool is called without a confirmation handler, Mind fails closed and returns a failed `ToolResult`.

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
Result preview:
Workspace files:
- notes.txt

Step 2
Action: final
Answer: Your workspace contains notes.txt.
```

Trace mode is useful for debugging tool selection, permission failures, protocol failures, confirmations, and agent loops. Long tool outputs and raw invalid model responses are shown as previews so terminal traces stay readable.

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
  - embeddings
  - LLM client
↓
Agent loop
↓
Tool registry
↓
Tools
  - workspace
  - codebase
  - memory
  - internet
↓
Workspace / Codebase / SQLite / External APIs
```

Current package responsibilities:

```text
mind/cli/        CLI parser and command handlers
mind/runtime/    ask/chat runtime flows and interactive confirmation
mind/core/       config, context, prompts, diagnostics, embeddings, and LLM client
mind/agent/      bounded agent loop, protocol parsing, trace output, and agent prompts
mind/tools/      tool registry, tool specs, tool results, permission checks, and tool implementations
mind/memory/     SQLite memory store and memory extraction
mind/workspace/  safe workspace file access
mind/codebase/   safe read-only codebase file access
```

## Safety Model

Mind's current safety boundaries:

```text
- workspace-relative file access
- project-root-relative codebase access
- rejection of path traversal outside workspace/project root
- rejection of symlink escapes
- ignored runtime/build/cache paths for codebase tools
- confirmation-required local write tools
- overwrite protection for workspace writes
- content size caps for workspace writes/appends
- bounded agent loop
- explicit tool registry
- structured agent protocol validation
- structured tool results
- configurable tool permission enforcement
- no arbitrary shell execution
- no external write tools enabled
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
pytest tests/test_codebase.py
pytest tests/test_tools.py
pytest tests/test_agent.py
```

The tests currently cover:

- CLI command routing
- Context building
- Ask runtime behavior
- Chat loop behavior
- Manual memory storage
- Memory metadata storage
- Memory deduplication
- Memory deletion
- Memory review status updates
- Memory embedding backfill
- Agent run persistence and inspection commands
- Memory formatting
- Memory embedding storage and lookup
- Memory semantic retrieval ranking
- Automatic memory extraction parsing
- Embedding generation and provider response validation
- Workspace file listing
- Safe workspace file reading, writing, and appending
- Codebase file listing and reading
- Prompt construction
- Config loading
- Agent JSON parsing
- Agent protocol retry behavior
- Agent tool loop behavior
- Agent trace output
- Tool registry behavior
- Read-only Git status tool behavior
- Structured tool results
- Tool permission enforcement
- Tool confirmation behavior
- Workspace, codebase, memory, and internet tools

## Development Roadmap

Planned development stages:

1. Basic CLI and local model interaction
2. Safe workspace file access
3. Centralized context construction
4. Persistent memory
   - Split automatic extraction from prompt context injection.
   - Wire semantic memory retrieval into context building with recent-memory fallback.
5. Bounded agent loop
6. Tool registry and controlled tool execution
7. Tool metadata and permission enforcement
8. Agent trace/debug mode
9. Safe local write and append tools
10. Read-only codebase tools
11. Project/devlog/status tools
12. Memory review workflow and retrieval improvements
13. Mission/run history
14. Controlled test-runner tool with explicit local-execute permission
15. Optional retrieval-augmented generation over local files and memories
16. Optional integrations for GitHub, email drafts, calendar, web search, project workflows, and automation

Near-term next steps:

```text
1. Wire semantic memory retrieval into context building.
2. Add mission/run history.
3. Add a controlled test-runner tool with explicit local-execute permission.
4. Add model provider abstraction.
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
