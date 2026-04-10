"""Path sandbox for tool execution - prevents workspace escape (s02)."""

import os
from pathlib import Path
from typing import Union


class SandboxError(Exception):
    """Raised when a path tries to escape the workspace."""
    pass


class PathSandbox:
    """Ensures all file operations stay within workspace boundaries."""
    
    def __init__(self, workdir: Union[str, Path] = None):
        """Initialize sandbox with workspace root.
        
        Args:
            workdir: Workspace root directory. Defaults to current working directory.
        """
        if workdir is None:
            workdir = os.getcwd()
        self.workdir = Path(workdir).resolve()
        
    def safe_path(self, p: Union[str, Path]) -> Path:
        """Convert path to absolute path within workspace.
        
        Args:
            p: Input path (relative or absolute)
            
        Returns:
            Resolved Path object within workspace
            
        Raises:
            SandboxError: If path escapes workspace
        """
        if isinstance(p, str):
            p = Path(p)
            
        # Handle absolute paths - check if they're within workspace
        if p.is_absolute():
            resolved = p.resolve()
        else:
            # Relative paths are relative to workdir
            resolved = (self.workdir / p).resolve()
            
        # Check if path is within workspace
        try:
            resolved.relative_to(self.workdir)
        except ValueError:
            raise SandboxError(
                f"Path escapes workspace: {p}\n"
                f"Resolved to: {resolved}\n"
                f"Workspace: {self.workdir}"
            )
            
        return resolved
        
    def is_safe(self, p: Union[str, Path]) -> bool:
        """Check if path is safe without raising exception.
        
        Args:
            p: Path to check
            
        Returns:
            True if path is within workspace
        """
        try:
            self.safe_path(p)
            return True
        except SandboxError:
            return False


# Global sandbox instance
_default_sandbox: PathSandbox | None = None


def get_sandbox(workdir: Union[str, Path] = None) -> PathSandbox:
    """Get or create default sandbox instance."""
    global _default_sandbox
    if _default_sandbox is None or workdir is not None:
        return PathSandbox(workdir)
    return _default_sandbox


def safe_path(p: Union[str, Path], workdir: Union[str, Path] = None) -> Path:
    """Convenience function to get safe path."""
    return get_sandbox(workdir).safe_path(p)
