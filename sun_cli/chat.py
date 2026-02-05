"""Chat functionality for Sun CLI."""

import json
import uuid

import httpx
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

from .config import get_config
from .models import Conversation, MessageRole
from .prompts import get_prompt_manager


class ChatSession:
    """A chat session with an AI model."""
    
    def __init__(self, console: Console) -> None:
        self.console = console
        self.config = get_config()
        self.conversation = Conversation(id=str(uuid.uuid4())[:8])
        self.prompt_manager = get_prompt_manager()
        
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
        system_prompt = self.prompt_manager.build_system_prompt()
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
    
    def clear_history(self) -> None:
        """Clear conversation history but keep system prompt."""
        system_messages = [m for m in self.conversation.messages if m.role == MessageRole.SYSTEM]
        self.conversation.messages.clear()
        self.conversation.messages.extend(system_messages)
        self.console.print("[dim]Conversation history cleared. (System prompt preserved)[/dim]")
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
