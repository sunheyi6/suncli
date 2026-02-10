"""Plan mode management for Sun CLI - inspired by Claude Code."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text


class PlanMode(Enum):
    """Plan mode states."""
    INACTIVE = "inactive"
    PLANNING = "planning"
    APPROVED = "approved"
    EXECUTING = "executing"


@dataclass
class PlanStep:
    """A single step in a plan."""
    id: int
    description: str
    status: str = "pending"


@dataclass
class Plan:
    """A plan with multiple steps."""
    title: str
    description: str
    steps: List[PlanStep] = field(default_factory=list)
    status: PlanMode = PlanMode.PLANNING
    
    def add_step(self, description: str) -> PlanStep:
        """Add a step to the plan."""
        step_id = len(self.steps) + 1
        step = PlanStep(id=step_id, description=description)
        self.steps.append(step)
        return step
    
    def to_markdown(self) -> str:
        """Convert plan to markdown format."""
        md = f"# {self.title}\n\n"
        md += f"{self.description}\n\n"
        md += "## Implementation Steps\n\n"
        for step in self.steps:
            status_icon = {"pending": "⏳", "in_progress": "🔄", "completed": "✅"}.get(step.status, "⏳")
            md += f"{status_icon} **Step {step.id}:** {step.description}\n\n"
        return md


class PlanModeManager:
    """Manages plan mode state and operations."""
    
    def __init__(self, console: Console):
        self.console = console
        self._mode: PlanMode = PlanMode.INACTIVE
        self._current_plan: Optional[Plan] = None
        self._original_user_input: Optional[str] = None
    
    @property
    def is_active(self) -> bool:
        """Check if plan mode is active."""
        return self._mode != PlanMode.INACTIVE
    
    @property
    def mode(self) -> PlanMode:
        """Get current plan mode."""
        return self._mode
    
    @property
    def current_plan(self) -> Optional[Plan]:
        """Get current plan."""
        return self._current_plan
    
    def start_planning(self, user_input: str) -> None:
        """Start planning mode for a user request."""
        self._mode = PlanMode.PLANNING
        self._original_user_input = user_input
        self._current_plan = Plan(
            title="Implementation Plan",
            description=f"Plan for: {user_input}"
        )
        self.console.print(Panel(
            "[bold cyan]📋 Entering Plan Mode[/bold cyan]\n\n"
            "[dim]AI will create a plan before executing. You can review and approve the plan before implementation.[/dim]",
            border_style="cyan"
        ))
    
    def set_plan(self, title: str, description: str, steps: List[str]) -> None:
        """Set the current plan with steps."""
        if not self._current_plan:
            self._current_plan = Plan(title=title, description=description)
        
        self._current_plan.title = title
        self._current_plan.description = description
        self._current_plan.steps.clear()
        for step_desc in steps:
            self._current_plan.add_step(step_desc)
        
        self._mode = PlanMode.PLANNING
        self.display_plan()
    
    def display_plan(self) -> None:
        """Display the current plan."""
        if not self._current_plan:
            self.console.print("[yellow]No plan to display.[/yellow]")
            return
        
        plan_md = self._current_plan.to_markdown()
        self.console.print(Panel(
            Markdown(plan_md),
            title="[bold cyan]📋 Plan Preview[/bold cyan]",
            border_style="cyan"
        ))
        
        self.console.print("\n[dim]Commands:[/dim]")
        self.console.print("  [cyan]/approve[/cyan] - Approve and execute the plan")
        self.console.print("  [cyan]/modify[/cyan] - Request plan modifications")
        self.console.print("  [cyan]/cancel[/cyan] - Cancel plan mode")
    
    def approve(self) -> bool:
        """Approve the plan and move to execution."""
        if self._mode != PlanMode.PLANNING:
            self.console.print("[yellow]No plan to approve.[/yellow]")
            return False
        
        self._mode = PlanMode.APPROVED
        self.console.print(Panel(
            "[bold green]✅ Plan Approved![/bold green]\n\n"
            "[dim]Proceeding with implementation...[/dim]",
            border_style="green"
        ))
        return True
    
    def cancel(self) -> None:
        """Cancel plan mode."""
        self._mode = PlanMode.INACTIVE
        self._current_plan = None
        self._original_user_input = None
        self.console.print(Panel(
            "[bold yellow]Plan Mode Cancelled[/bold yellow]",
            border_style="yellow"
        ))
    
    def update_step_status(self, step_id: int, status: str) -> None:
        """Update status of a specific step."""
        if not self._current_plan:
            return
        
        for step in self._current_plan.steps:
            if step.id == step_id:
                step.status = status
                break
    
    def get_system_prompt(self) -> str:
        """Get system prompt for plan mode."""
        return """# Plan Mode Instructions

You are currently in PLAN MODE. When the user asks you to perform a task that requires writing code or making changes:

1. **First, create a detailed plan** before taking any action:
   - Analyze the user's request carefully
   - Break down the task into clear, actionable steps
   - Consider dependencies and potential issues
   - Use the TodoWrite tool to create a task list

2. **Present the plan** in a clear format:
   - Title: A concise title for the plan
   - Description: Brief overview of what will be done
   - Steps: Numbered list of specific steps to implement

3. **Wait for user approval** before executing:
   - The user will use /approve to confirm
   - The user may use /modify to request changes
   - The user may use /cancel to abort

4. **After approval**, execute the plan step by step:
   - Mark each step as in_progress when starting
   - Mark each step as completed when done
   - Update the todo list as you progress

5. **When all steps are complete**, use the ExitPlanMode tool to exit plan mode.

IMPORTANT: Do NOT write any code or make any changes until the user approves the plan with /approve.
"""
    
    def get_exit_instruction(self) -> str:
        """Get instruction for exiting plan mode."""
        return """IMPORTANT: You have completed the plan. Use the ExitPlanMode tool to exit plan mode and return to normal operation.

The ExitPlanMode tool should be called with:
- title: A concise title for the plan (e.g., "Implement User Authentication")
- plan: A markdown formatted plan with implementation steps

Example:
ExitPlanMode(title="Implement User Authentication", plan="# Implement User Authentication\\n\\n## Steps\\n1. Create user model\\n2. Add authentication endpoints\\n3. Implement JWT validation")
"""
