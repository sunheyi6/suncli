"""FastAPI web server for Sun CLI (Phase 5 - Vercel deployment).

Exposes Sun CLI's AI agent capabilities as HTTP endpoints,
allowing deployment to Vercel or any ASGI-compatible platform.
"""

import io
import json
import os
import uuid
from contextlib import redirect_stdout, redirect_stderr
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# We need to suppress rich console output in web mode
os.environ["TERM"] = "dumb"

from rich.console import Console

from ..chat import ChatSession
from ..skills.library import get_skill_library
from ..memory import get_memory_manager


app = FastAPI(
    title="Sun CLI Web API",
    description="Self-improving AI Agent API with Memory and Skill evolution",
    version="0.3.0"
)

# CORS for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ───────────────────── Request/Response Models ─────────────────────

class ChatRequest(BaseModel):
    """Chat request."""
    message: str = Field(..., description="User message")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context continuity")


class ChatResponse(BaseModel):
    """Chat response."""
    response: str
    conversation_id: str
    tool_calls_used: int = 0


class SkillInfo(BaseModel):
    """Skill information."""
    name: str
    description: str
    category: str
    version: str
    use_count: int
    success_rate: float
    last_used: Optional[str]
    archived: bool


class MemoryInfo(BaseModel):
    """Memory information."""
    name: str
    type: str
    description: str
    updated_at: str


# ───────────────────── Session Store ─────────────────────

# In-memory session store (use Redis for production)
_sessions: dict[str, ChatSession] = {}


def _get_or_create_session(conversation_id: str) -> ChatSession:
    """Get or create a chat session."""
    if conversation_id in _sessions:
        return _sessions[conversation_id]
    
    # Create a console that discards output
    string_io = io.StringIO()
    console = Console(file=string_io, force_terminal=False, color_system=None)
    
    session = ChatSession(console=console)
    _sessions[conversation_id] = session
    return session


# ───────────────────── API Endpoints ─────────────────────

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "0.3.0",
        "features": {
            "self_improving": True,
            "procedural_skills": True,
            "memory": True,
            "nudge_engine": True,
        }
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message and get AI response."""
    conversation_id = request.conversation_id or str(uuid.uuid4())[:8]
    
    try:
        session = _get_or_create_session(conversation_id)
        
        # Suppress all stdout/stderr during execution
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            response = await session.stream_message(request.message)
        
        # Count tool calls from conversation
        tool_calls = 0
        for msg in session.conversation.messages:
            if msg.role.value == "assistant" and msg.content:
                from ..tools.executor import ToolCallParser
                if ToolCallParser.has_tool_calls(msg.content):
                    tool_calls += len(ToolCallParser.parse(msg.content))
        
        return ChatResponse(
            response=response,
            conversation_id=conversation_id,
            tool_calls_used=tool_calls
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/skills")
async def list_skills():
    """List all available skills."""
    manager = get_skill_library()
    skills = manager.list_skills(include_archived=False)
    
    return {
        "skills": [
            SkillInfo(
                name=s.name,
                description=s.description,
                category=s.category,
                version=s.version,
                use_count=s.use_count,
                success_rate=s.success_rate,
                last_used=s.last_used,
                archived=s.archived
            ) for s in skills
        ],
        "stats": manager.get_stats()
    }


@app.get("/api/memories")
async def list_memories():
    """List all memories."""
    manager = get_memory_manager()
    memories = manager.list_memories()
    
    return {
        "memories": [
            MemoryInfo(
                name=m["name"],
                type=m["type"],
                description=m["description"],
                updated_at=m["updated_at"]
            ) for m in memories
        ]
    }


@app.get("/api/config")
async def get_config_info():
    """Get current configuration (sanitized)."""
    from ..config import get_config
    config = get_config()
    
    return {
        "model": config.model,
        "base_url": config.base_url,
        "self_improving_enabled": config.self_improving_enabled,
        "memory_nudge_interval": config.memory_nudge_interval,
        "skill_nudge_interval": config.skill_nudge_interval,
        "memory_char_limit": config.memory_char_limit,
        "user_char_limit": config.user_char_limit,
    }
