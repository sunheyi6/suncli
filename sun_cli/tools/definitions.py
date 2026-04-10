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

# Collect all tools
ALL_TOOLS: list[ToolDefinition] = [
    READ_TOOL,
    WRITE_TOOL,
    EDIT_TOOL,
    BASH_TOOL,
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
]


def get_tool_schemas() -> list[dict]:
    """Get all tool schemas for LLM."""
    return [tool.to_schema() for tool in ALL_TOOLS]


def build_tools_prompt() -> str:
    """Build the tools section of system prompt."""
    lines = [
        "# Available Tools",
        "",
        "You have access to the following tools. When you need to use a tool, "
        "output the tool call in XML format:",
        "",
        "```xml",
        '<tool name="tool_name">',
        '  <arg name="param1">value1</arg>',
        '  <arg name="param2">value2</arg>',
        "</tool>",
        "```",
        "",
    ]
    
    for tool in ALL_TOOLS:
        lines.append(tool.to_prompt_text())
        lines.append("")
        
    lines.extend([
        "## Multi-Round Tool Calling",
        "",
        "You can call tools MULTIPLE TIMES in sequence! The system supports iterative tool calling:",
        "1. Analyze the user's request",
        "2. Call tools to gather information",
        "3. Receive tool results",
        "4. Call MORE tools if needed",
        "5. Repeat until you have all information",
        "6. Finally, provide your answer WITHOUT tool calls",
        "",
        "## Tool Usage Guidelines",
        "",
        "1. **Always read first**: Use `read` to understand existing code",
        "2. **Be precise with edit**: old_str must match exactly",
        "3. **Multi-step tasks**: Break complex tasks into multiple tool calls",
        "4. **Verify results**: After editing, read the file again",
        "5. **Use bash wisely**: For git operations, tests, file listing",
        "6. **Handle errors**: If a tool fails, analyze and try alternatives",
        "",
    ])
    
    return "\n".join(lines)
