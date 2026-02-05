"""Configuration management for Sun CLI."""

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseSettings, Field


def get_config_dir() -> Path:
    """Get the configuration directory."""
    if os.name == "nt":  # Windows
        config_dir = Path(os.environ.get("APPDATA", "~")) / "sun-cli"
    else:  # Unix-like
        config_dir = Path.home() / ".config" / "sun-cli"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_env_file_path() -> Path:
    """Get the path to the env file."""
    return get_config_dir() / ".env"


class Config(BaseSettings):
    """Sun CLI configuration."""
    
    class Config:
        env_prefix = "SUN_"
        env_file = str(get_env_file_path())
        env_file_encoding = "utf-8"
    
    # API Configuration
    api_key: str | None = Field(default=None, description="OpenAI API key")
    base_url: str = Field(default="https://api.openai.com/v1", description="API base URL")
    model: str = Field(default="gpt-4o-mini", description="Model to use")
    
    # Behavior
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    
    # UI
    theme: Literal["dark", "light", "system"] = Field(default="dark")
    
    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return self.api_key is not None


# Global config instance
_config: Config | None = None


def get_config(reload: bool = False) -> Config:
    """Get or create global config instance."""
    global _config
    if _config is None or reload:
        _config = Config()
    return _config


def reload_config() -> Config:
    """Reload configuration from disk."""
    return get_config(reload=True)
