"""Standardized tool definitions with schemas (s02)."""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolParameter:
    """Tool parameter definition."""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolDefinition:
    """Standardized tool definition."""
    name: str
    description: str
    parameters: list[ToolParameter]
    handler: Callable = None
    
    def to_schema(self) -> dict[str, Any]:
        """Convert to JSON schema format."""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.required:
                required.append(param.name)
                
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }
    
    def to_prompt_text(self) -> str:
        """Convert to prompt-friendly text."""
        lines = [f"### {self.name}", f"{self.description}", ""]
        
        if self.parameters:
            lines.append("Parameters:")
            for param in self.parameters:
                req_mark = " (required)" if param.required else " (optional)"
                lines.append(f"  - {param.name}: {param.type}{req_mark} - {param.description}")
                
        return "\n".join(lines)


# Standard tool definitions
READ_TOOL = ToolDefinition(
    name="read",
    description="Read the contents of a file.",
    parameters=[
        ToolParameter("file_path", "string", "Path to the file"),
        ToolParameter("limit", "integer", "Maximum lines to read", required=False),
        ToolParameter("offset", "integer", "Starting line number", required=False),
    ],
)

WRITE_TOOL = ToolDefinition(
    name="write",
    description="Write content to a file (creates new or overwrites existing).",
    parameters=[
        ToolParameter("file_path", "string", "Path to the file"),
        ToolParameter("content", "string", "Content to write"),
    ],
)

EDIT_TOOL = ToolDefinition(
    name="edit",
    description="Edit a file by replacing a specific string.",
    parameters=[
        ToolParameter("file_path", "string", "Path to the file"),
        ToolParameter("old_str", "string", "Exact string to search for (must match exactly!)"),
        ToolParameter("new_str", "string", "Replacement string"),
    ],
)

BASH_TOOL = ToolDefinition(
    name="bash",
    description="Execute a shell command.",
    parameters=[
        ToolParameter("command", "string", "Command to execute"),
        ToolParameter("cwd", "string", "Working directory (optional)", required=False),
        ToolParameter("timeout", "integer", "Timeout in seconds (default: 60)", required=False),
    ],
)

# s04: Subagent tool
SUBAGENT_TOOL = ToolDefinition(
    name="subagent",
    description="Spawn a subagent with fresh context to handle a complex subtask. "
                "The subagent will run independently and return a summary.",
    parameters=[
        ToolParameter("prompt", "string", "The task for the subagent to perform"),
        ToolParameter("tools", "array", "List of tools the subagent can use", required=False),
    ],
)

# s13: Background task tool
BACKGROUND_RUN_TOOL = ToolDefinition(
    name="background_run",
    description="Run a slow command in the background. Returns immediately with a task_id. "
                "Use background_check to get results later.",
    parameters=[
        ToolParameter("command", "string", "Command to run in background"),
        ToolParameter("description", "string", "Description of what this command does", required=False),
    ],
)

BACKGROUND_CHECK_TOOL = ToolDefinition(
    name="background_check",
    description="Check status and results of background tasks.",
    parameters=[
        ToolParameter("task_id", "string", "Task ID to check (optional, checks all if omitted)", required=False),
    ],
)

# s14: Cron/Scheduler tool
SCHEDULE_CREATE_TOOL = ToolDefinition(
    name="schedule_create",
    description="Create a scheduled task that runs at specified times (cron format).",
    parameters=[
        ToolParameter("cron", "string", "Cron expression (e.g., '0 9 * * 1' for weekly Monday 9am)"),
        ToolParameter("prompt", "string", "The prompt/task to execute when triggered"),
        ToolParameter("recurring", "boolean", "Whether this repeats (default: True)", required=False),
        ToolParameter("name", "string", "Name for this schedule", required=False),
    ],
)

SCHEDULE_LIST_TOOL = ToolDefinition(
    name="schedule_list",
    description="List all scheduled tasks.",
    parameters=[],
)

SCHEDULE_REMOVE_TOOL = ToolDefinition(
    name="schedule_remove",
    description="Remove a scheduled task.",
    parameters=[
        ToolParameter("schedule_id", "string", "ID of schedule to remove"),
    ],
)

# s15-s16: Team tools
TEAM_SPAWN_TOOL = ToolDefinition(
    name="team_spawn",
    description="Spawn a persistent teammate with a specific role.",
    parameters=[
        ToolParameter("name", "string", "Name of the teammate"),
        ToolParameter("role", "string", "Role (e.g., 'coder', 'tester', 'reviewer')"),
        ToolParameter("prompt", "string", "Initial instructions for the teammate"),
    ],
)

