# Mind

Mind is a lightweight local-first personal AI assistant.

It is designed to run on your own machine, inspect files inside a controlled workspace, answer questions about its local environment, use persistent memory, and eventually support custom tools.

## Current Status

Mind is currently a v0.1 command-line prototype.

Implemented:

- `mind`
- `mind doctor`
- `mind ask <prompt>`
- `mind ask <prompt> --file <workspace-relative-path>`
- `mind files`
- Basic assistant identity prompt
- Workspace-relative file access
- Basic manual memory system + context injection
- Experimental automatic memory extraction during chat

## Requirements

- Python 3.11+
- Ollama running locally
- A configured local model available through Ollama

## Purpose

Mind is not meant to be a thin wrapper around an API. The goal is to build a local-first assistant architecture that stays understandable, extensible, and safe.

The project is being developed in stages:

1. Basic CLI and local model interaction
2. Safe workspace file access
3. Better context construction
4. Persistent memory
5. Custom tool execution
6. Optional integrations for email, web search, project workflows, and automation
