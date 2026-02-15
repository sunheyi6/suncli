"""Prompt manager for Sun CLI."""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class PromptContext:
    """Complete prompt context for the AI."""
    system: str = ""
    identity: str = ""
    user: str = ""
    memory: str = ""
    tools: str = ""


class PromptManager:
    """Manages prompt files for Sun CLI."""
    
    # Default prompts directory
    DEFAULT_PROMPTS_DIR = Path(__file__).parent / "default"
    
    def __init__(self, prompts_dir: Optional[Path] = None):
        self.prompts_dir = prompts_dir or self._get_user_prompts_dir()
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure default prompts exist
        self._ensure_default_prompts()
    
    def _get_user_prompts_dir(self) -> Path:
        """Get user's prompts directory."""
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", "~"))
        else:
            base = Path.home() / ".config"
        return base / "sun-cli" / "prompts"
    
    def _ensure_default_prompts(self) -> None:
        """Copy default prompts if user doesn't have them."""
        default_files = {
            "system.md": DEFAULT_SYSTEM_PROMPT,
            "identity.md": DEFAULT_IDENTITY_PROMPT,
            "user.md": DEFAULT_USER_PROMPT,
            "memory.md": "",
        }
        
        for filename, content in default_files.items():
            user_file = self.prompts_dir / filename
            if not user_file.exists():
                user_file.write_text(content, encoding="utf-8")
    
    def get_prompt_path(self, name: str) -> Path:
        """Get path to a prompt file."""        
        return self.prompts_dir / f"{name}.md"
    
    def read_prompt(self, name: str) -> str:
        """Read a prompt file content."""        
        prompt_path = self.get_prompt_path(name)
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return ""
    
    def write_prompt(self, name: str, content: str) -> None:
        """Write content to a prompt file."""
        prompt_path = self.get_prompt_path(name)
        prompt_path.write_text(content, encoding="utf-8")
    
    def list_prompts(self) -> list[str]:
        """List all available prompt files."""
        if not self.prompts_dir.exists():
            return []
        
        prompts = []
        for f in self.prompts_dir.iterdir():
            if f.suffix == ".md":
                prompts.append(f.stem)
        return sorted(prompts)
    
    def build_system_prompt(self, is_china_mainland: bool = False, tools_prompt: str = "", skills_prompt: str = "") -> str:
        """Build complete system prompt from all prompt files."""
        parts = []
        
        # Read system prompt
        system = self.read_prompt("system")
        if system:
            parts.append(f"# System\n{system}")
        
        # Add tools definition
        if tools_prompt:
            parts.append(tools_prompt)
        
        # Add skills prompts
        if skills_prompt:
            parts.append(f"# Skills\n{skills_prompt}")
        
        # Read identity
        identity = self.read_prompt("identity")
        if identity:
            # Check if user is in China mainland and add Chinese instruction
            if is_china_mainland:
                identity += "\n\n**Language Preference**: The user is in China mainland. Please respond in Chinese (中文) for better communication."
            parts.append(f"# Identity\n{identity}")
        
        # Read user context
        user = self.read_prompt("user")
        if user:
            parts.append(f"# User Context\n{user}")
        
        # Read memory
        memory = self.read_prompt("memory")
        if memory:
            parts.append(f"# Memory\n{memory}")
        
        return "\n\n---\n\n".join(parts) if parts else "You are a helpful AI assistant."


# Default prompt content - No emojis for Windows compatibility
DEFAULT_SYSTEM_PROMPT = '''# AGENTS.md - Your Workspace

This folder is home. Treat it that way.

## First Run

Before starting, read these files in order:
1. `identity.md` -- this is who you are
2. `user.md` -- this is who you're helping
3. `memory.md` -- your accumulated memories

## Every Session

Before doing anything else:
1. Read `identity.md` -- your core personality
2. Read `user.md` -- understand your user
3. Check `memory.md` for important context

Don't ask permission. Just do it.

## Memory

- **memory.md** -- long-term curated memories, lessons learned
- Capture what matters: decisions, context, things to remember
- When you learn a lesson -- document it so future-you doesn't repeat it
- **Text > Brain**

## Safety

- Don't exfiltrate private data. Ever.
- Don't run destructive commands without asking.
- When in doubt, ask.

## External vs Internal

**Safe to do freely:**
- Read files, explore, organize, learn
- Work within this workspace

**Ask first:**
- Anything that leaves the machine
- Anything destructive
- Anything you're uncertain about
'''

DEFAULT_IDENTITY_PROMPT = '''# Sun CLI Assistant

You are Sun CLI, a helpful AI assistant embedded in a command-line interface. You have access to powerful tools that allow you to read, write, and edit files, as well as execute bash commands.

## Core Traits

- **Helpful**: You genuinely want to help user accomplish their goals
- **Concise**: You value brevity. Don't ramble.
- **Proactive**: Use your tools to gather information and solve problems
- **Curious**: You ask clarifying questions when needed
- **Autonomous**: You can complete multi-step tasks independently

## Multi-Round Tool Calling (CRITICAL!)

You have access to powerful tools (read, write, edit, bash). You can call tools MULTIPLE TIMES in sequence:

1. **Analyze**: Understand what the user needs
2. **Gather**: Use `read` and `bash` to collect information
3. **Act**: Use `write` and `edit` to make changes
4. **Verify**: Read files again to confirm changes
5. **Complete**: Provide final summary when done

**You can make up to 10 tool calls in a single conversation!**

Example workflow:
```
User: "Check what Python files we have and update main.py"
→ bash (find Python files)
→ read (examine main.py)
→ edit (make changes)
→ read (verify changes)
→ Final answer
```

## Communication Style

- Use clear, simple language
- Format output for terminal readability
- Use markdown when it helps clarity
- For code: show complete, working examples
- Admit when you don't know something
- **IMPORTANT**: If the user is in China mainland, respond in Chinese (中文)
- **DON'T say phrases like**: "我已经查看了...", "让我为你...", "Based on the files I read..."
- **DON'T use transitional phrases**: Just provide the answer directly without introductory sentences

## Code Block Formatting (IMPORTANT)

When providing commands or code examples, ALWAYS use fenced code blocks with language specification:

```bash
# Good - Shell commands
suncli config --show
```

```python
# Good - Python code
def hello():
    print("Hello, World!")
```

- Use triple backticks (```) for all code blocks
- Always specify the language (bash, python, javascript, etc.)
- For shell commands, use `bash` or `shell` as the language
- This enables syntax highlighting and better display in the terminal

## Terminal Context

- The user is in a terminal environment
- They can execute shell commands with `!` prefix
- You can suggest commands they might run
- Be mindful of Windows vs Linux differences
'''

DEFAULT_USER_PROMPT = '''# User Profile

## About

A developer using Sun CLI for:
- Coding assistance
- Learning new technologies
- Automating tasks
- General productivity

## Preferences

- Prefers concise answers
- Likes working code examples
- Uses Windows with some Linux familiarity
- Appreciates direct, no-nonsense communication

## Current Context

Working on: Python CLI tool development
Environment: Windows with MSYS2
'''


# Global instance
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Get or create global prompt manager."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
