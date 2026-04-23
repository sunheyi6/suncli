"""Review Agent - silently analyzes conversation to extract learnings (Phase 2)."""

import json
import os
from typing import Any, Optional

import httpx


class ReviewAgent:
    """A lightweight agent that reviews conversation snapshots and extracts memories/skills.
    
    This runs silently in the background (no user interaction).
    It shares the same MemoryManager and SkillManagerV2 as the main agent.
    """
    
    def __init__(self, client: httpx.AsyncClient, config: Any):
        """Initialize review agent.
        
        Args:
            client: HTTP client for API calls (shared with main agent)
            config: Configuration with model, base_url, etc.
        """
        self.client = client
        self.config = config
    
    async def review_memory(
        self,
        messages_snapshot: list[dict],
        current_memories: str = ""
    ) -> Optional[dict]:
        """Review conversation for durable facts worth saving to memory.
        
        Returns:
            dict with action details if something should be saved, None otherwise.
        """
        prompt = self._build_memory_review_prompt(messages_snapshot, current_memories)
        
        response = await self._call_llm(prompt)
        if not response:
            return None
        
        # Parse the response
        return self._parse_review_response(response, "memory")
    
    async def review_skills(
        self,
        messages_snapshot: list[dict],
        current_skills_index: str = ""
    ) -> Optional[dict]:
        """Review conversation for procedural knowledge worth saving as a skill.
        
        Returns:
            dict with action details if a skill should be created/patched, None otherwise.
        """
        prompt = self._build_skill_review_prompt(messages_snapshot, current_skills_index)
        
        response = await self._call_llm(prompt)
        if not response:
            return None
        
        return self._parse_review_response(response, "skill")
    
    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Call LLM with the review prompt."""
        try:
            response = await self.client.post(
                "/chat/completions",
                json={
                    "model": self.config.model,
                    "messages": [
                        {"role": "system", "content": "You are a review agent. Analyze conversations and decide what learnings to save. Be conservative — if nothing is worth saving, say so."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1500,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"].get("content", "")
        except Exception:
            return None
    
    def _build_memory_review_prompt(
        self,
        messages: list[dict],
        current_memories: str
    ) -> str:
        """Build prompt for memory review."""
        # Filter to recent user/assistant exchanges
        recent = []
        for msg in messages[-20:]:  # Last 20 messages
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                recent.append(f"{role.upper()}: {content[:800]}")
        
        conversation_text = "\n\n".join(recent)
        
        return f"""Review this conversation and decide if there are durable facts worth saving to memory.

Current memories:
{current_memories or "(none)"}

Conversation:
{conversation_text}

Memory Guidelines:
- Save durable facts: user preferences, environment details, tool quirks, stable conventions
- Prioritize what reduces future user steering
- Write memories as declarative facts, not instructions
- GOOD: "User prefers concise responses" | "Project uses pytest with xdist"
- BAD: "Always respond concisely" | "Run tests with pytest -n 4"
- If nothing is worth saving, just say "Nothing to save." and stop

If you find something worth saving, respond in this exact format:
ACTION: save_memory
name: <short_name>
type: <user|feedback|project|reference>
description: <one_line_description>
content: <the_fact_to_remember>
"""
    
    def _build_skill_review_prompt(
        self,
        messages: list[dict],
        current_skills: str
    ) -> str:
        """Build prompt for skill review."""
        recent = []
        for msg in messages[-30:]:  # Last 30 messages (skills need more context)
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                recent.append(f"{role.upper()}: {content[:800]}")
        
        conversation_text = "\n\n".join(recent)
        
        return f"""Review this conversation and decide if there's procedural knowledge worth saving as a skill.

Current skills:
{current_skills or "(none)"}

Conversation:
{conversation_text}

Skill Guidelines:
- Create when: complex task succeeded (5+ tool calls), errors overcome, user-corrected approach worked
- A skill should have: When to use, Steps, Pitfalls
- If the user corrected your approach, that's valuable — save it
- If you discovered a new pitfall during execution, patch the existing skill
- If nothing is worth saving, just say "Nothing to save." and stop

If you find something worth saving, respond in this exact format:

For CREATE:
ACTION: create_skill
name: <skill_name>
category: <devops|software-development|testing|data-analysis|general>
description: <one_line_description>
content: |
  ## When to use
  - <trigger condition>
  
  ## Steps
  1. <step>
  2. <step>
  
  ## Pitfalls
  - <pitfall and how to avoid>

For PATCH:
ACTION: patch_skill
name: <existing_skill_name>
old_string: <exact text to find>
new_string: <replacement text>
"""
    
    def _parse_review_response(self, text: str, review_type: str) -> Optional[dict]:
        """Parse review agent response into structured action."""
        if not text:
            return None
        
        text_lower = text.lower().strip()
        if "nothing to save" in text_lower:
            return None
        
        lines = text.split("\n")
        result: dict[str, Any] = {"type": review_type, "action": None}
        
        current_key = None
        current_value_lines = []
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            # Detect ACTION line
            if stripped.upper().startswith("ACTION:"):
                action_text = stripped.split(":", 1)[1].strip().lower()
                result["action"] = action_text
                continue
            
            # Key: value pattern
            if ":" in stripped and not stripped.startswith("-") and not stripped.startswith("|"):
                # Save previous key
                if current_key:
                    result[current_key] = "\n".join(current_value_lines).strip()
                    current_value_lines = []
                
                key, value = stripped.split(":", 1)
                current_key = key.strip().lower().replace(" ", "_")
                current_value_lines.append(value.strip())
            elif current_key:
                current_value_lines.append(line)
        
        # Save last key
        if current_key:
            result[current_key] = "\n".join(current_value_lines).strip()
        
        if not result.get("action"):
            return None
        
        return result
