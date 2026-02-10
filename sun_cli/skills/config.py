"""Config management skill for Sun CLI."""

from typing import Optional
from ..skills import Skill, SkillContext
from ..config import get_config, get_config_dir
from rich.panel import Panel


class ConfigSkill(Skill):
    """Config management skill."""
    
    @property
    def name(self) -> str:
        return "config"
    
    @property
    def description(self) -> str:
        return "Manage Sun CLI configuration (API key, base URL, model, etc.)"
    
    @property
    def trigger_keywords(self) -> list[str]:
        return [
            "配置", "设置", "config", "设置 api", "设置模型",
            "修改配置", "查看配置", "show config"
        ]
    
    @property
    def system_prompt(self) -> Optional[str]:
        return """## Configuration Management

Users can configure Sun CLI with:
- API Key: Authentication for AI services
- Base URL: API endpoint (e.g., https://api.moonshot.cn/v1 for Kimi)
- Model: AI model to use (e.g., moonshot-v1-128k, gpt-4o-mini)
- Temperature: Sampling temperature (0.0-2.0)

Recommended AI services for Chinese users:
- Kimi (Moonshot): https://api.moonshot.cn/v1
- 通义千问: https://dashscope.aliyuncs.com/compatible-mode/v1
- 智谱 AI (GLM): https://open.bigmodel.cn/api/paas/v4
- DeepSeek: https://api.deepseek.com/v1
"""
    
    def initialize(self, context: SkillContext) -> None:
        super().initialize(context)
        self.config = get_config()
    
    async def handle(self, user_input: str) -> bool:
        lower_input = user_input.lower()
        
        if "查看配置" in lower_input or "show config" in lower_input or "/config" in lower_input:
            self._show_config()
            return True
        
        if "配置" in lower_input or "设置" in lower_input or "config" in lower_input:
            self._show_config_help()
            return True
        
        return False
    
    def _show_config(self):
        self.context.console.print(Panel.fit(
            f"[bold]Current Configuration[/bold]\n\n"
            f"API Key: {'[green][OK] Set[/green]' if self.config.is_configured else '[red][X] Not set[/red]'}\n"
            f"Base URL: [cyan]{self.config.base_url}[/cyan]\n"
            f"Model: [cyan]{self.config.model}[/cyan]\n"
            f"Temperature: [cyan]{self.config.temperature}[/cyan]",
            title="Config"
        ))
    
    def _show_config_help(self):
        self.context.console.print(Panel(
            """[bold]Configuration Commands:[/bold]

Use CLI commands to manage config:
  [cyan]suncli config --api-key <key>[/cyan]    - Set API key
  [cyan]suncli config --base-url <url>[/cyan]    - Set API base URL
  [cyan]suncli config --model <model>[/cyan]      - Set model
  [cyan]suncli config --show[/cyan]              - Show current config

[bold]Recommended AI Services:[/bold]

  [cyan]Kimi API (Moonshot):[/cyan]
    suncli config --api-key sk-xxx --base-url https://api.moonshot.cn/v1 --model moonshot-v1-128k

  [cyan]通义千问:[/cyan]
    suncli config --api-key sk-xxx --base-url https://dashscope.aliyuncs.com/compatible-mode/v1 --model qwen-turbo

  [cyan]智谱 AI:[/cyan]
    suncli config --api-key sk-xxx --base-url https://open.bigmodel.cn/api/paas/v4 --model glm-4

  [cyan]DeepSeek:[/cyan]
    suncli config --api-key sk-xxx --base-url https://api.deepseek.com/v1 --model deepseek-chat

  [cyan]OpenAI:[/cyan]
    suncli config --api-key sk-xxx --base-url https://api.openai.com/v1 --model gpt-4o-mini""",
            title="Configuration Help",
            border_style="yellow"
        ))
