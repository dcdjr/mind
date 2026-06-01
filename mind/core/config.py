"""Configuration loading for Mind.

The config file is Mind's source of truth for paths, project settings, model
settings, assistant identity, memory behavior, and tool permissions.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_CONFIG_PATH = Path("configs/config.toml")


@dataclass(frozen=True)
class AssistantConfig:
    name: str
    description: str


@dataclass(frozen=True)
class PathConfig:
    workspace: Path
    database: Path


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    base_url: str
    default: str
    cloud: str = ""
    uncensored: str = ""
    small: str = ""


@dataclass(frozen=True)
class MemoryConfig:
    auto_extract: bool
    inject_context: bool
    max_relevant_memories: int


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str
    model: str
    enabled: bool


@dataclass(frozen=True)
class ContextConfig:
    max_workspace_chars: int


@dataclass(frozen=True)
class ToolConfig:
    allow_external_read: bool
    allow_local_write: bool
    allow_external_write: bool
    allow_dangerous: bool
    require_confirmation: bool


@dataclass(frozen=True)
class ProjectConfig:
    root: Path


@dataclass(frozen=True)
class Config:
    assistant: AssistantConfig
    paths: PathConfig
    model: ModelConfig
    memory: MemoryConfig
    embeddings: EmbeddingConfig
    context: ContextConfig
    tools: ToolConfig
    project: ProjectConfig = field(
        default_factory=lambda: ProjectConfig(root=Path("."))
    )


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> Config:
    """Load Mind's configuration from a TOML file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("rb") as file:
        raw = tomllib.load(file)

    project_config = raw.get("project", {})

    return Config(
        assistant=AssistantConfig(
            name=raw["assistant"]["name"],
            description=raw["assistant"]["description"],
        ),
        paths=PathConfig(
            workspace=Path(raw["paths"]["workspace"]),
            database=Path(raw["paths"]["database"]),
        ),
        model=ModelConfig(
            provider=raw["model"]["provider"],
            base_url=raw["model"]["base_url"],
            default=raw["model"]["default"],
            cloud=raw["model"].get("cloud", ""),
            uncensored=raw["model"].get("uncensored", ""),
            small=raw["model"].get("small", ""),
        ),
        memory=MemoryConfig(
            auto_extract=raw["memory"].get(
                "auto_extract",
                raw["memory"].get("auto_memory", True),
            ),
            inject_context=raw["memory"].get("inject_context", True),
            max_relevant_memories=raw["memory"]["max_relevant_memories"],
        ),
        embeddings=EmbeddingConfig(
            provider=raw["embeddings"]["provider"],
            model=raw["embeddings"]["model"],
            enabled=raw["embeddings"]["enabled"],
        ),
        context=ContextConfig(
            max_workspace_chars=raw["context"]["max_workspace_chars"],
        ),
        tools=ToolConfig(
            allow_external_read=raw["tools"]["allow_external_read"],
            allow_local_write=raw["tools"]["allow_local_write"],
            allow_external_write=raw["tools"]["allow_external_write"],
            allow_dangerous=raw["tools"]["allow_dangerous"],
            require_confirmation=raw["tools"]["require_confirmation"],
        ),
        project=ProjectConfig(
            root=Path(project_config.get("root", ".")),
        ),
    )