TEAM_SEND_TOOL = ToolDefinition(
    name="team_send",
    description="Send a message to a teammate's inbox.",
    parameters=[
        ToolParameter("to", "string", "Name of teammate"),
        ToolParameter("content", "string", "Message content"),
    ],
)

TEAM_LIST_TOOL = ToolDefinition(
    name="team_list",
    description="List all teammates and their status.",
    parameters=[],
)

# s16: Protocol tools
REQUEST_APPROVAL_TOOL = ToolDefinition(
    name="request_approval",
    description="Request approval for a high-risk action from lead/user.",
    parameters=[
        ToolParameter("action", "string", "Description of action requesting approval"),
        ToolParameter("request_id", "string", "Unique identifier for this request"),
    ],
)

# s18: Worktree tools
WORKTREE_CREATE_TOOL = ToolDefinition(
    name="worktree_create",
    description="Create a git worktree (isolated workspace) for a task.",
    parameters=[
        ToolParameter("name", "string", "Name for this worktree"),
        ToolParameter("task_id", "integer", "Task ID to bind to"),
    ],
)

WORKTREE_ENTER_TOOL = ToolDefinition(
    name="worktree_enter",
    description="Enter a worktree context for subsequent commands.",
    parameters=[
        ToolParameter("name", "string", "Name of worktree to enter"),
    ],
)

WORKTREE_CLOSEOUT_TOOL = ToolDefinition(
    name="worktree_closeout",
    description="Close out a worktree - keep or remove it.",
    parameters=[
        ToolParameter("name", "string", "Name of worktree"),
        ToolParameter("action", "string", "'keep' to preserve, 'remove' to delete"),
        ToolParameter("reason", "string", "Reason for this action"),
        ToolParameter("complete_task", "boolean", "Also mark bound task as completed", required=False),
    ],
)

# s20: Self-Improving Skills (v2)
SKILL_VIEW_TOOL = ToolDefinition(
    name="skill_view",
    description="Load a skill by name to see its full content (Steps, Pitfalls, When to use). Use this when a skill in the index seems relevant to the current task.",
    parameters=[
        ToolParameter("name", "string", "Name of the skill to load"),
    ],
)

