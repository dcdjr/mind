"""Configuration loading for Mind.

The config file is Mind's source of truth for paths, model settings,
assistant identity, and memory behavior.
"""

from __future__ import annotations


import tomllib
from dataclasses import dataclass
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


@dataclass(frozen=True)
class MemoryConfig:
    auto_memory: bool
    max_relevant_memories: int


@dataclass(frozen=True)
class Config:
    assistant: AssistantConfig
    paths: PathConfig
    model: ModelConfig
    memory: MemoryConfig


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> Config:
    """Load Mind's configuration from a TOML file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with config_path.open("rb") as file:
        raw = tomllib.load(file)


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
        ),
        memory=MemoryConfig(
            auto_memory=raw["memory"]["auto_memory"],
            max_relevant_memories=raw["memory"]["max_relevant_memories"],
        ),
    )
