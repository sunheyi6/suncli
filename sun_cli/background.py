"""Background task system - run slow commands without blocking (s08/s13)."""

import json
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class RuntimeTask:
    """Record of a background task."""
    id: str
    command: str
    description: str
    status: str  # running, completed, failed, timeout
    started_at: float
    completed_at: Optional[float] = None
    result_preview: str = ""
    output_file: str = ""
    exit_code: Optional[int] = None


@dataclass
class Notification:
    """Notification for completed background task."""
    type: str
    task_id: str
    status: str
    preview: str
    timestamp: float = field(default_factory=time.time)


class BackgroundManager:
    """Manages background task execution.
    
    Key insight: Main loop remains single-threaded. Only the waiting is parallel.
    """
    
    def __init__(self, runtime_dir: Path = None):
        """Initialize background manager.
        
        Args:
            runtime_dir: Directory for storing task records and outputs
        """
        if runtime_dir is None:
            runtime_dir = Path(".runtime-tasks")
        self.runtime_dir = Path(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        
        self.tasks: dict[str, RuntimeTask] = {}
        self._notifications: list[Notification] = []
        self._lock = threading.Lock()
        
        # Load existing tasks
        self._load_tasks()
        
    def run(self, command: str, description: str = "") -> str:
        """Start a background task, return immediately with task_id.
        
        Args:
            command: Command to execute
            description: Human-readable description
            
        Returns:
            task_id for checking status later
        """
        task_id = str(uuid.uuid4())[:8]
        
        task = RuntimeTask(
            id=task_id,
            command=command,
            description=description or command,
            status="running",
            started_at=time.time(),
        )
        
        with self._lock:
            self.tasks[task_id] = task
        
        # Save task record
        self._save_task(task)
        
        # Start background thread
        thread = threading.Thread(
            target=self._execute,
            args=(task_id, command),
            daemon=True,
        )
        thread.start()
        
        return task_id
    
    def check(self, task_id: Optional[str] = None) -> list[RuntimeTask]:
        """Check status of background tasks.
        
        Args:
            task_id: Specific task to check, or None for all
            
        Returns:
            List of task records
        """
        if task_id:
            task = self.tasks.get(task_id)
            return [task] if task else []
        
        return list(self.tasks.values())
    
    def drain_notifications(self) -> list[Notification]:
        """Get and clear pending notifications.
        
        Called before each LLM call to inject completed task results.
        
        Returns:
            List of notifications
        """
        with self._lock:
            notifs = self._notifications.copy()
            self._notifications.clear()
            return notifs
    
    def has_pending_notifications(self) -> bool:
        """Check if there are pending notifications."""
        with self._lock:
            return len(self._notifications) > 0
    
    def _execute(self, task_id: str, command: str):
        """Execute command in background thread."""
        output_path = self.runtime_dir / f"{task_id}.log"
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for background tasks
                encoding="utf-8",
                errors="replace",
            )
            
            # Save full output to file
            output_text = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            output_path.write_text(output_text, encoding="utf-8")
            
            status = "completed" if result.returncode == 0 else "failed"
            preview = (result.stdout + result.stderr)[:500]
            exit_code = result.returncode
            
        except subprocess.TimeoutExpired:
            status = "timeout"
            preview = "Command timed out after 300 seconds"
            output_path.write_text(preview, encoding="utf-8")
            exit_code = -1
            
        except Exception as e:
            status = "failed"
            preview = f"Error: {str(e)}"
            output_path.write_text(preview, encoding="utf-8")
            exit_code = -1
        
        # Update task record
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.status = status
                task.completed_at = time.time()
                task.result_preview = preview
                task.output_file = str(output_path)
                task.exit_code = exit_code
                self._save_task(task)
                
                # Add notification
                self._notifications.append(Notification(
                    type="background_completed",
                    task_id=task_id,
                    status=status,
                    preview=preview,
                ))
    
    def _save_task(self, task: RuntimeTask):
        """Save task record to disk."""
        task_path = self.runtime_dir / f"{task.id}.json"
        task_path.write_text(
            json.dumps({
                "id": task.id,
                "command": task.command,
                "description": task.description,
                "status": task.status,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
                "result_preview": task.result_preview,
                "output_file": task.output_file,
                "exit_code": task.exit_code,
            }, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def _load_tasks(self):
        """Load existing task records from disk."""
        for task_path in self.runtime_dir.glob("*.json"):
            try:
                data = json.loads(task_path.read_text(encoding="utf-8"))
                task = RuntimeTask(
                    id=data["id"],
                    command=data["command"],
                    description=data.get("description", ""),
                    status=data["status"],
                    started_at=data["started_at"],
                    completed_at=data.get("completed_at"),
                    result_preview=data.get("result_preview", ""),
                    output_file=data.get("output_file", ""),
                    exit_code=data.get("exit_code"),
                )
                self.tasks[task.id] = task
            except Exception:
                pass  # Skip corrupted task files
    
    def read_output(self, task_id: str, max_chars: int = 10000) -> str:
        """Read full output from task log file.
        
        Args:
            task_id: Task ID
            max_chars: Maximum characters to read
            
        Returns:
            Output content
        """
        task = self.tasks.get(task_id)
        if not task or not task.output_file:
            return "Output not available"
        
        try:
            path = Path(task.output_file)
            if not path.exists():
                return "Output file not found"
            
            content = path.read_text(encoding="utf-8")
            if len(content) > max_chars:
                content = content[:max_chars] + f"\n\n[Truncated at {max_chars} chars, see file: {path}]"
            return content
        except Exception as e:
            return f"Error reading output: {e}"
    
    def format_for_prompt(self, notifications: list[Notification]) -> str:
        """Format notifications for injection into prompt.
        
        Args:
            notifications: List of notifications
            
        Returns:
            Formatted text for LLM
        """
        if not notifications:
            return ""
        
        lines = ["<background-results>"]
        for n in notifications:
            lines.append(f"[bg:{n.task_id}] {n.status} - {n.preview[:200]}")
        lines.append("</background-results>")
        
        return "\n".join(lines)


# Global instance
_background_manager: Optional[BackgroundManager] = None


def get_background_manager() -> BackgroundManager:
    """Get or create global background manager."""
    global _background_manager
    if _background_manager is None:
        _background_manager = BackgroundManager()
    return _background_manager
