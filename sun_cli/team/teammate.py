"""Teammate - persistent agent with lifecycle (s15/s17)."""

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import httpx

from ..tools.executor import ToolCallParser, ToolExecutor


class TeammateStatus(Enum):
    """Teammate lifecycle status."""
    WORKING = "working"
    IDLE = "idle"
    SHUTDOWN = "shutdown"


@dataclass
class IdentityContext:
    """Identity block for context restoration."""
    name: str
    role: str
    team_name: str


class Teammate:
    """A persistent teammate with independent message history.
    
    Lifecycle: WORK -> IDLE -> WORK or SHUTDOWN
    In IDLE phase, polls inbox and task board for new work.
    """
    
    IDLE_TIMEOUT = 60  # Seconds before shutdown when idle
    POLL_INTERVAL = 5   # Seconds between idle polls
    
    def __init__(
        self,
        name: str,
        role: str,
        team_name: str,
        client: httpx.AsyncClient,
        config: Any,
        mailbox,
        task_board,
    ):
        """Initialize teammate.
        
        Args:
            name: Unique name
            role: Role (coder, tester, reviewer, etc.)
            team_name: Team identifier
            client: HTTP client for API calls
            config: Configuration
            mailbox: Mailbox for receiving messages
            task_board: Task board for auto-claim
        """
        self.name = name
        self.role = role
        self.team_name = team_name
        self.client = client
        self.config = config
        self.mailbox = mailbox
        self.task_board = task_board
        
        self.status = TeammateStatus.WORKING
        self.messages: list[dict] = []
        self.idle_time = 0
        
        # Initial system prompt
        self._init_messages()
    
    def _init_messages(self):
        """Initialize message history with identity."""
        self.messages = [
            {
                "role": "system",
                "content": f"""You are '{self.name}', a {self.role} on team '{self.team_name}'.

Your responsibilities:
1. Complete assigned tasks using available tools
2. Report progress and results clearly
3. When idle, wait for new assignments
4. Follow team protocols for approvals

You have access to tools: read, write, edit, bash.
Use them to accomplish your work."""
            }
        ]
    
    async def run(self, initial_prompt: str):
        """Main lifecycle loop.
        
        Args:
            initial_prompt: Initial task
        """
        # Start with initial work
        self.messages.append({"role": "user", "content": initial_prompt})
        
        while True:
            # WORK PHASE
            should_idle = await self._work_phase()
            if not should_idle:
                break
            
            # IDLE PHASE
            should_resume = await self._idle_phase()
            if not should_resume:
                self.status = TeammateStatus.SHUTDOWN
                break
            
            self.status = TeammateStatus.WORKING
        
        return f"{self.name} shutdown after {self.idle_time}s idle"
    
    async def _work_phase(self, max_iterations: int = 50) -> bool:
        """Execute work until done or need to idle.
        
        Returns:
            True if should transition to idle, False if should shutdown
        """
        for iteration in range(max_iterations):
            # Call LLM
            response = await self._call_llm()
            
            if not response:
                return False  # Error, shutdown
            
            # Check for tool calls
            tool_calls = ToolCallParser.parse(response)
            
            if not tool_calls:
                # Work complete
                self.messages.append({"role": "assistant", "content": response})
                return True  # Go to idle
            
            # Execute tools
            self.messages.append({"role": "assistant", "content": response})
            
            results = []
            for call in tool_calls:
                result = ToolExecutor.execute(call)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": result if isinstance(result, str) else str(result),
                })
            
            self.messages.append({"role": "user", "content": json.dumps(results)})
        
        # Max iterations
        return True
    
    async def _idle_phase(self) -> bool:
        """Poll for new work.
        
        Returns:
            True if should resume work, False if should shutdown
        """
        self.status = TeammateStatus.IDLE
        
        elapsed = 0
        while elapsed < self.IDLE_TIMEOUT:
            # 1. Check inbox first (explicit messages)
            inbox = self.mailbox.read_inbox(self.name)
            if inbox:
                self._ensure_identity()
                for msg in inbox:
                    self.messages.append({
                        "role": "user",
                        "content": f"<inbox from=\"{msg.get('from', 'unknown')}\">{msg.get('content', '')}</inbox>"
                    })
                return True
            
            # 2. Scan for auto-claimable tasks
            claimable = self.task_board.find_claimable(role=self.role)
            if claimable:
                task = claimable[0]
                success = self.task_board.claim_task(
                    task["id"], 
                    self.name, 
                    source="auto"
                )
                if success:
                    self._ensure_identity()
                    self.messages.append({
                        "role": "user",
                        "content": f"<auto-claimed>Task #{task['id']}: {task['subject']}</auto-claimed>"
                    })
                    return True
            
            # 3. Wait
            time.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL
        
        # Timeout - shutdown
        return False
    
    def _ensure_identity(self):
        """Re-inject identity if messages are short (after compression)."""
        if len(self.messages) <= 3:
            # Context was likely compressed, re-inject identity
            self.messages.insert(0, {
                "role": "user",
                "content": f"<identity>You are '{self.name}', role: {self.role}, team: {self.team_name}. Continue your work.</identity>"
            })
            self.messages.insert(1, {
                "role": "assistant",
                "content": f"I am {self.name}. Continuing."
            })
    
    async def _call_llm(self) -> Optional[str]:
        """Call LLM with current messages."""
        try:
            response = await self.client.post(
                "/chat/completions",
                json={
                    "model": self.config.model,
                    "messages": self.messages,
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"] or ""
        except Exception:
            return None
    
    def to_dict(self) -> dict:
        """Serialize teammate state."""
        return {
            "name": self.name,
            "role": self.role,
            "team_name": self.team_name,
            "status": self.status.value,
        }
