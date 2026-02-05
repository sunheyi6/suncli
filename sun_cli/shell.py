"""Shell command execution for Sun CLI."""

import subprocess
import os
from pathlib import Path

from rich.console import Console


def execute_shell_command(command: str, console: Console) -> int:
    """Execute a shell command and display output.
    
    Args:
        command: The command to execute (without the ! prefix)
        console: Rich console for output
        
    Returns:
        Exit code of the command
    """
    if not command.strip():
        return 0
    
    # Handle cd command specially to change directory
    parts = command.strip().split(maxsplit=1)
    if parts and parts[0].lower() == 'cd':
        return _handle_cd(parts[1] if len(parts) > 1 else "", console)
    
    try:
        # Execute command and capture output as bytes first
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
        )
        
        # Try to decode stdout
        stdout_text = _decode_output(result.stdout)
        stderr_text = _decode_output(result.stderr)
        
        # Print stdout
        if stdout_text:
            print(stdout_text.rstrip())
        
        # Print stderr
        if stderr_text:
            print(f"[Warning] {stderr_text.rstrip()}")
        
        # Show exit code if non-zero
        if result.returncode != 0:
            console.print(f"[red]Exit code: {result.returncode}[/red]")
        
        return result.returncode
        
    except Exception as e:
        console.print(f"[red]Error executing command: {e}[/red]")
        return 1


def _decode_output(data: bytes) -> str:
    """Decode byte output trying multiple encodings."""
    if not data:
        return ""
    
    # Try encodings in order
    encodings = ['utf-8', 'gbk', 'gb2312', 'cp936', 'latin-1']
    
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    
    # Last resort: decode with replace
    return data.decode('utf-8', errors='replace')


def _handle_cd(path: str, console: Console) -> int:
    """Handle cd command to change directory."""
    try:
        if not path:
            # cd without args goes to home directory
            path = str(Path.home())
        
        # Expand user (~) using Path, expand vars using os
        path = os.path.expandvars(path)
        path = Path(path).expanduser()
        
        # Handle "-" to go to previous directory
        if str(path) == "-":
            old_cwd = os.environ.get('OLDPWD', '')
            if old_cwd:
                path = Path(old_cwd)
            else:
                console.print("[red]No previous directory[/red]")
                return 1
        
        # Save current directory before changing
        os.environ['OLDPWD'] = str(Path.cwd())
        
        # Change directory
        target = path.resolve()
        target.mkdir(parents=True, exist_ok=True)
        os.chdir(target)
        
        # Show new directory
        console.print(f"[dim]{Path.cwd()}[/dim]")
        return 0
        
    except Exception as e:
        console.print(f"[red]cd: {e}[/red]")
        return 1


def is_shell_command(user_input: str) -> bool:
    """Check if user input is a shell command (starts with !).
    
    Args:
        user_input: Raw user input
        
    Returns:
        True if it should be executed as shell command
    """
    stripped = user_input.strip()
    return stripped.startswith('!')


def extract_command(user_input: str) -> str:
    """Extract the actual command from user input (remove ! prefix).
    
    Args:
        user_input: Raw user input starting with !
        
    Returns:
        The command without ! prefix
    """
    stripped = user_input.strip()
    if stripped.startswith('!'):
        return stripped[1:].strip()
    return stripped
