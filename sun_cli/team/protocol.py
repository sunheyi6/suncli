"""Protocol system for structured team coordination (s16)."""

import json
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class RequestStatus(Enum):
    """Protocol request status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class RequestKind(Enum):
    """Types of protocol requests."""
    SHUTDOWN = "shutdown"
    PLAN_APPROVAL = "plan_approval"
    TASK_CLAIM = "task_claim"


@dataclass
class RequestRecord:
    """Persistent record of a protocol request."""
    request_id: str
    kind: str
    from_agent: str
    to_agent: str
    status: str
    payload: dict
    created_at: float
    responded_at: Optional[float] = None
    response_payload: Optional[dict] = None
    
    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "kind": self.kind,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "status": self.status,
            "payload": self.payload,
            "created_at": self.created_at,
            "responded_at": self.responded_at,
            "response_payload": self.response_payload,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RequestRecord":
        return cls(
            request_id=data["request_id"],
            kind=data["kind"],
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            status=data["status"],
            payload=data.get("payload", {}),
            created_at=data["created_at"],
            responded_at=data.get("responded_at"),
            response_payload=data.get("response_payload"),
        )


@dataclass
class ProtocolEnvelope:
    """Structured protocol message.
    
    {
        "type": "shutdown_request",
        "from": "lead",
        "to": "alice",
        "request_id": "req_001",
        "payload": {},
        "timestamp": 1710000000.0,
    }
    """
    type: str
    from_agent: str
    to_agent: str
    request_id: str
    payload: dict
    timestamp: float
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "from": self.from_agent,
            "to": self.to_agent,
            "request_id": self.request_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ProtocolEnvelope":
        return cls(
            type=data["type"],
            from_agent=data["from"],
            to_agent=data["to"],
            request_id=data["request_id"],
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", time.time()),
        )


class ProtocolManager:
    """Manages structured protocol requests between agents.
    
    Requests are persisted to disk for recovery.
    """
    
    def __init__(self, team_dir: Path):
        """Initialize protocol manager.
        
        Args:
            team_dir: Team directory (.team/)
        """
        self.requests_dir = team_dir / "requests"
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        
        self._requests: dict[str, RequestRecord] = {}
        self._load_requests()
    
    def create_request(
        self,
        kind: str,
        from_agent: str,
        to_agent: str,
        payload: dict = None,
    ) -> str:
        """Create a new protocol request.
        
        Args:
            kind: Request type (shutdown, plan_approval, etc.)
            from_agent: Requester
            to_agent: Responder
            payload: Request data
            
        Returns:
            request_id
        """
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        
        record = RequestRecord(
            request_id=request_id,
            kind=kind,
            from_agent=from_agent,
            to_agent=to_agent,
            status=RequestStatus.PENDING.value,
            payload=payload or {},
            created_at=time.time(),
        )
        
        self._requests[request_id] = record
        self._save_request(record)
        
        return request_id
    
    def respond(
        self,
        request_id: str,
        approved: bool,
        response_payload: dict = None,
    ) -> bool:
        """Respond to a protocol request.
        
        Args:
            request_id: Request ID
            approved: Whether request is approved
            response_payload: Response data
            
        Returns:
            True if successful
        """
        if request_id not in self._requests:
            return False
        
        record = self._requests[request_id]
        record.status = RequestStatus.APPROVED.value if approved else RequestStatus.REJECTED.value
        record.responded_at = time.time()
        record.response_payload = response_payload or {}
        
        self._save_request(record)
        return True
    
    def get_request(self, request_id: str) -> Optional[RequestRecord]:
        """Get request record."""
        return self._requests.get(request_id)
    
    def get_pending_for(self, agent_name: str) -> list[RequestRecord]:
        """Get pending requests for an agent."""
        return [
            r for r in self._requests.values()
            if r.to_agent == agent_name and r.status == RequestStatus.PENDING.value
        ]
    
    def get_sent_by(self, agent_name: str) -> list[RequestRecord]:
        """Get requests sent by an agent."""
        return [
            r for r in self._requests.values()
            if r.from_agent == agent_name
        ]
    
    def build_protocol_message(
        self,
        request_id: str,
        approved: bool,
        feedback: str = "",
    ) -> ProtocolEnvelope:
        """Build response envelope.
        
        Args:
            request_id: Request being responded to
            approved: Approval status
            feedback: Response text
            
        Returns:
            Protocol envelope
        """
        record = self._requests.get(request_id)
        if not record:
            raise ValueError(f"Request not found: {request_id}")
        
        msg_type = f"{record.kind}_response"
        
        return ProtocolEnvelope(
            type=msg_type,
            from_agent=record.to_agent,
            to_agent=record.from_agent,
            request_id=request_id,
            payload={"approve": approved, "feedback": feedback},
            timestamp=time.time(),
        )
    
    def _save_request(self, record: RequestRecord):
        """Persist request to disk."""
        path = self.requests_dir / f"{record.request_id}.json"
        path.write_text(
            json.dumps(record.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def _load_requests(self):
        """Load existing requests."""
        for path in self.requests_dir.glob("req_*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                record = RequestRecord.from_dict(data)
                self._requests[record.request_id] = record
            except Exception:
                pass
