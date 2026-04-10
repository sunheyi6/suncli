"""Team manager - coordinates teammates and team state (s15-s17)."""

import json
from pathlib import Path
from typing import Optional

import httpx

from .teammate import Teammate, TeammateStatus
from .mailbox import Mailbox
from .protocol import ProtocolManager


class TeamManager:
    """Manages the team of persistent agents.
    
    Directory structure:
    .team/
    ├── config.json       # Team roster
    ├── inbox/            # Mailboxes
    │   ├── alice.jsonl
    │   └── bob.jsonl
    └── requests/         # Protocol records
        ├── req_001.json
        └── req_002.json
    """
    
    def __init__(self, root: Path = None, client: httpx.AsyncClient = None, config=None):
        """Initialize team manager.
        
        Args:
            root: Project root
            client: HTTP client for LLM calls
            config: Configuration
        """
        if root is None:
            root = Path.cwd()
        self.root = Path(root).resolve()
        self.team_dir = self.root / ".team"
        self.team_dir.mkdir(parents=True, exist_ok=True)
        
        self.client = client
        self.config = config
        
        # Sub-systems
        self.mailbox = Mailbox(self.team_dir)
        self.protocol = ProtocolManager(self.team_dir)
        
        # Active teammates
        self._teammates: dict[str, Teammate] = {}
        
        # Load config
        self._config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load team configuration."""
        config_path = self.team_dir / "config.json"
        if config_path.exists():
            return json.loads(config_path.read_text(encoding="utf-8"))
        return {"team_name": "default", "members": []}
    
    def _save_config(self):
        """Save team configuration."""
        config_path = self.team_dir / "config.json"
        config_path.write_text(
            json.dumps(self._config, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def spawn(
        self,
        name: str,
        role: str,
        prompt: str,
        task_board=None,
    ) -> Teammate:
        """Spawn a new teammate.
        
        Args:
            name: Teammate name
            role: Role (coder, tester, etc.)
            prompt: Initial task/instructions
            task_board: Task board for auto-claim
            
        Returns:
            Teammate instance
        """
        # Add to roster
        member_entry = {
            "name": name,
            "role": role,
            "status": "working",
        }
        
        # Update or add
        existing = [m for m in self._config["members"] if m["name"] == name]
        if existing:
            existing[0].update(member_entry)
        else:
            self._config["members"].append(member_entry)
        
        self._save_config()
        
        # Create teammate
        from ..task.manager import TaskManager  # Avoid circular import
        
        teammate = Teammate(
            name=name,
            role=role,
            team_name=self._config["team_name"],
            client=self.client,
            config=self.config,
            mailbox=self.mailbox,
            task_board=task_board or TaskManager(),
        )
        
        self._teammates[name] = teammate
        return teammate
    
    def get_teammate(self, name: str) -> Optional[Teammate]:
        """Get active teammate by name."""
        return self._teammates.get(name)
    
    def list_members(self) -> list[dict]:
        """List all team members from config."""
        return self._config["members"]
    
    def send_message(
        self,
        from_agent: str,
        to_agent: str,
        content: str,
    ) -> str:
        """Send message to a teammate.
        
        Args:
            from_agent: Sender
            to_agent: Recipient
            content: Message
            
        Returns:
            Message ID
        """
        return self.mailbox.send(from_agent, to_agent, content)
    
    def request_shutdown(
        self,
        target: str,
        from_agent: str = "lead",
    ) -> str:
        """Request graceful shutdown of a teammate.
        
        Args:
            target: Teammate to shutdown
            from_agent: Requester
            
        Returns:
            request_id
        """
        request_id = self.protocol.create_request(
            kind="shutdown",
            from_agent=from_agent,
            to_agent=target,
        )
        
        # Send protocol message
        envelope = self.protocol.build_protocol_message(request_id, approved=False)
        self.mailbox.send(
            from_agent=from_agent,
            to_agent=target,
            content=f"Shutdown request: {request_id}",
            msg_type="shutdown_request",
            extra={"request_id": request_id},
        )
        
        return request_id
    
    def approve_plan(
        self,
        request_id: str,
        approved: bool = True,
        feedback: str = "",
    ) -> bool:
        """Approve or reject a plan approval request.
        
        Args:
            request_id: Request ID
            approved: Whether to approve
            feedback: Response text
            
        Returns:
            True if successful
        """
        success = self.protocol.respond(request_id, approved, {"feedback": feedback})
        
        if success:
            # Send response message
            envelope = self.protocol.build_protocol_message(request_id, approved, feedback)
            record = self.protocol.get_request(request_id)
            
            self.mailbox.send(
                from_agent=record.to_agent,
                to_agent=record.from_agent,
                content=feedback or ("Approved" if approved else "Rejected"),
                msg_type=envelope.type,
                extra={"request_id": request_id, "approve": approved},
            )
        
        return success
    
    def get_status(self) -> dict:
        """Get team status summary."""
        return {
            "team_name": self._config["team_name"],
            "member_count": len(self._config["members"]),
            "active_teammates": len(self._teammates),
            "pending_requests": len([
                r for r in self.protocol._requests.values()
                if r.status == "pending"
            ]),
        }


# Global instance
_team_manager: Optional[TeamManager] = None


def get_team_manager(client: httpx.AsyncClient = None, config=None) -> TeamManager:
    """Get or create global team manager."""
    global _team_manager
    if _team_manager is None:
        _team_manager = TeamManager(client=client, config=config)
    return _team_manager
