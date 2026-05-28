from __future__ import annotations

from ollama import Client

from mind.core.config import Config


class EmbeddingError(Exception):
    """Base error for embedding generation failures."""


class EmbeddingConfigError(EmbeddingError):
    """Raised when embedding config is missing or disabled."""


class EmbeddingInputError(EmbeddingError):
    """Raised when the input text is invalid."""


class EmbeddingProviderError(EmbeddingError):
    """Raised when the embedding provider call fails."""


class EmbeddingResponseError(EmbeddingError):
    """Raised when the provider response has an invalid shape."""


def embed_text(config: Config, text: str) -> list[float]:
    """Generate one embedding vector for a text string using the configured provider."""
    clean_text = text.strip()

    if not clean_text:
        raise EmbeddingInputError("Cannot embed empty text.")

    if not config.embeddings.enabled:
        raise EmbeddingConfigError("Embeddings are disabled in config.")

    if config.embeddings.provider != "ollama":
        raise EmbeddingConfigError(
            f"Unsupported embedding provider: {config.embeddings.provider!r}."
        )

    client = Client(host=config.model.base_url)

    try:
        response = client.embed(
            model=config.embeddings.model,
            input=clean_text,
        )
    except Exception as error:
        raise EmbeddingProviderError(
            f"Embedding provider call failed: {type(error).__name__}: {error}"
        ) from error

    embeddings = response.get("embeddings")

    if not isinstance(embeddings, list) or not embeddings:
        raise EmbeddingResponseError("Embedding response did not contain embeddings.")

    # Ollama returns a batch of embeddings even when we send one input string.
    embedding = embeddings[0]

    if not isinstance(embedding, list) or not embedding:
        raise EmbeddingResponseError("Embedding response contained an invalid vector.")

    if not all(isinstance(value, int | float) for value in embedding):
        raise EmbeddingResponseError("Embedding vector contained non-numeric values.")

    return [float(value) for value in embedding]
