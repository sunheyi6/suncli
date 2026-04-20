"""Core tools for Sun CLI - read, write, edit, bash with sandbox (s02)."""

import os
import subprocess
import locale
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .sandbox import safe_path, SandboxError


@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    content: str
    error: Optional[str] = None


def read_file(file_path: str, limit: int = None, offset: int = None) -> ToolResult:
    """Read file content with sandbox protection.
    
    Args:
        file_path: Path to the file to read
        limit: Maximum lines to read (optional)
        offset: Starting line number (optional)
        
    Returns:
        ToolResult with file content or error
    """
    try:
        path = safe_path(file_path)
        if not path.exists():
            return ToolResult(
                success=False,
                content="",
                error=(
                    f"File not found: {file_path}\n"
                    f"Correction: Use `bash` tool to list directory contents first, "
                    f"then use exact paths from the listing. Do NOT guess paths."
                )
            )
        if path.is_dir():
            # Auto-list directory contents instead of erroring
            try:
                entries = []
                for item in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                    prefix = "[DIR] " if item.is_dir() else "[FILE]"
                    size = item.stat().st_size if item.is_file() else 0
                    entries.append(f"{prefix} {item.name}" + (f" ({size} bytes)" if item.is_file() else ""))
                
                listing = "\n".join(entries) if entries else "(empty directory)"
                return ToolResult(
                    success=True,
                    content=(
                        f"[Directory listing: {file_path}]\n"
                        f"Note: This is a directory, not a file. "
                        f"Below are its contents. Use `read` on a specific file path.\n\n"
                        f"{listing}"
                    )
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    content="",
                    error=(
                        f"Path is a directory and could not be listed: {file_path}.\n"
                        f"Error: {e}\n"
                        f"Correction: Use `bash` tool to list directory contents."
                    )
                )
        
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        
        # Apply offset
        if offset and offset > 0:
            lines = lines[offset:]
            
        # Apply limit
        if limit and limit > 0:
            lines = lines[:limit]
            
        content = "\n".join(lines)
        
        # Truncate if too large (>50KB)
        if len(content) > 50000:
            content = content[:50000] + "\n\n[Content truncated at 50000 chars]"
            
        return ToolResult(success=True, content=content)
    except SandboxError as e:
        return ToolResult(success=False, content="", error=str(e))
    except Exception as e:
        return ToolResult(success=False, content="", error=str(e))


def write_file(file_path: str, content: str) -> ToolResult:
    """Write content to file with sandbox protection.
    
    Args:
        file_path: Path to the file to write
        content: Content to write
        
    Returns:
        ToolResult indicating success or failure
    """
    try:
        path = safe_path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult(success=True, content=f"Written to {file_path}")
    except SandboxError as e:
        return ToolResult(success=False, content="", error=str(e))
    except Exception as e:
        return ToolResult(success=False, content="", error=str(e))


def edit_file(file_path: str, old_str: str, new_str: str) -> ToolResult:
    """Edit file by replacing old_str with new_str (sandbox protected).
    
    Args:
        file_path: Path to the file to edit
        old_str: String to search for (must be exact match)
        new_str: String to replace with
        
    Returns:
        ToolResult indicating success or failure
    """
    try:
        path = safe_path(file_path)
        if not path.exists():
            return ToolResult(
                success=False,
                content="",
                error=(
                    f"File not found: {file_path}\n"
                    f"Correction: Use `bash` tool to list directory contents first, "
                    f"then use exact paths from the listing. Do NOT guess paths."
                )
            )

        content = path.read_text(encoding="utf-8")

        if old_str not in content:
            return ToolResult(
                success=False,
                content="",
                error=(
                    f"String not found in file: {old_str[:50]}...\n"
                    f"Correction: Use `read` tool to get the exact current file content, "
                    f"then copy-paste the exact text (including whitespace) into old_str."
                )
            )
        
        new_content = content.replace(old_str, new_str)
        path.write_text(new_content, encoding="utf-8")
        return ToolResult(success=True, content=f"Edited {file_path}")
    except SandboxError as e:
        return ToolResult(success=False, content="", error=str(e))
    except Exception as e:
        return ToolResult(success=False, content="", error=str(e))


def _decode_process_output(data: bytes) -> str:
    """Decode process output bytes with practical Windows-friendly fallbacks."""
    if not data:
        return ""

    if b"\x00" in data:
        for enc in ("utf-16le", "utf-16", "utf-16be"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue

    preferred = locale.getpreferredencoding(False) or "utf-8"
    encodings = ["utf-8", preferred, "gbk", "cp936"]
    tried = set()
    for enc in encodings:
        norm = enc.lower()
        if norm in tried:
            continue
        tried.add(norm)
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _normalize_windows_command(command: str) -> str:
    """Normalize common cross-shell command patterns for PowerShell."""
    cmd = (command or "").strip()
    if not cmd:
        return cmd

    # PowerShell 5.x doesn't support `&&`.
    if "&&" in cmd:
        cmd = cmd.replace("&&", ";")

    # Common unix listing shorthand generated by models.
    lowered = cmd.lower()
    if lowered in {"ls -la", "ls -al"}:
        return "Get-ChildItem -Force"
    if lowered.startswith("ls -la "):
        return "Get-ChildItem -Force " + cmd[6:].strip()
    if lowered.startswith("ls -al "):
        return "Get-ChildItem -Force " + cmd[6:].strip()

    if lowered == "dir":
        return "Get-ChildItem"
    if lowered.startswith("dir "):
        return "Get-ChildItem " + cmd[4:].strip()
    return cmd


def run_bash(command: str, cwd: Optional[str] = None, timeout: int = 60) -> ToolResult:
    """Execute a bash command with sandbox protection.
    
    Args:
        command: Command to execute
        cwd: Working directory (optional)
        timeout: Timeout in seconds (default: 60)
        
    Returns:
        ToolResult with command output
    """
    try:
        working_dir = cwd
        if cwd:
            # Validate cwd is within workspace
            working_dir = str(safe_path(cwd))
        else:
            working_dir = os.getcwd()
            
        if os.name == "nt":
            normalized = _normalize_windows_command(command)
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", normalized],
                capture_output=True,
                text=False,
                cwd=working_dir,
                timeout=timeout,
            )
        else:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=False,
                cwd=working_dir,
                timeout=timeout,
            )

        stdout_text = _decode_process_output(result.stdout)
        stderr_text = _decode_process_output(result.stderr)
        output = stdout_text
        if stderr_text:
            output += f"\n[stderr]: {stderr_text}"
        
        return ToolResult(
            success=result.returncode == 0,
            content=output,
            error=None if result.returncode == 0 else f"Exit code: {result.returncode}"
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            success=False,
            content="",
            error=(
                f"Command timed out after {timeout} seconds.\n"
                f"Correction: Break the command into smaller steps, "
                f"or increase timeout, or run as a background task."
            )
        )
    except SandboxError as e:
        return ToolResult(
            success=False,
            content="",
            error=f"{str(e)}\nCorrection: Ensure the path is within the allowed workspace."
        )
    except Exception as e:
        return ToolResult(
            success=False,
            content="",
            error=f"{str(e)}\nCorrection: Check the command syntax and path validity."
        )


TOOL_DEFINITIONS = """# Available Tools

You have access to the following tools. When you need to use a tool, output the tool call in JSON format:

## Tool Call Format

**JSON Format (Required):**
```json
{"tool": "read", "args": {"file_path": "test.txt"}}
```

**DO NOT use XML format for tool calls.**

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
