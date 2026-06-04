from pathlib import Path

import mind.core.context as context_builder
from mind.core.config import (
    AssistantConfig,
    Config,
    ContextConfig,
    EmbeddingConfig,
    MemoryConfig,
    ModelConfig,
    PathConfig,
    ToolConfig,
)

def make_test_config(tmp_path: Path) -> Config:
    """Build an isolated config for context tests."""
    return Config(
        assistant=AssistantConfig(
            name="Mind",
            description="Test assistant",
        ),
        paths=PathConfig(
            workspace=tmp_path / "workspace",
            database=tmp_path / "data" / "mind.db",
        ),
        model=ModelConfig(
            provider="ollama",
            base_url="http://localhost:11434",
            default="gemma4:e4b",
        ),
        memory=MemoryConfig(
            auto_extract=True,
            inject_context=True,
            max_relevant_memories=8,
        ),
        embeddings=EmbeddingConfig(
            provider="ollama",
            model="nomic-embed-text",
            enabled=True,
        ),
        context=ContextConfig(
            max_workspace_chars=12000,
        ),
        tools=ToolConfig(
            allow_external_read=True,
            allow_local_write=False,
            allow_external_write=False,
            allow_dangerous=False,
            require_confirmation=True,
        )
    )


def test_build_context_includes_most_recent_memories(monkeypatch, tmp_path: Path):
    """Memory context should include only the most recent configured number of memories."""
    base_config = make_test_config(tmp_path)

    test_config = Config(
        assistant=base_config.assistant,
        paths=base_config.paths,
        model=base_config.model,
        memory=MemoryConfig(
            auto_extract=True,
            inject_context=True,
            max_relevant_memories=2,
        ),
        embeddings=base_config.embeddings,
        context=base_config.context,
        tools=base_config.tools,
    )

    monkeypatch.setattr(
        context_builder,
        "list_memories",
        lambda config: [
            (1, "Old memory."),
            (2, "Recent memory one."),
            (3, "Recent memory two."),
        ],
    )

    context = context_builder.build_context(test_config)

    assert context.memory_context is not None
    assert "Old memory." not in context.memory_context
    assert "Recent memory one." in context.memory_context
    assert "Recent memory two." in context.memory_context


def test_build_context_uses_relevant_memories_when_query_is_available(
    monkeypatch,
    tmp_path: Path,
):
    """Memory context should prefer semantic retrieval for query-specific prompts."""
    test_config = make_test_config(tmp_path)

    list_called = False

    def fake_list_memories(config):
        nonlocal list_called
        list_called = True
        return [(1, "Recent fallback memory.")]

    monkeypatch.setattr(context_builder, "list_memories", fake_list_memories)
    monkeypatch.setattr(
        context_builder,
        "retrieve_relevant_memories",
        lambda config, query, limit: [(2, f"Relevant to {query} with limit {limit}.")],
    )

    context = context_builder.build_context(test_config, query="planning")

    assert context.memory_context is not None
    assert "Relevant to planning with limit 8." in context.memory_context
    assert "Recent fallback memory." not in context.memory_context
    assert list_called is False


def test_build_context_falls_back_to_recent_memories_when_retrieval_fails(
    monkeypatch,
    tmp_path: Path,
):
    """Memory context should still work if embedding retrieval is unavailable."""
    test_config = make_test_config(tmp_path)

    def broken_retrieve_relevant_memories(config, query, limit):
        raise RuntimeError("embedding model unavailable")

    monkeypatch.setattr(
        context_builder,
        "retrieve_relevant_memories",
        broken_retrieve_relevant_memories,
    )
    monkeypatch.setattr(
        context_builder,
        "list_memories",
        lambda config: [(1, "Recent fallback memory.")],
    )

    context = context_builder.build_context(test_config, query="planning")

    assert context.memory_context is not None
    assert "Recent fallback memory." in context.memory_context


def test_build_context_returns_no_memory_context_when_injection_disabled(
    monkeypatch,
    tmp_path: Path,
):
    """Memory context should be None when memory injection is disabled."""
    base_config = make_test_config(tmp_path)

    test_config = Config(
        assistant=base_config.assistant,
        paths=base_config.paths,
        model=base_config.model,
        memory=MemoryConfig(
            auto_extract=True,
            inject_context=False,
            max_relevant_memories=8,
        ),
        embeddings=base_config.embeddings,
        context=base_config.context,
        tools=base_config.tools,
    )

    called = False

    def fake_list_memories(config):
        nonlocal called
        called = True
        return [(1, "This should not be loaded.")]

    monkeypatch.setattr(context_builder, "list_memories", fake_list_memories)

    context = context_builder.build_context(test_config)

    assert context.memory_context is None
    assert called is False


def test_build_context_includes_workspace_context_when_file_paths_are_given(tmp_path: Path):
    """Workspace context should include formatted contents for each provided workspace file."""
    test_config = make_test_config(tmp_path)

    workspace = test_config.paths.workspace
    workspace.mkdir(parents=True)

    notes_file = workspace / "notes.txt"
    notes_file.write_text("These are workspace notes.", encoding="utf-8")

    plan_file = workspace / "plan.md"
    plan_file.write_text("# Project Plan\nBuild Mind.", encoding="utf-8")

    context = context_builder.build_context(
        test_config,
        [Path("notes.txt"), Path("plan.md")],
    )

    assert context.workspace_context is not None

    assert "FILE: notes.txt" in context.workspace_context
    assert "These are workspace notes." in context.workspace_context

    assert "FILE: plan.md" in context.workspace_context
    assert "# Project Plan\nBuild Mind." in context.workspace_context


def test_build_context_returns_no_workspace_context_when_no_file_paths_are_given(tmp_path: Path):
    """Workspace context should be None when no file path is provided."""
    test_config = make_test_config(tmp_path)

    context = context_builder.build_context(test_config)

    assert context.workspace_context is None


def test_build_workspace_context_truncates_when_context_is_too_large(tmp_path: Path):
    """Workspace context should be truncated when it exceeds the configured character limit."""
    base_config = make_test_config(tmp_path)

    test_config = Config(
        assistant=base_config.assistant,
        paths=base_config.paths,
        model=base_config.model,
        memory=base_config.memory,
        embeddings=base_config.embeddings,
        context=ContextConfig(
            max_workspace_chars=50,
        ),
        tools=base_config.tools,
    )

    workspace = test_config.paths.workspace
    workspace.mkdir(parents=True)

    notes_file = workspace / "notes.txt"
    notes_file.write_text("A" * 100, encoding="utf-8")

    context = context_builder.build_context(test_config, [Path("notes.txt")])

    assert context.workspace_context is not None
    assert len(context.workspace_context) <= test_config.context.max_workspace_chars
    assert "[Workspace context truncated]" in context.workspace_context


def test_build_memory_context_marks_semantic_memories_used(monkeypatch, tmp_path: Path):
    base_config = make_test_config(tmp_path)

    def fake_retrieve_relevant_memories(
        config: Config,
        query: str,
        limit: int
    ) -> list[tuple[int, str]]:
        return [(2, "Relevant memory.")]

    monkeypatch.setattr(
        context_builder,
        "retrieve_relevant_memories",
        fake_retrieve_relevant_memories,
    )

    assert 
