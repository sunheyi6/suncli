"""Skill framework for Sun CLI - modular extension system."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
from rich.console import Console


@dataclass
class SkillContext:
    """Context passed to skills."""
    console: Console
    config: Any
    chat_session: Any = None


class Skill(ABC):
    """Base class for all skills."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Skill name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Skill description."""
        pass
    
    @property
    def trigger_keywords(self) -> list[str]:
        """Keywords that can trigger this skill."""
        return []
    
    @property
    def system_prompt(self) -> Optional[str]:
        """Optional system prompt addition for this skill."""
        return None
    
    def initialize(self, context: SkillContext) -> None:
        """Initialize the skill with context."""
        self.context = context
    
    @abstractmethod
    async def handle(self, user_input: str) -> bool:
        """
        Handle user input.
        
        Returns:
            True if the skill handled the input, False otherwise
        """
        pass
    
    def get_help(self) -> str:
        """Get help text for this skill."""
        return f"{self.name}: {self.description}"


class SkillManager:
    """Manages all available skills."""
    
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._context: Optional[SkillContext] = None
    
    def register(self, skill: Skill) -> None:
        """Register a skill."""
        self._skills[skill.name] = skill
    
    def initialize(self, context: SkillContext) -> None:
        """Initialize all skills with context."""
        self._context = context
        for skill in self._skills.values():
            skill.initialize(context)
    
    async def handle(self, user_input: str) -> bool:
        """
        Try to handle user input with registered skills.
        
        Returns:
            True if any skill handled the input, False otherwise
        """
        for skill in self._skills.values():
            if await skill.handle(user_input):
                return True
        return False
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """Get skill by name."""
        return self._skills.get(name)
    
    def list_skills(self) -> list[Skill]:
        """List all registered skills."""
        return list(self._skills.values())
    
    def get_all_system_prompts(self) -> str:
        """Get all skill system prompts combined."""
        prompts = []
        for skill in self._skills.values():
            if skill.system_prompt:
                prompts.append(f"## {skill.name}\n{skill.system_prompt}")
        return "\n\n".join(prompts) if prompts else ""
    
    def get_help_text(self) -> str:
        """Get help text for all skills."""
        if not self._skills:
            return "No skills registered."
        
        lines = ["[bold]Available Skills:[/bold]"]
        for skill in self._skills.values():
            lines.append(f"  [cyan]{skill.name}[/cyan]: {skill.description}")
            
            if skill.trigger_keywords:
                keywords = ", ".join(skill.trigger_keywords)
                lines.append(f"    [dim]Triggers: {keywords}[/dim]")
        
        return "\n".join(lines)


# Global instance
_skill_manager: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    """Get or create global skill manager."""
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
    return _skill_manager
