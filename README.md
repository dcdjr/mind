# Mind

Mind is a lightweight local-first personal AI assistant.

It is designed to run on your own machine, use a local model through Ollama, read files from a controlled workspace, maintain persistent memory, and provide a foundation for future custom tools and automation.

Mind is not meant to be a thin wrapper around an API. The goal is to build a local-first assistant architecture that stays understandable, extensible, and safe.

## Current Status

Mind is currently a v0.1 command-line prototype.

Implemented:

- `mind`
- `mind doctor`
- `mind ask <prompt>`
- `mind ask <prompt> --files <workspace-relative-path> [more-files...]`
- `mind files`
- `mind chat`
- `mind remember <text>`
- `mind memories`
- `mind forget <memory-id>`
- Basic assistant identity prompt
- Config-driven local model settings
- Workspace-relative file access
- Safe workspace file reading
- Centralized context builder
- Basic manual memory system
- SQLite-backed persistent memory
- Memory context injection into prompts
- Experimental automatic memory extraction during chat
- Unit tests for CLI routing, context building, memory, workspace access, prompt construction, and memory extraction parsing

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

Ask using a file from the workspace as context:

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

## Architecture

Mind is currently organized around a small layered architecture:

```text
CLI
↓
Context Builder
↓
Memory + Workspace
↓
Prompt Builder
↓
Local LLM Client
↓
Response
↓
Automatic Memory Extractor
↓
SQLite
```

Current module responsibilities:

```text
mind/cli.py              CLI parsing and command routing
mind/chat.py             Interactive chat loop and automatic memory extraction
mind/context.py          Memory/workspace context assembly
mind/prompt.py           System prompt and message construction
mind/llm.py              Ollama client calls
mind/memory.py           SQLite-backed persistent memory
mind/memory_extractor.py Model-output parsing for automatic memory extraction
mind/workspace.py        Safe workspace file listing and reading
mind/config.py           TOML config loading
```

## Testing

Run the test suite:

```bash
pytest
```

The tests currently cover:

- CLI command routing
- Context building
- Chat loop behavior
- Manual memory storage
- Memory deletion
- Memory formatting
- Automatic memory extraction parsing
- Workspace file listing
- Safe workspace file reading
- Prompt construction
- Config loading

## Development Roadmap

Planned development stages:

1. Basic CLI and local model interaction
2. Safe workspace file access
3. Centralized context construction
4. Persistent memory
5. Memory cleanup and deduplication
6. Improved workspace context support
7. Custom tool execution
8. Optional integrations for email, web search, project workflows, and automation
9. Optional retrieval-augmented generation over local files and memories

## Design Goals

Mind should be:

- Local-first
- Understandable
- Extensible
- Safe by default
- Useful from the command line
- Built around clear internal layers
- Capable of growing into a more powerful personal assistant without becoming a messy wrapper script

## Non-Goals for v0.1

Mind is not currently:

- A browser agent
- A full RAG system
- A multi-agent framework
- A cloud-first assistant
- A production security tool
- A general-purpose automation platform

Those may become future directions, but the current priority is building a clean, reliable local assistant foundation.
