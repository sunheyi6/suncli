"""Mailbox system for inter-agent messaging (s15)."""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class MessageEnvelope:
    """A wrapped message with metadata.
    
    envelope = {
        "type": "message",
        "from": "lead",
        "to": "alice",
        "content": "...",
        "timestamp": 1710000000.0,
    }
    """
    type: str
    from_agent: str
    to_agent: str
    content: str
    timestamp: float
    extra: dict = None
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "from": self.from_agent,
            "to": self.to_agent,
            "content": self.content,
            "timestamp": self.timestamp,
            **(self.extra or {})
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "MessageEnvelope":
        extra = {k: v for k, v in data.items() 
                if k not in ("type", "from", "to", "content", "timestamp")}
        return cls(
            type=data.get("type", "message"),
            from_agent=data.get("from", ""),
            to_agent=data.get("to", ""),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", time.time()),
            extra=extra,
        )


class Mailbox:
    """Simple JSONL-based mailbox for each teammate."""
    
    def __init__(self, team_dir: Path):
        """Initialize mailbox system.
        
        Args:
            team_dir: Team directory (.team/)
        """
        self.inbox_dir = team_dir / "inbox"
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
    
    def send(
        self, 
        from_agent: str, 
        to_agent: str, 
        content: str,
        msg_type: str = "message",
        extra: dict = None,
    ) -> str:
        """Send a message to an agent's inbox.
        
        Args:
            from_agent: Sender name
            to_agent: Recipient name
            content: Message content
            msg_type: Message type
            extra: Extra fields
            
        Returns:
            Message ID
        """
        envelope = MessageEnvelope(
            type=msg_type,
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            timestamp=time.time(),
            extra=extra,
        )
        
        inbox_path = self.inbox_dir / f"{to_agent}.jsonl"
        
        with open(inbox_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(envelope.to_dict(), ensure_ascii=False) + "\n")
        
        return f"{to_agent}_{int(time.time())}"
    
    def read_inbox(self, agent_name: str, clear: bool = True) -> list[dict]:
        """Read and optionally clear an agent's inbox.
        
        Args:
            agent_name: Agent name
            clear: Whether to clear inbox after reading
            
        Returns:
            List of messages
        """
        inbox_path = self.inbox_dir / f"{agent_name}.jsonl"
        
        if not inbox_path.exists():
            return []
        
        messages = []
        try:
            with open(inbox_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            msg = json.loads(line)
                            messages.append(msg)
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass
        
        if clear and messages:
            inbox_path.write_text("", encoding="utf-8")
        
        return messages
    
    def peek_inbox(self, agent_name: str) -> list[dict]:
        """Read without clearing."""
        return self.read_inbox(agent_name, clear=False)
    
    def has_messages(self, agent_name: str) -> bool:
        """Check if agent has pending messages."""
        inbox_path = self.inbox_dir / f"{agent_name}.jsonl"
        
        if not inbox_path.exists():
            return False
        
        content = inbox_path.read_text(encoding="utf-8").strip()
        return bool(content)
