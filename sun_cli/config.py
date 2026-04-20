"""Configuration management for Sun CLI."""

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
import dotenv


def test_api_connection(config: "Config") -> tuple[bool, str]:
    """Test API connection and return (success, message).
    
    Returns:
        (True, success_message) if connection works.
        (False, error_message) if connection fails.
    """
    try:
        import httpx
    except ImportError:
        return True, "跳过 API 测试（httpx 未安装）"
    
    if not config.api_key:
        return False, "API Key 未设置，请先配置 API Key"
    
    try:
        with httpx.Client(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        ) as client:
            resp = client.post(
                "/chat/completions",
                json={
                    "model": config.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                },
            )
            if resp.status_code == 200:
                return True, "API 连接测试成功"
            elif resp.status_code == 401:
                return False, "API Key 无效或已过期，请检查 Key 是否正确"
            elif resp.status_code == 404:
                data = resp.json()
                err_msg = data.get("error", {}).get("message", "")
                if "model" in err_msg.lower() or "not found" in err_msg.lower():
                    return False, f"模型 '{config.model}' 不存在或无访问权限，请更换模型（例如 moonshot-v1-128k）"
                return False, f"请求地址错误 (404)，请检查 Base URL 是否正确: {config.base_url}"
            else:
                text = resp.text[:200]
                return False, f"API 请求失败 (HTTP {resp.status_code}): {text}"
    except httpx.ConnectError:
        return False, f"无法连接到 API 服务器，请检查网络或 Base URL 是否正确: {config.base_url}"
    except httpx.TimeoutException:
        return False, "连接 API 服务器超时，请检查网络或 Base URL 是否正确"
    except Exception as e:
        return False, f"测试连接时出错: {e}"


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
    # Check project directory first
    project_env = Path(".") / ".env"
    if project_env.exists():
        return project_env
    # Fallback to default config directory
    return get_config_dir() / ".env"


def get_api_config_file_path() -> Path:
    """Get the path to the API config file (stores API key, base URL, model)."""
    # Check project directory first
    project_api = Path(".") / ".api_config"
    if project_api.exists():
        return project_api
    # Fallback to default config directory
    return get_config_dir() / ".api_config"


class Config(BaseModel):
    """Sun CLI configuration."""

    api_key: str | None = Field(default=None, description="OpenAI API key")
    base_url: str = Field(default="https://api.openai.com/v1", description="API base URL")
    model: str = Field(default="gpt-4o-mini", description="Model to use")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    theme: Literal["dark", "light", "system"] = Field(default="dark")
    auto_confirm: bool = Field(default=False, description="Skip all confirmations and execute directly")
    auto_compact: bool = Field(default=True, description="Automatically compact long conversation history")
    compact_trigger_messages: int = Field(default=24, ge=10, description="Trigger compaction when message count exceeds this value")
    compact_keep_recent: int = Field(default=10, ge=4, description="How many recent messages to keep uncompressed")
    show_tool_traces: bool = Field(default=False, description="Show tool execution trace panels in chat")

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables.
        
        API-related configs (key, base_url, model) are loaded from .api_config
        which overrides .env for those settings.
        """
        # Load general config first
        env_file = get_env_file_path()
        if env_file.exists():
            dotenv.load_dotenv(env_file, override=True)
        
        # Load API config (overrides .env for API-related settings)
        api_config_file = get_api_config_file_path()
        if api_config_file.exists():
            dotenv.load_dotenv(api_config_file, override=True)

        return cls(
            api_key=os.getenv("SUN_API_KEY"),
            base_url=os.getenv("SUN_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("SUN_MODEL", "gpt-4o-mini"),
            temperature=float(os.getenv("SUN_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("SUN_MAX_TOKENS")) if os.getenv("SUN_MAX_TOKENS") else None,
            theme=os.getenv("SUN_THEME", "dark"),
            auto_confirm=os.getenv("SUN_AUTO_CONFIRM", "").lower() in ("true", "1", "yes"),
            auto_compact=os.getenv("SUN_AUTO_COMPACT", "true").lower() in ("true", "1", "yes"),
            compact_trigger_messages=int(os.getenv("SUN_COMPACT_TRIGGER_MESSAGES", "24")),
            compact_keep_recent=int(os.getenv("SUN_KEEP_RECENT", "10")),
            show_tool_traces=os.getenv("SUN_SHOW_TOOL_TRACES", "").lower() in ("true", "1", "yes"),
        )
    
    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return self.api_key is not None
    
    @property
    def yolo_mode(self) -> bool:
        """Check if auto-confirm (yolo) mode is enabled."""
        return self.auto_confirm


# Global config instance
_config: Config | None = None


def get_config(reload: bool = False) -> Config:
    """Get or create global config instance."""
    global _config
    if _config is None or reload:
        _config = Config.from_env()
    return _config


def reload_config() -> Config:
    """Reload configuration from disk."""
    return get_config(reload=True)


def _update_env_file(file_path: Path, updates: dict[str, str]) -> None:
    """Helper to update key=value lines in an env-style file."""
    existing_content = ""
    if file_path.exists():
        existing_content = file_path.read_text(encoding="utf-8")
    
    lines = existing_content.split("\n")
    
    for env_var, str_value in updates.items():
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{env_var}="):
                lines[i] = f"{env_var}={str_value}"
                found = True
                break
        if not found:
            lines.append(f"{env_var}={str_value}")
    
    # Filter out empty lines at end to keep clean
    while lines and lines[-1].strip() == "":
        lines.pop()
    
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_config(**kwargs) -> Config:
    """Update configuration and save to the appropriate file.
    
    API-related configs (api_key, base_url, model) go to .api_config.
    All other configs go to .env.
    """
    # API-related field mapping
    api_mapping = {
        "api_key": "SUN_API_KEY",
        "base_url": "SUN_BASE_URL",
        "model": "SUN_MODEL",
    }
    
    # General config field mapping
    env_mapping = {
        "temperature": "SUN_TEMPERATURE",
        "max_tokens": "SUN_MAX_TOKENS",
        "theme": "SUN_THEME",
        "auto_confirm": "SUN_AUTO_CONFIRM",
        "auto_compact": "SUN_AUTO_COMPACT",
        "compact_trigger_messages": "SUN_COMPACT_TRIGGER_MESSAGES",
        "compact_keep_recent": "SUN_KEEP_RECENT",
        "show_tool_traces": "SUN_SHOW_TOOL_TRACES",
    }
    
    # Update API config file
    api_updates = {
        api_mapping[k]: str(v)
        for k, v in kwargs.items()
        if k in api_mapping and v is not None
    }
    if api_updates:
        api_file = get_api_config_file_path()
        _update_env_file(api_file, api_updates)
    
    # Update general env file
    env_updates = {
        env_mapping[k]: str(v)
        for k, v in kwargs.items()
        if k in env_mapping and v is not None
    }
    if env_updates:
        env_file = get_env_file_path()
        _update_env_file(env_file, env_updates)
    
    # Cleanup: remove migrated API keys from .env (if they exist there from old versions)
    if api_updates:
        env_file = get_env_file_path()
        if env_file.exists():
            content = env_file.read_text(encoding="utf-8")
            lines = content.split("\n")
            cleaned = [
                line for line in lines
                if not any(line.startswith(f"{var}=") for var in api_mapping.values())
            ]
            while cleaned and cleaned[-1].strip() == "":
                cleaned.pop()
            env_file.write_text("\n".join(cleaned) + "\n", encoding="utf-8")
    
    return reload_config()
