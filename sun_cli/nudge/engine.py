"""Nudge Engine - triggers periodic self-review for Memory and Skills (Phase 2)."""

import asyncio
from typing import Any, Optional

from ..memory import get_memory_manager
from ..skills.library import get_skill_library
from .review_agent import ReviewAgent


class NudgeEngine:
    """Maintains counters and triggers background review when thresholds are reached.
    
    Two independent counters:
    - Memory nudge: per user turn (captures user preferences, corrections)
    - Skill nudge: per tool iteration (captures procedural learnings from execution)
    
    When a nudge fires, a background ReviewAgent silently analyzes the conversation
    and decides whether to save memories or create/patch skills.
    """
    
    def __init__(
        self,
        client: Any,
        config: Any,
        memory_nudge_interval: int = 10,
        skill_nudge_interval: int = 10,
        enabled: bool = True
    ):
        self.client = client
        self.config = config
        self.enabled = enabled
        
        # Intervals (configurable)
        self.memory_nudge_interval = memory_nudge_interval
        self.skill_nudge_interval = skill_nudge_interval
        
        # Counters
        self._turns_since_memory = 0
        self._iters_since_skill = 0
        
        # State tracking
        self._pending_review = False
        self._review_tasks: set = set()
    
    def on_user_turn(self) -> None:
        """Call this after each user message."""
        if not self.enabled:
            return
        self._turns_since_memory += 1
    
    def on_tool_iteration(self) -> None:
        """Call this after each tool iteration round."""
        if not self.enabled:
            return
        self._iters_since_skill += 1
    
    def on_memory_saved(self) -> None:
        """Reset memory counter when agent actively saves memory."""
        self._turns_since_memory = 0
    
    def on_skill_managed(self) -> None:
        """Reset skill counter when agent actively manages a skill."""
        self._iters_since_skill = 0
    
    async def maybe_trigger_review(
        self,
        messages_snapshot: list[dict],
        quiet: bool = True
    ) -> None:
        """Check if any nudge threshold is reached and trigger review if so.
        
        This should be called after the final response is sent to the user,
        so the review happens silently without blocking the conversation.
        """
        if not self.enabled:
            return
        
        review_memory = self._turns_since_memory >= self.memory_nudge_interval
        review_skills = self._iters_since_skill >= self.skill_nudge_interval
        
        if not review_memory and not review_skills:
            return
        
        if self._pending_review:
            return
        
        self._pending_review = True
        
        # Reset counters immediately so we don't double-trigger
        if review_memory:
            self._turns_since_memory = 0
        if review_skills:
            self._iters_since_skill = 0
        
        # Start background review
        task = asyncio.create_task(
            self._run_background_review(
                messages_snapshot,
                review_memory=review_memory,
                review_skills=review_skills,
                quiet=quiet
            )
        )
        self._review_tasks.add(task)
        task.add_done_callback(self._review_tasks.discard)
    
    async def _run_background_review(
        self,
        messages_snapshot: list[dict],
        review_memory: bool = False,
        review_skills: bool = False,
        quiet: bool = True
    ) -> None:
        """Run review agent in background."""
        try:
            review_agent = ReviewAgent(self.client, self.config)
            
            # Review memory
            if review_memory:
                memory_mgr = get_memory_manager()
                current_memories = memory_mgr.load_for_session()
                result = await review_agent.review_memory(
                    messages_snapshot,
                    current_memories=current_memories
                )
                if result:
                    await self._apply_memory_result(result, quiet=quiet)
            
            # Review skills
            if review_skills:
                skill_mgr = get_skill_library()
                current_skills = skill_mgr.build_index_prompt()
                result = await review_agent.review_skills(
                    messages_snapshot,
                    current_skills_index=current_skills
                )
                if result:
                    await self._apply_skill_result(result, quiet=quiet)
        
        except Exception:
            # Silently fail — review should never break the main flow
            pass
        finally:
            self._pending_review = False
    
    async def _apply_memory_result(self, result: dict, quiet: bool = True) -> None:
        """Apply a memory save action from review agent."""
        try:
            memory_mgr = get_memory_manager()
            name = result.get("name") or result.get("short_name", "review_memory")
            mem_type = result.get("type", "feedback")
            description = result.get("description", "Auto-saved from review")
            content = result.get("content", "")
            
            if content:
                save_result = memory_mgr.save(name, mem_type, content, description)
                if save_result.get("success") and not quiet:
                    print(f"[Nudge] Memory saved: {name}")
        except Exception:
            pass
    
    async def _apply_skill_result(self, result: dict, quiet: bool = True) -> None:
        """Apply a skill create/patch action from review agent."""
        try:
            from ..skills.handlers import handle_skill_manage
            
            action = result.get("action", "")
            name = result.get("name", "")
            
            if "create" in action:
                category = result.get("category", "general")
                description = result.get("description", "")
                content = result.get("content", "")
                if content:
                    handle_skill_manage(
                        action="create",
                        name=name,
                        category=category,
                        description=description,
                        content=content
                    )
                    if not quiet:
                        print(f"[Nudge] Skill created: {name}")
            
            elif "patch" in action:
                old_string = result.get("old_string", "")
                new_string = result.get("new_string", "")
                if old_string and new_string:
                    handle_skill_manage(
                        action="patch",
                        name=name,
                        old_string=old_string,
                        new_string=new_string
                    )
                    if not quiet:
                        print(f"[Nudge] Skill patched: {name}")
        
        except Exception:
            pass
