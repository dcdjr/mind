from pathlib import Path

from mind.core.config import load_config


def test_load_config_reads_basic_settings():
    """Config loading should turn TOML settings into typed Python objects."""
    config = load_config(Path("configs/config.toml"))

    assert config.assistant.name == "Mind"
    assert config.paths.workspace == Path("workspace")
    assert config.paths.database == Path("data/mind.db")
    assert config.project.root == Path(".")
    assert config.model.provider == "ollama"
    assert config.model.default == "gemma4:e2b"
    assert config.memory.auto_extract is True
    assert config.memory.inject_context is True
    assert config.memory.min_similarity == 0.3
    assert config.embeddings.provider == "ollama"
    assert config.embeddings.model == "nomic-embed-text"
    assert config.embeddings.enabled is True
    assert config.context.max_workspace_chars == 12000
    assert config.tools.allow_external_read is True
    assert config.tools.allow_local_write is True
    assert config.tools.allow_external_write is False
    assert config.tools.allow_dangerous is False
    assert config.tools.require_confirmation is True
    assert config.model.cloud == "gpt-oss:120b-cloud"
    assert config.model.uncensored == "oroboroslabs/qwen3.5-abliterated-47-4:latest"
    assert config.model.small == "qwen2.5:1.5b"
