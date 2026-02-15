"""Core tools for Sun CLI - read, write, edit, bash."""

from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    content: str
    error: Optional[str] = None


def read_file(file_path: str) -> ToolResult:
    """Read file content.
    
    Args:
        file_path: Path to the file to read
        
    Returns:
        ToolResult with file content or error
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return ToolResult(success=False, content="", error=f"File not found: {file_path}")
        
        content = path.read_text(encoding="utf-8")
        return ToolResult(success=True, content=content)
    except Exception as e:
        return ToolResult(success=False, content="", error=str(e))


def write_file(file_path: str, content: str) -> ToolResult:
    """Write content to file.
    
    Args:
        file_path: Path to the file to write
        content: Content to write
        
    Returns:
        ToolResult indicating success or failure
    """
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult(success=True, content=f"Written to {file_path}")
    except Exception as e:
        return ToolResult(success=False, content="", error=str(e))


def edit_file(file_path: str, old_str: str, new_str: str) -> ToolResult:
    """Edit file by replacing old_str with new_str.
    
    Args:
        file_path: Path to the file to edit
        old_str: String to search for (must be exact match)
        new_str: String to replace with
        
    Returns:
        ToolResult indicating success or failure
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return ToolResult(success=False, content="", error=f"File not found: {file_path}")
        
        content = path.read_text(encoding="utf-8")
        
        if old_str not in content:
            return ToolResult(
                success=False, 
                content="", 
                error=f"String not found in file: {old_str[:50]}..."
            )
        
        new_content = content.replace(old_str, new_str)
        path.write_text(new_content, encoding="utf-8")
        return ToolResult(success=True, content=f"Edited {file_path}")
    except Exception as e:
        return ToolResult(success=False, content="", error=str(e))


def run_bash(command: str, cwd: Optional[str] = None) -> ToolResult:
    """Execute a bash command.
    
    Args:
        command: Command to execute
        cwd: Working directory (optional)
        
    Returns:
        ToolResult with command output
    """
    import subprocess
    import os
    
    try:
        working_dir = cwd if cwd else os.getcwd()
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=working_dir,
            encoding="utf-8",
            errors="replace"
        )
        
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]: {result.stderr}"
        
        return ToolResult(
            success=result.returncode == 0,
            content=output,
            error=None if result.returncode == 0 else f"Exit code: {result.returncode}"
        )
    except Exception as e:
        return ToolResult(success=False, content="", error=str(e))


TOOL_DEFINITIONS = """# Available Tools

You have access to the following tools. When you need to use a tool, output the tool call in one of these formats:

## Tool Call Formats

**XML Format (Recommended):**
```xml
<tool name="read">
  <arg name="file_path">test.txt</arg>
</tool>
```

**JSON Format:**
```json
{"tool": "read", "args": {"file_path": "test.txt"}}
```

## Tool Definitions

### read
Read the contents of a file.
- Usage: `<tool name="read"><arg name="file_path">path/to/file</arg></tool>`
- Args: file_path (string) - Path to the file
- Returns: File content as text
- Tip: Use offset and limit for large files

### write
Write content to a file (creates new or overwrites existing).
- Usage: `<tool name="write"><arg name="file_path">path/to/file</arg><arg name="content">content</arg></tool>`
- Args: 
  - file_path (string) - Path to the file
  - content (string) - Content to write
- Returns: Success message
- WARNING: This will overwrite existing files!

### edit
Edit a file by replacing a specific string.
- Usage: `<tool name="edit"><arg name="file_path">path/to/file</arg><arg name="old_str">old text</arg><arg name="new_str">new text</arg></tool>`
- Args:
  - file_path (string) - Path to the file
  - old_str (string) - Exact string to search for (must match exactly!)
  - new_str (string) - Replacement string
- Returns: Success message
- Note: old_str must match exactly (case-sensitive, including whitespace)
- Tip: For multi-line edits, include the surrounding context

### bash
Execute a shell command.
- Usage: `<tool name="bash"><arg name="command">ls -la</arg></tool>`
- Args:
  - command (string) - Command to execute
  - cwd (string, optional) - Working directory
- Returns: Command output (stdout + stderr)
- Use for: git operations, running tests, listing files, etc.

## Multi-Round Tool Calling (IMPORTANT!)

You can call tools MULTIPLE TIMES in sequence! The system supports iterative tool calling:

1. You analyze the user's request
2. You call tools to gather information
3. You receive the tool results
4. You can call MORE tools if needed
5. Repeat until you have all information
6. Finally, provide your answer WITHOUT tool calls

## Tool Usage Guidelines

1. **Always read first**: Use `read` to understand existing code before making changes
2. **Be precise with edit**: old_str must match exactly - copy from the file content
3. **Multi-step tasks**: Break complex tasks into multiple tool calls
4. **Verify results**: After editing, read the file again to verify changes
5. **Use bash wisely**: For git operations, file listing, running tests
6. **Handle errors**: If a tool fails, analyze the error and try alternative approaches
7. **Destructive operations**: Be extra careful with rm, git reset, etc.

## Example Workflows

### Example 1: Simple Read
User: "What's in README.md?"
Assistant: <tool name="read"><arg name="file_path">README.md</arg></tool>

### Example 2: Multi-Step Analysis
User: "Find all Python files and analyze their imports"
Assistant: 
<tool name="bash"><arg name="command">find . -name "*.py" -type f</arg></tool>

[After receiving results]

Assistant: <tool name="read"><arg name="file_path">src/main.py</arg></tool>

[After receiving results, continue with more reads if needed]

### Example 3: Edit File
User: "Add a new function to utils.py"
Assistant: <tool name="read"><arg name="file_path">utils.py</arg></tool>

[After reading]

Assistant: <tool name="edit">
  <arg name="file_path">utils.py</arg>
  <arg name="old_str">def existing_func():
    pass</arg>
  <arg name="new_str">def existing_func():
    pass

def new_function():
    \"\"\"New utility function.\"\"\"
    return True</arg>
</tool>

[After editing]

Assistant: <tool name="read"><arg name="file_path">utils.py</arg></tool>
"""
