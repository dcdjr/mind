from pathlib import Path

import pytest

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
from mind.core.embeddings import (
    EmbeddingConfigError,
    EmbeddingInputError,
    EmbeddingProviderError,
    EmbeddingResponseError,
    embed_text,
)


class FakeOllamaClient:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = {"embeddings": [[1, 2.5, 3]]} if response is None else response
        self.error = error
        self.calls = []

    def embed(self, **kwargs):
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return self.response


def make_test_config(tmp_path: Path, embeddings: EmbeddingConfig | None = None) -> Config:
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
        embeddings=embeddings
        or EmbeddingConfig(
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
        ),
    )


def test_embed_text_calls_ollama_with_configured_model_and_trimmed_input(
    monkeypatch,
    tmp_path: Path,
):
    config = make_test_config(tmp_path)
    fake_client = FakeOllamaClient(response={"embeddings": [[1, 2.5, 3]]})
    created_hosts = []

    def fake_client_factory(host: str):
        created_hosts.append(host)
        return fake_client

    monkeypatch.setattr("mind.core.embeddings.Client", fake_client_factory)

    embedding = embed_text(config, "  hello semantic memory  ")

    assert created_hosts == ["http://localhost:11434"]
    assert fake_client.calls == [
        {
            "model": "nomic-embed-text",
            "input": "hello semantic memory",
        }
    ]
    assert embedding == [1.0, 2.5, 3.0]


def test_embed_text_rejects_empty_text_before_calling_provider(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)
    called = False

    def fake_client_factory(host: str):
        nonlocal called
        called = True
        return FakeOllamaClient()

    monkeypatch.setattr("mind.core.embeddings.Client", fake_client_factory)

    with pytest.raises(EmbeddingInputError, match="Cannot embed empty text"):
        embed_text(config, "   ")

    assert called is False


def test_embed_text_rejects_disabled_embeddings_before_calling_provider(
    monkeypatch,
    tmp_path: Path,
):
    config = make_test_config(
        tmp_path,
        embeddings=EmbeddingConfig(
            provider="ollama",
            model="nomic-embed-text",
            enabled=False,
        ),
    )
    called = False

    def fake_client_factory(host: str):
        nonlocal called
        called = True
        return FakeOllamaClient()

    monkeypatch.setattr("mind.core.embeddings.Client", fake_client_factory)

    with pytest.raises(EmbeddingConfigError, match="Embeddings are disabled"):
        embed_text(config, "hello")

    assert called is False


def test_embed_text_rejects_unsupported_provider_before_calling_provider(
    monkeypatch,
    tmp_path: Path,
):
    config = make_test_config(
        tmp_path,
        embeddings=EmbeddingConfig(
            provider="other",
            model="nomic-embed-text",
            enabled=True,
        ),
    )
    called = False

    def fake_client_factory(host: str):
        nonlocal called
        called = True
        return FakeOllamaClient()

    monkeypatch.setattr("mind.core.embeddings.Client", fake_client_factory)

    with pytest.raises(EmbeddingConfigError, match="Unsupported embedding provider"):
        embed_text(config, "hello")

    assert called is False


def test_embed_text_wraps_provider_errors(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)
    fake_client = FakeOllamaClient(error=RuntimeError("ollama unavailable"))

    monkeypatch.setattr("mind.core.embeddings.Client", lambda host: fake_client)

    with pytest.raises(EmbeddingProviderError, match="ollama unavailable"):
        embed_text(config, "hello")


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"embeddings": []},
        {"embeddings": "not a list"},
        {"embeddings": [[]]},
        {"embeddings": ["not a vector"]},
        {"embeddings": [[1, "bad"]]},
    ],
)
def test_embed_text_rejects_invalid_provider_responses(
    monkeypatch,
    tmp_path: Path,
    response,
):
    config = make_test_config(tmp_path)
    fake_client = FakeOllamaClient(response=response)

    monkeypatch.setattr("mind.core.embeddings.Client", lambda host: fake_client)

    with pytest.raises(EmbeddingResponseError):
        embed_text(config, "hello")
