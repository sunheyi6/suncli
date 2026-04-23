"""Tool handlers for skill_view and skill_manage (Self-Improving Phase 1)."""

from typing import Any

from .manager import get_skill_manager_v2


def handle_skill_view(name: str) -> str:
    """Load and return full content of a skill.
    
    Args:
        name: Name of the skill to view
    """
    manager = get_skill_manager_v2()
    content = manager.load_full(name)
    
    if content:
        # Record that this skill was viewed (counts as usage attempt)
        manager.record_usage(name, success=True)
        return f"Skill: {name}\n\n{content}"
    
    # List available skills
    skills = manager.list_skills()
    available = "\n".join(f"  - {s.name}: {s.description}" for s in skills) if skills else "  (none)"
    return f"Skill '{name}' not found.\n\nAvailable skills:\n{available}"


def handle_skill_manage(
    action: str,
    name: str = None,
    category: str = None,
    description: str = None,
    content: str = None,
    old_string: str = None,
    new_string: str = None,
    version: str = "1.0.0"
) -> str:
    """Manage skills (create, update/patch, delete).
    
    Skills are procedural memory — reusable approaches for recurring task types.
    
    Args:
        action: One of "create", "patch", "delete", "list", "stats"
        name: Skill name
        category: Category for create (e.g., "devops", "software-development")
        description: Short description
        content: Full markdown content (for create) — should include Steps, Pitfalls, When to use
        old_string: Text to find (for patch)
        new_string: Replacement text (for patch)
        version: Semantic version string
    """
    manager = get_skill_manager_v2()
    action = action.lower().strip()
    
    if action == "list":
        skills = manager.list_skills()
        if not skills:
            return "No skills stored yet."
        
        lines = ["Skills:"]
        for skill in skills:
            meta = f" (uses: {skill.use_count}, success: {skill.success_rate:.0%})"
            lines.append(f"  - {skill.name} [{skill.category}]: {skill.description}{meta}")
        return "\n".join(lines)
    
    if action == "stats":
        stats = manager.get_stats()
        return (
            f"Skill Stats:\n"
            f"  Total: {stats['total']} (active: {stats['active']}, archived: {stats['archived']})\n"
            f"  Total uses: {stats['total_uses']}\n"
            f"  Avg success rate: {stats['avg_success_rate']:.0%}"
        )
    
    if not name:
        return "Error: 'name' is required for this action."
    
    if action == "create":
        if not all([category, description, content]):
            return (
                "Error: 'category', 'description', and 'content' are required for create.\n"
                "Content should include:\n"
                "  ## When to use\n"
                "  ## Steps\n"
                "  ## Pitfalls"
            )
        
        success, msg = manager.create(
            name=name,
            category=category,
            description=description,
            content=content,
            version=version
        )
        
        if success:
            return f"Created skill '{name}': {msg}"
        return f"Error: {msg}"
    
    if action == "patch":
        if old_string is None or new_string is None:
            return "Error: 'old_string' and 'new_string' are required for patch."
        
        success, msg = manager.patch(name, old_string, new_string)
        return msg if success else f"Error: {msg}"
    
    if action == "delete":
        success, msg = manager.delete(name)
        return msg if success else f"Error: {msg}"
    
    return f"Error: Unknown action '{action}'. Use: create, patch, delete, list, stats."


SKILL_VIEW_SCHEMA = {
    "name": "skill_view",
    "description": (
        "Load a skill by name to see its full content (Steps, Pitfalls, When to use). "
        "Use this when a skill in the index seems relevant to the current task."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name of the skill to load"
            }
        },
        "required": ["name"]
    }
}

SKILL_MANAGE_SCHEMA = {
    "name": "skill_manage",
    "description": (
        "Manage skills (create, update/patch, delete). Skills are your procedural memory — "
        "reusable approaches for recurring task types.\n\n"
        "Create when: complex task succeeded (5+ tool calls), errors overcome, "
        "user-corrected approach worked, non-trivial workflow discovered, "
        "or user asks you to remember a procedure.\n"
        "Update when: instructions stale/wrong, OS-specific failures, "
        "missing steps or pitfalls found during use. "
        "If you used a skill and hit issues not covered by it, "
        "patch it immediately with skill_manage(action='patch') — don't wait to be asked.\n\n"
        "After difficult/iterative tasks, offer to save as a skill. "
        "Skip for simple one-offs."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "One of: create, patch, delete, list, stats"
            },
            "name": {
                "type": "string",
                "description": "Skill name"
            },
            "category": {
                "type": "string",
                "description": "Category for create (e.g., devops, software-development)"
            },
            "description": {
                "type": "string",
                "description": "Short one-line description"
            },
            "content": {
                "type": "string",
                "description": "Full markdown content with Steps, Pitfalls, When to use sections"
            },
            "old_string": {
                "type": "string",
                "description": "Exact text to find for patch"
            },
            "new_string": {
                "type": "string",
                "description": "Replacement text for patch"
            },
            "version": {
                "type": "string",
                "description": "Semantic version (default: 1.0.0)"
            }
        },
        "required": ["action"]
    }
}
