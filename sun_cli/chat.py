"""Chat functionality for Sun CLI."""

import json
import uuid

import httpx
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from .config import get_config
from .models import Conversation, MessageRole
from .prompts import get_prompt_manager
from .mirror_manager import get_mirror_manager


class ChatSession:
    """A chat session with an AI model."""
    
    def __init__(self, console: Console) -> None:
        self.console = console
        self.config = get_config()
        self.conversation = Conversation(id=str(uuid.uuid4())[:8])
        self.prompt_manager = get_prompt_manager()
        
        # Detect location for language preference
        self._is_china_mainland = False
        try:
            mm = get_mirror_manager()
            self._is_china_mainland = mm.detect_location()
        except Exception:
            pass
        
        if not self.config.is_configured:
            raise RuntimeError(
                "API key not configured. Run `sun config` to set it up, "
                "or set SUN_API_KEY environment variable."
            )
        
        self.client = httpx.AsyncClient(
            base_url=self.config.base_url,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )
        
        # Initialize with system prompt
        self._initialize_system_prompt()
    
    def _initialize_system_prompt(self) -> None:
        """Load system prompt from prompt files."""
        system_prompt = self.prompt_manager.build_system_prompt(self._is_china_mainland)
        if system_prompt:
            self.conversation.add_message(MessageRole.SYSTEM, system_prompt)
    
    async def send_message(self, content: str) -> str:
        """Send a message and get the complete response."""
        # Add user message
        self.conversation.add_message(MessageRole.USER, content)
        
        # Call API
        response = await self.client.post(
            "/chat/completions",
            json={
                "model": self.config.model,
                "messages": self.conversation.to_openai_messages(),
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            },
        )
        response.raise_for_status()
        
        data = response.json()
        assistant_content = data["choices"][0]["message"]["content"] or ""
        self.conversation.add_message(MessageRole.ASSISTANT, assistant_content)
        
        return assistant_content
    
    async def stream_message(self, content: str) -> str:
        """Send a message and stream the response with live display."""
        # Add user message
        self.conversation.add_message(MessageRole.USER, content)
        
        # Call API with streaming
        try:
            async with self.client.stream(
                "POST",
                "/chat/completions",
                json={
                    "model": self.config.model,
                    "messages": self.conversation.to_openai_messages(),
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                
                full_content = ""
                
                with Live(Markdown(""), console=self.console, refresh_per_second=10) as live:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                                delta = chunk["choices"][0]["delta"].get("content", "")
                                if delta:
                                    full_content += delta
                                    live.update(Markdown(full_content))
                            except (json.JSONDecodeError, KeyError):
                                continue
            
            self.conversation.add_message(MessageRole.ASSISTANT, full_content)
            
            return full_content
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                self._show_api_error()
            raise
        except Exception as e:
            raise
    
    def _show_api_error(self) -> None:
        """Show API configuration error with recommendations."""
        from rich.table import Table
        
        error_panel = Panel(
            "[bold red]API Authentication Failed[/bold red]\n\n"
            "Your API key is invalid or not configured properly.\n\n"
            "[bold]Recommended AI Services for Chinese Users:[/bold]",
            title="[red]Configuration Error[/red]",
            border_style="red"
        )
        self.console.print(error_panel)
        
        # Create table with AI service recommendations
        table = Table(show_header=True, header_style="bold magenta", border_style="cyan")
        table.add_column("Service", style="cyan", width=20)
        table.add_column("Base URL", style="yellow", width=35)
        table.add_column("Model", style="green", width=20)
        
        table.add_row(
            "Kimi (Moonshot)",
            "https://api.moonshot.cn/v1",
            "moonshot-v1-128k"
        )
        table.add_row(
            "通义千问 (Qwen)",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "qwen-turbo"
        )
        table.add_row(
            "智谱 AI (GLM)",
            "https://open.bigmodel.cn/api/paas/v4",
            "glm-4"
        )
        table.add_row(
            "DeepSeek",
            "https://api.deepseek.com/v1",
            "deepseek-chat"
        )
        
        self.console.print(table)
        
        # Show configuration examples
        self.console.print("\n[bold]Configuration Examples:[/bold]")
        self.console.print("\n[cyan]Kimi API:[/cyan]")
        self.console.print("  suncli config --api-key sk-xxx --base-url https://api.moonshot.cn/v1 --model moonshot-v1-128k")
        
        self.console.print("\n[cyan]通义千问:[/cyan]")
        self.console.print("  suncli config --api-key sk-xxx --base-url https://dashscope.aliyuncs.com/compatible-mode/v1 --model qwen-turbo")
        
        self.console.print("\n[cyan]智谱 AI:[/cyan]")
        self.console.print("  suncli config --api-key sk-xxx --base-url https://open.bigmodel.cn/api/paas/v4 --model glm-4")
        
        self.console.print("\n[dim]Get your API key from the respective service's official website.[/dim]")
    
    def clear_history(self) -> None:
        """Clear conversation history but keep system prompt."""
        system_messages = [m for m in self.conversation.messages if m.role == MessageRole.SYSTEM]
        self.conversation.messages.clear()
        self.conversation.messages.extend(system_messages)
        self.console.print("[dim]Conversation history cleared. (System prompt preserved)[/dim]")
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
