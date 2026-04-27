# Architecture

Mind v0.1 starts as a small local CLI.

The planned architecture is:

```text
CLI
↓
Context Builder
↓
Memory + Workspace + System Info
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
