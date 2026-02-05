"""Git helper for Sun CLI - Smart commit workflow."""

import subprocess
import re
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table


@dataclass
class GitStatus:
    """Git repository status."""
    branch: str = ""
    ahead: int = 0
    behind: int = 0
    staged: List[str] = None
    unstaged: List[str] = None
    untracked: List[str] = None
    has_conflicts: bool = False
    conflicted_files: List[str] = None
    
    def __post_init__(self):
        if self.staged is None:
            self.staged = []
        if self.unstaged is None:
            self.unstaged = []
        if self.untracked is None:
            self.untracked = []
        if self.conflicted_files is None:
            self.conflicted_files = []
    
    @property
    def is_clean(self) -> bool:
        """Check if working tree is clean."""
        return not (self.staged or self.unstaged or self.untracked or self.conflicted_files)
    
    @property
    def has_changes(self) -> bool:
        """Check if there are any changes to commit."""
        return bool(self.staged or self.unstaged or self.untracked)


@dataclass
class ConflictInfo:
    """Information about a merge conflict."""
    file: str
    ours_content: str
    theirs_content: str
    base_content: Optional[str] = None


class GitHelper:
    """Helper class for Git operations."""
    
    def __init__(self, console: Console):
        self.console = console
        self.repo_root = self._find_repo_root()
    
    def _find_repo_root(self) -> Optional[Path]:
        """Find git repository root."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            if result.returncode == 0:
                return Path(result.stdout.strip())
        except Exception:
            pass
        return None
    
    def is_git_repo(self) -> bool:
        """Check if current directory is in a git repository."""
        return self.repo_root is not None
    
    def get_status(self) -> GitStatus:
        """Get detailed git status."""
        status = GitStatus()
        
        # Get branch and ahead/behind info
        try:
            # Branch name
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            if result.returncode == 0:
                status.branch = result.stdout.strip()
            
            # Ahead/behind
            result = subprocess.run(
                ["git", "rev-list", "--left-right", "--count", f"HEAD...@{u}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split()
                if len(parts) == 2:
                    status.behind = int(parts[1])  # commits we are behind
                    status.ahead = int(parts[0])   # commits we are ahead
        except Exception:
            pass
        
        # Get detailed status
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if len(line) < 3:
                        continue
                    
                    index_status = line[0]
                    worktree_status = line[1]
                    file_path = line[3:]
                    
                    # Check for conflicts
                    if index_status in "UD" or worktree_status in "UD" or index_status == worktree_status == "A":
                        status.has_conflicts = True
                        status.conflicted_files.append(file_path)
                    elif index_status == "M" or index_status == "A" or index_status == "D" or index_status == "R":
                        status.staged.append(file_path)
                    elif worktree_status == "M" or worktree_status == "D":
                        status.unstaged.append(file_path)
                    elif index_status == "?":
                        status.untracked.append(file_path)
        except Exception:
            pass
        
        return status
    
    def get_staged_diff(self) -> str:
        """Get diff of staged changes."""
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--no-color"],
                capture_output=True,
                encoding="utf-8",
                errors="replace"
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception:
            return ""
    
    def get_recent_commits(self, n: int = 3) -> List[str]:
        """Get recent commit messages for context."""
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-n", str(n)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            if result.returncode == 0:
                return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except Exception:
            pass
        return []
    
    def pull(self, rebase: bool = True) -> Tuple[bool, str]:
        """Pull from remote. Returns (success, message)."""
        cmd = ["git", "pull"]
        if rebase:
            cmd.append("--rebase")
        
        self.console.print("[dim]正在拉取远程代码...[/dim]")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        
        if result.returncode == 0:
            return True, result.stdout or "Already up to date."
        else:
            # Check if it's a conflict
            if "CONFLICT" in result.stderr or "conflict" in result.stderr.lower():
                return False, "conflict"
            return False, result.stderr
    
    def push(self) -> Tuple[bool, str]:
        """Push to remote. Returns (success, message)."""
        self.console.print("[dim]正在推送到远程...[/dim]")
        
        result = subprocess.run(
            ["git", "push"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        
        if result.returncode == 0:
            return True, result.stdout or "Push successful."
        else:
            return False, result.stderr
    
    def stage_all(self) -> bool:
        """Stage all changes."""
        result = subprocess.run(
            ["git", "add", "-A"],
            capture_output=True
        )
        return result.returncode == 0
    
    def commit(self, message: str) -> bool:
        """Create a commit."""
        result = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return result.returncode == 0
    
    def get_conflict_details(self, file_path: str) -> Optional[ConflictInfo]:
        """Get details of a conflicted file."""
        try:
            file_full_path = self.repo_root / file_path
            if not file_full_path.exists():
                return None
            
            content = file_full_path.read_text(encoding="utf-8", errors="replace")
            
            # Parse conflict markers
            ours_match = re.search(r"<<<<<<< HEAD\n(.*?)=======", content, re.DOTALL)
            theirs_match = re.search(r"=======(.*?)>>>>>>> ", content, re.DOTALL)
            
            if ours_match and theirs_match:
                return ConflictInfo(
                    file=file_path,
                    ours_content=ours_match.group(1).strip(),
                    theirs_content=theirs_match.group(1).strip()
                )
        except Exception:
            pass
        return None
    
    def resolve_conflict(self, file_path: str, resolution: str, content: str) -> bool:
        """Resolve a conflict by writing resolved content."""
        try:
            file_full_path = self.repo_root / file_path
            file_full_path.write_text(content, encoding="utf-8")
            
            # Stage the resolved file
            subprocess.run(
                ["git", "add", file_path],
                capture_output=True
            )
            return True
        except Exception:
            return False
    
    def abort_rebase(self) -> bool:
        """Abort current rebase."""
        result = subprocess.run(
            ["git", "rebase", "--abort"],
            capture_output=True
        )
        return result.returncode == 0
    
    def continue_rebase(self) -> bool:
        """Continue rebase after resolving conflicts."""
        result = subprocess.run(
            ["git", "rebase", "--continue"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return result.returncode == 0


def format_diff_for_ai(diff: str, max_lines: int = 100) -> str:
    """Format diff for AI consumption, limiting size."""
    lines = diff.splitlines()
    
    if len(lines) > max_lines:
        # Keep first 50 and last 50 lines
        truncated = lines[:50] + ["... (truncated) ..."] + lines[-50:]
        return "\n".join(truncated)
    
    return diff


def detect_commit_intent(user_input: str) -> bool:
    """Detect if user wants to commit/push."""
    commit_keywords = [
        "提交", "commit", "push", "推送",
        "保存代码", "上传代码", "提交代码",
        "commit changes", "push changes",
        "save and push", "commit and push",
    ]
    
    user_lower = user_input.lower()
    return any(keyword in user_lower for keyword in commit_keywords)
