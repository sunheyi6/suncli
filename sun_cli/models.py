"""Data models for Sun CLI."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageRole(str, Enum):
    """Message roles in conversation."""
    
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """A single message in the conversation."""
    
    role: MessageRole
    content: str
    
    def to_openai_format(self) -> dict[str, str]:
        """Convert to OpenAI API format."""
        return {"role": self.role.value, "content": self.content}


@dataclass 
class Conversation:
    """A conversation session."""
    
    id: str
    messages: list[Message] = field(default_factory=list)
    
    def add_message(self, role: MessageRole, content: str) -> None:
        """Add a message to the conversation."""
        self.messages.append(Message(role=role, content=content))
    
    def to_openai_messages(self) -> list[dict[str, str]]:
        """Convert all messages to OpenAI format."""
        return [msg.to_openai_format() for msg in self.messages]
