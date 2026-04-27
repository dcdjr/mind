from pathlib import Path

from mind.config import load_config

def test_load_config_reads_basic_settings():
    """Config loading should turn TOML settings into typed Python objects."""
    config = load_config(Path("configs/config.toml"))

    assert config.assistant.name == "Mind"
    assert config.paths.workspace == Path("workspace")
    assert config.model.provider == "ollama"
    assert config.model.default == "gemma4:e2b"
    assert config.memory.auto_memory is True
