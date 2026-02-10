"""Prompt management skill for Sun CLI."""

from typing import Optional
from ..skills import Skill, SkillContext
from ..prompts import get_prompt_manager
from rich.panel import Panel


class PromptSkill(Skill):
    """Prompt management skill."""
    
    @property
    def name(self) -> str:
        return "prompt"
    
    @property
    def description(self) -> str:
        return "Manage AI prompt files (system.md, identity.md, user.md, memory.md)"
    
    @property
    def trigger_keywords(self) -> list[str]:
        return [
            "编辑提示词", "修改提示词", "edit prompt", "修改 identity",
            "修改 system", "修改 user", "修改 memory", "查看提示词"
        ]
    
    @property
    def system_prompt(self) -> Optional[str]:
        return """## Prompt Management

You can help users manage their prompt files:
- system.md: Workspace guidelines, safety rules, memory management
- identity.md: AI personality, communication style, core traits
- user.md: User preferences, context, work environment
- memory.md: Long-term memories, lessons learned, curated notes

Users can edit these files to customize your behavior.
"""
    
    def initialize(self, context: SkillContext) -> None:
        super().initialize(context)
        self.pm = get_prompt_manager()
    
    async def handle(self, user_input: str) -> bool:
        lower_input = user_input.lower()
        
        if "编辑提示词" in lower_input or "修改提示词" in lower_input or "edit prompt" in lower_input:
            self._show_prompt_help()
            return True
        
        if "查看提示词" in lower_input or "show prompt" in lower_input:
            self._show_current_prompt()
            return True
        
        if "修改 identity" in lower_input or "edit identity" in lower_input:
            self._edit_prompt("identity")
            return True
        
        if "修改 system" in lower_input or "edit system" in lower_input:
            self._edit_prompt("system")
            return True
        
        if "修改 user" in lower_input or "edit user" in lower_input:
            self._edit_prompt("user")
            return True
        
        if "修改 memory" in lower_input or "edit memory" in lower_input:
            self._edit_prompt("memory")
            return True
        
        return False
    
    def _show_prompt_help(self):
        self.context.console.print(Panel(
            """[bold]Prompt Management Commands:[/bold]

Use CLI commands to manage prompts:
  [cyan]suncli prompt --list[/cyan]        - List all prompt files
  [cyan]suncli prompt --show <name>[/cyan]  - View a prompt file
  [cyan]suncli prompt --edit <name>[/cyan]  - Edit a prompt file
  [cyan]suncli prompt --path[/cyan]        - Show prompts directory

Available prompts:
  [cyan]system.md[/cyan]   - Workspace guidelines and safety rules
  [cyan]identity.md[/cyan] - AI personality and communication style
  [cyan]user.md[/cyan]     - User preferences and context
  [cyan]memory.md[/cyan]   - Long-term memories and lessons""",
            title="Prompt Management",
            border_style="blue"
        ))
    
    def _show_current_prompt(self):
        system = self.pm.build_system_prompt()
        self.context.console.print(Panel(
            system[:2000] + "..." if len(system) > 2000 else system,
            title="Current System Prompt Preview",
            border_style="green"
        ))
    
    def _edit_prompt(self, name: str):
        import subprocess
        import os
        
        prompt_path = self.pm.get_prompt_path(name)
        if not prompt_path.exists():
            prompt_path.write_text(f"# {name.title()} Prompt\n\n", encoding="utf-8")
            self.context.console.print(f"[green][OK][/green] Created {name}.md")
        
        editor = os.environ.get("EDITOR", "notepad" if os.name == "nt" else "nano")
        try:
            subprocess.run([editor, str(prompt_path)], check=False)
            self.context.console.print(f"[green][OK][/green] Saved {name}.md")
        except FileNotFoundError:
            self.context.console.print(f"[red]Editor '{editor}' not found.[/red]")
            self.context.console.print(f"[dim]File location: {prompt_path}[/dim]")
