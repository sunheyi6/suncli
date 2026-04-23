"""Skill framework for Sun CLI - modular extension system + procedural memory library.

This module provides two complementary skill systems:
1. Classic Skills: Command interceptors triggered by keywords (GitSkill, PromptSkill, etc.)
2. Procedural Library: Experience playbooks created and maintained by the Agent itself
"""

from .skill import Skill, SkillContext, SkillManager, get_skill_manager
from .entry import SkillEntry
from .library import SkillLibrary, get_skill_library
from .handlers import handle_skill_view, handle_skill_manage, SKILL_VIEW_SCHEMA, SKILL_MANAGE_SCHEMA

__all__ = [
    # Classic skill framework
    "Skill",
    "SkillContext",
    "SkillManager",
    "get_skill_manager",
    # Procedural memory (Self-Improving)
    "SkillEntry",
    "SkillLibrary",
    "get_skill_library",
    "handle_skill_view",
    "handle_skill_manage",
    "SKILL_VIEW_SCHEMA",
    "SKILL_MANAGE_SCHEMA",
]
