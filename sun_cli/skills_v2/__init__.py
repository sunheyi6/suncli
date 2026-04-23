"""Skills v2 - Hermes-style procedural memory system.

This module provides a self-improving skill system where the AI can:
- View skills on-demand (progressive loading)
- Create skills after overcoming complex tasks
- Patch skills when new pitfalls are discovered
- Track lifecycle metadata (use_count, success_rate, last_used)
"""

from .skill import SkillEntry
from .manager import SkillManagerV2, get_skill_manager_v2

__all__ = ["SkillEntry", "SkillManagerV2", "get_skill_manager_v2"]
