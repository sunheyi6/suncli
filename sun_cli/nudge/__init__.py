"""Nudge Engine - Self-Improving review triggers (Phase 2).

The Nudge Engine maintains two counters:
- Memory nudge: every N user turns, review for durable facts
- Skill nudge: every N tool iterations, review for procedural learnings

When thresholds are reached, a background ReviewAgent silently analyzes
the conversation and decides what to save — without interrupting the user.
"""

from .engine import NudgeEngine
from .review_agent import ReviewAgent

__all__ = ["NudgeEngine", "ReviewAgent"]
