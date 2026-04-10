"""Worktree manager - git worktree isolation (s18)."""

import json
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class CloseoutAction(Enum):
    """Worktree closeout actions."""
    KEEP = "keep"
    REMOVE = "remove"


@dataclass
class WorktreeRecord:
    """Record of a worktree."""
    name: str
    path: str
    branch: str
    task_id: Optional[int]
    status: str  # active, kept, removed
    created_at: float
    last_entered_at: Optional[float] = None
    last_command_at: Optional[float] = None
    last_command_preview: str = ""
    closeout_action: Optional[str] = None
    closeout_reason: Optional[str] = None
    closeout_at: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "branch": self.branch,
            "task_id": self.task_id,
            "status": self.status,
            "created_at": self.created_at,
            "last_entered_at": self.last_entered_at,
            "last_command_at": self.last_command_at,
            "last_command_preview": self.last_command_preview,
            "closeout_action": self.closeout_action,
            "closeout_reason": self.closeout_reason,
            "closeout_at": self.closeout_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "WorktreeRecord":
        return cls(
            name=data["name"],
            path=data["path"],
            branch=data["branch"],
            task_id=data.get("task_id"),
            status=data["status"],
            created_at=data["created_at"],
            last_entered_at=data.get("last_entered_at"),
            last_command_at=data.get("last_command_at"),
            last_command_preview=data.get("last_command_preview", ""),
            closeout_action=data.get("closeout_action"),
            closeout_reason=data.get("closeout_reason"),
            closeout_at=data.get("closeout_at"),
        )


class WorktreeManager:
    """Manages git worktrees as isolated execution lanes.
    
    Directory structure:
    .worktrees/
    ├── index.json        # Registry
    ├── events.jsonl      # Lifecycle events
    ├── auth-refactor/    # Worktree directory
    │   └── .git/
    └── ui-login/
        └── .git/
    """
    
    def __init__(self, root: Path = None):
        """Initialize worktree manager.
        
        Args:
            root: Project root
        """
        if root is None:
            root = Path.cwd()
        self.root = Path(root).resolve()
        self.worktrees_dir = self.root / ".worktrees"
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_path = self.worktrees_dir / "index.json"
        self.events_path = self.worktrees_dir / "events.jsonl"
        
        self._worktrees: dict[str, WorktreeRecord] = {}
        self._load_index()
    
    def _load_index(self):
        """Load worktree registry."""
        if self.index_path.exists():
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            for wt_data in data.get("worktrees", []):
                record = WorktreeRecord.from_dict(wt_data)
                self._worktrees[record.name] = record
    
    def _save_index(self):
        """Save worktree registry."""
        data = {
            "worktrees": [wt.to_dict() for wt in self._worktrees.values()]
        }
        self.index_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def _emit_event(self, event_type: str, worktree: str, task_id: Optional[int] = None, extra: dict = None):
        """Write lifecycle event."""
        event = {
            "event": event_type,
            "worktree": worktree,
            "task_id": task_id,
            "ts": time.time(),
            **(extra or {})
        }
        with open(self.events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    
    def create(self, name: str, task_id: int = None) -> WorktreeRecord:
        """Create a git worktree and bind to task.
        
        Args:
            name: Worktree name
            task_id: Optional task ID to bind
            
        Returns:
            WorktreeRecord
        """
        if name in self._worktrees:
            raise ValueError(f"Worktree {name} already exists")
        
        worktree_path = self.worktrees_dir / name
        branch = f"wt/{name}"
        
        # Create git worktree
        try:
            subprocess.run(
                ["git", "worktree", "add", "-b", branch, str(worktree_path), "HEAD"],
                cwd=self.root,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            # Branch might exist, try without -b
            try:
                subprocess.run(
                    ["git", "worktree", "add", str(worktree_path), branch],
                    cwd=self.root,
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                raise RuntimeError(f"Failed to create worktree: {e.stderr.decode()}")
        
        # Create record
        record = WorktreeRecord(
            name=name,
            path=str(worktree_path),
            branch=branch,
            task_id=task_id,
            status="active",
            created_at=time.time(),
        )
        
        self._worktrees[name] = record
        self._save_index()
        self._emit_event("worktree.create", name, task_id)
        
        return record
    
    def enter(self, name: str) -> str:
        """Mark entry into a worktree.
        
        Args:
            name: Worktree name
            
        Returns:
            Path to worktree
        """
        if name not in self._worktrees:
            raise ValueError(f"Worktree {name} not found")
        
        record = self._worktrees[name]
        record.last_entered_at = time.time()
        self._save_index()
        
        self._emit_event("worktree.enter", name, record.task_id)
        
        return record.path
    
    def run_in_worktree(
        self,
        name: str,
        command: str,
        timeout: int = 60,
    ) -> tuple[bool, str]:
        """Run a command in a worktree.
        
        Args:
            name: Worktree name
            command: Command to run
            timeout: Timeout seconds
            
        Returns:
            (success, output)
        """
        if name not in self._worktrees:
            return False, f"Worktree {name} not found"
        
        record = self._worktrees[name]
        
        if record.status not in ("active", "kept"):
            return False, f"Worktree {name} is not active"
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=record.path,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            
            # Update record
            record.last_command_at = time.time()
            record.last_command_preview = (result.stdout + result.stderr)[:200]
            self._save_index()
            
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"
            
            return result.returncode == 0, output
            
        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {timeout} seconds"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def closeout(
        self,
        name: str,
        action: str,
        reason: str = "",
        complete_task: bool = False,
        task_manager=None,
    ) -> WorktreeRecord:
        """Close out a worktree.
        
        Args:
            name: Worktree name
            action: "keep" or "remove"
            reason: Why this action was taken
            complete_task: Also mark bound task as completed
            task_manager: Task manager for completing task
            
        Returns:
            Updated WorktreeRecord
        """
        if name not in self._worktrees:
            raise ValueError(f"Worktree {name} not found")
        
        record = self._worktrees[name]
        
        if action == CloseoutAction.REMOVE.value:
            # Check for uncommitted changes
            try:
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=record.path,
                    capture_output=True,
                    text=True,
                )
                if result.stdout.strip():
                    # Has uncommitted changes
                    return False, "Worktree has uncommitted changes. Commit or stash first."
            except Exception:
                pass
            
            # Remove worktree
            try:
                subprocess.run(
                    ["git", "worktree", "remove", record.path],
                    cwd=self.root,
                    check=True,
                    capture_output=True,
                )
                record.status = "removed"
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to remove worktree: {e}")
        else:
            record.status = "kept"
        
        # Update record
        record.closeout_action = action
        record.closeout_reason = reason
        record.closeout_at = time.time()
        
        self._save_index()
        self._emit_event(
            f"worktree.closeout.{action}",
            name,
            record.task_id,
            {"reason": reason}
        )
        
        # Complete task if requested
        if complete_task and record.task_id and task_manager:
            task_manager.update_status(record.task_id, "completed")
        
        return record
    
    def get(self, name: str) -> Optional[WorktreeRecord]:
        """Get worktree record."""
        return self._worktrees.get(name)
    
    def list_all(self) -> list[WorktreeRecord]:
        """List all worktrees."""
        return list(self._worktrees.values())
    
    def get_for_task(self, task_id: int) -> Optional[WorktreeRecord]:
        """Get worktree bound to task."""
        for wt in self._worktrees.values():
            if wt.task_id == task_id:
                return wt
        return None
    
    def read_events(self, limit: int = 100) -> list[dict]:
        """Read recent events."""
        if not self.events_path.exists():
            return []
        
        events = []
        with open(self.events_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        
        return events[-limit:]
