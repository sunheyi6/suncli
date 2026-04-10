"""Team system - multi-agent collaboration (s15-s17)."""

from .teammate import Teammate, TeammateStatus
from .mailbox import Mailbox, MessageEnvelope
from .protocol import ProtocolManager, ProtocolEnvelope, RequestRecord
from .manager import TeamManager, get_team_manager

__all__ = [
    "Teammate",
    "TeammateStatus", 
    "Mailbox",
    "MessageEnvelope",
    "ProtocolManager",
    "ProtocolEnvelope",
    "RequestRecord",
    "TeamManager",
    "get_team_manager",
]