SKILL_MANAGE_TOOL = ToolDefinition(
    name="skill_manage",
    description=(
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
    parameters=[
        ToolParameter("action", "string", "One of: create, patch, delete, list, stats"),
        ToolParameter("name", "string", "Skill name", required=False),
        ToolParameter("category", "string", "Category for create (e.g., devops, software-development)", required=False),
        ToolParameter("description", "string", "Short one-line description", required=False),
        ToolParameter("content", "string", "Full markdown content with Steps, Pitfalls, When to use sections", required=False),
        ToolParameter("old_string", "string", "Exact text to find for patch", required=False),
        ToolParameter("new_string", "string", "Replacement text for patch", required=False),
        ToolParameter("version", "string", "Semantic version (default: 1.0.0)", required=False),
    ],
)

# Web Search tool (DuckDuckGo)
WEB_SEARCH_TOOL = ToolDefinition(
    name="web_search",
    description="Search the web using DuckDuckGo. Returns search results including titles, URLs, and snippets.",
    parameters=[
        ToolParameter("query", "string", "Search query"),
        ToolParameter("max_results", "integer", "Maximum results (1-10, default: 5)", required=False),
    ],
)

WEATHER_NOW_TOOL = ToolDefinition(
    name="weather_now",
    description="Get current weather and today's forecast for a city/location.",
    parameters=[
        ToolParameter("location", "string", "Location name, e.g. 'Beijing' or '北京'", required=False),
    ],
)

# Collect all tools
ALL_TOOLS: list[ToolDefinition] = [
    READ_TOOL,
    WRITE_TOOL,
    EDIT_TOOL,
    BASH_TOOL,
    WEB_SEARCH_TOOL,  # Web search
    WEATHER_NOW_TOOL,
    SUBAGENT_TOOL,
    BACKGROUND_RUN_TOOL,
    BACKGROUND_CHECK_TOOL,
    SCHEDULE_CREATE_TOOL,
    SCHEDULE_LIST_TOOL,
    SCHEDULE_REMOVE_TOOL,
    TEAM_SPAWN_TOOL,
    TEAM_SEND_TOOL,
    TEAM_LIST_TOOL,
    REQUEST_APPROVAL_TOOL,
    WORKTREE_CREATE_TOOL,
    WORKTREE_ENTER_TOOL,
    WORKTREE_CLOSEOUT_TOOL,
    SKILL_VIEW_TOOL,
    SKILL_MANAGE_TOOL,
]


def get_tool_schemas() -> list[dict]:
    """Get all tool schemas for LLM."""
    return [tool.to_schema() for tool in ALL_TOOLS]


def build_tools_prompt() -> str:
    """Build the tools section of system prompt with strict constraints."""
    lines = [
        "# Available Tools",
        "",
        "## CRITICAL: Tool Call Format Rules (STRICT)",
        "",
        "When you need to use a tool, you MUST output ONLY the tool call JSON. "
        "Do NOT output natural language explanations, apologies, or transitional phrases before or after the tool call.",
        "",
        "**Correct:**",
        "```json",
        '{"tool": "read", "args": {"file_path": "src/main.py"}}',
        "```",
        "",
        "**Wrong (DO NOT DO THIS):**",
        "```",
        'Sure, let me read the file for you.',  # 自然语言废话 - 禁止
        '{"tool": "read", "args": {"file_path": "src/main.py"}}',
        "```",
        "",
        "**Rule**: If you need to call a tool, output ONLY the JSON. No '我先看看', '让我为你', 'Sure, I will' etc.",
        "",
        "## Tool Call Format",
        "",
        "```json",
        '{"tool": "tool_name", "args": {"param1": "value1", "param2": "value2"}}',
        "```",
        "",
    ]

    for tool in ALL_TOOLS:
        lines.append(tool.to_prompt_text())
        lines.append("")

    lines.extend([
        "## Tool Responsibility Separation (CRITICAL)",
        "",
        "### read tool",
        "- **ONLY for reading files**. The file_path MUST point to an existing file.",
        "- **NEVER pass a directory to read**. If you need to see what's in a directory, use `bash` instead.",
        "- If the file does not exist, the system will return an error. Do NOT guess file paths.",
        "",
        "### bash tool",
        "- Use for: listing directory contents, git operations, running tests, searching files.",
        "- For directory listings: use `bash` with `ls -la` (Linux/Mac) or `Get-ChildItem` (Windows).",
        "- For finding files: use `bash` with `find` or `glob` patterns.",
        "",
        "## Path Integrity Rules (CRITICAL)",
        "",
        "1. **NEVER invent file paths**. Only use paths that have been confirmed to exist by previous `bash` or `read` results.",
        "2. **If unsure about a path**, call `bash` first to list the directory and confirm.",
        "3. **Before reading a file**, ensure you know its exact path from prior tool results, not from memory or guess.",
        "4. **Do NOT assume project structure**. Always verify with `bash` if you haven't seen the structure yet.",
        "",
        "## Multi-Round Tool Calling",
        "",
        "You can call tools MULTIPLE TIMES in sequence. Workflow:",
        "1. Analyze the user's request",
        "2. Call tools to gather information (ONLY JSON output, no natural language)",
        "3. Receive tool results",
        "4. Call MORE tools if needed (ONLY JSON output)",
        "5. Repeat until you have all information",
        "6. Finally, provide your answer WITHOUT tool calls",
        "",
        "## Tool Usage Guidelines",
        "",
        "1. **Always verify paths first**: Use `bash` to list directories before reading files in unknown projects",
        "2. **Be precise with edit**: old_str must match exactly",
        "3. **Multi-step tasks**: Break complex tasks into multiple tool calls",
        "4. **Verify results**: After editing, read the file again",
        "5. **Handle errors**: If a tool fails, analyze the error message and follow the correction hint provided",
        "6. **Weather questions**: For weather/current conditions, use `weather_now` first and avoid guessing",
        "",
        "## Skill System (Self-Improving)",
        "",
        "Skills are procedural memory — reusable playbooks for recurring tasks.",
        "- **Memory** stores facts (what you know). **Skills** store procedures (how to do things).",
        "- If you've discovered a new way to do something, save it as a skill.",
        "- Skills that aren't maintained become liabilities — patch them when you find issues.",
        "- Use `skill_view` to load a skill's full content before following it.",
        "",
    ])

    return "\n".join(lines)
