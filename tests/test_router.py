from pathlib import Path

import mind.core.router as router
from mind.core.config import (
    AssistantConfig,
    Config,
    ContextConfig,
    MemoryConfig,
    ModelConfig,
    PathConfig,
    ToolConfig,
)


def make_test_config(tmp_path: Path) -> Config:
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
            cloud="gpt-oss:120b-cloud",
            uncensored="dolphin3:8b",
            small="qwen2.5:1.5b",
        ),
        memory=MemoryConfig(
            auto_memory=True,
            max_relevant_memories=8,
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


def test_resolve_model_returns_default_model(tmp_path: Path):
    config = make_test_config(tmp_path)

    assert router.resolve_model(config, "default") == "gemma4:e4b"


def test_resolve_model_returns_cloud_model(tmp_path: Path):
    config = make_test_config(tmp_path)

    assert router.resolve_model(config, "cloud") == "gpt-oss:120b-cloud"


def test_resolve_model_returns_uncensored_model(tmp_path: Path):
    config = make_test_config(tmp_path)

    assert router.resolve_model(config, "uncensored") == "dolphin3:8b"


def test_resolve_model_falls_back_to_default_for_unknown_label(tmp_path: Path):
    config = make_test_config(tmp_path)

    assert router.resolve_model(config, "nonsense") == "gemma4:e4b"


def test_route_parses_valid_router_output(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    monkeypatch.setattr(
        router,
        "complete_small",
        lambda config, messages: '{"model": "cloud"}',
    )

    assert router.route(config, "solve a hard proof") == "cloud"


def test_route_falls_back_to_default_for_invalid_json(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    monkeypatch.setattr(
        router,
        "complete_small",
        lambda config, messages: "not json",
    )

    assert router.route(config, "hello") == "default"


def test_route_falls_back_to_default_for_missing_model_key(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    monkeypatch.setattr(
        router,
        "complete_small",
        lambda config, messages: '{"route": "cloud"}',
    )

    assert router.route(config, "hello") == "default"


def test_route_falls_back_to_default_for_unknown_route_label(monkeypatch, tmp_path: Path):
    config = make_test_config(tmp_path)

    monkeypatch.setattr(
        router,
        "complete_small",
        lambda config, messages: '{"model": "banana"}',
    )

    assert router.route(config, "hello") == "default"


def test_route_falls_back_to_default_when_router_model_call_fails(
    monkeypatch,
    tmp_path: Path,
):
    config = make_test_config(tmp_path)

    def broken_complete_small(config, messages):
        raise RuntimeError("small model unavailable")

    monkeypatch.setattr(router, "complete_small", broken_complete_small)

    assert router.route(config, "hello") == "default"
