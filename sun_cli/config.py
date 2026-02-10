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


def update_config(**kwargs) -> Config:
    """Update configuration and save to env file."""
    config = get_config()
    env_file = get_env_file_path()
    
    # Read existing env file
    existing_content = ""
    if env_file.exists():
        existing_content = env_file.read_text(encoding="utf-8")
    
    # Parse existing lines
    lines = existing_content.split('\n')
    updated_lines = []
    
    # Map of env var names to config fields
    env_mapping = {
        'api_key': 'SUN_API_KEY',
        'base_url': 'SUN_BASE_URL',
        'model': 'SUN_MODEL',
        'temperature': 'SUN_TEMPERATURE',
        'max_tokens': 'SUN_MAX_TOKENS',
        'theme': 'SUN_THEME',
    }
    
    # Update values
    for key, value in kwargs.items():
        if key in env_mapping and value is not None:
            env_var = env_mapping[key]
            str_value = str(value)
            
            # Find and replace existing line
            found = False
            for i, line in enumerate(lines):
                if line.startswith(f'{env_var}='):
                    lines[i] = f'{env_var}={str_value}'
                    found = True
                    break
            
            # Add new line if not found
            if not found:
                lines.append(f'{env_var}={str_value}')
    
    # Write updated content
    env_file.write_text('\n'.join(lines) + '\n', encoding="utf-8")
    
    # Reload config
    return reload_config()

