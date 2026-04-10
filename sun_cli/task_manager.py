"""File-based task graph manager for Sun CLI."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


VALID_STATUSES = {"pending", "in_progress", "completed"}


@dataclass
class Task:
    """A persisted task node."""

    id: int
    title: str
    status: str = "pending"
    depends_on: list[int] = field(default_factory=list)
    description: str = ""
    created_at: int = 0
    updated_at: int = 0
    # s15-s17: Team support
    owner: str = ""  # Who claimed this task
    claim_role: str = ""  # Required role to claim
    claimed_at: int = 0
    claim_source: str = ""  # "auto" or "manual"
    # s18: Worktree binding
    worktree: str = ""
    worktree_state: str = ""  # active, kept, removed, unbound

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            id=int(data["id"]),
            title=str(data.get("title", "")),
            status=str(data.get("status", "pending")),
            depends_on=[int(x) for x in data.get("depends_on", [])],
            description=str(data.get("description", "")),
            created_at=int(data.get("created_at", 0)),
            updated_at=int(data.get("updated_at", 0)),
            owner=str(data.get("owner", "")),
            claim_role=str(data.get("claim_role", "")),
            claimed_at=int(data.get("claimed_at", 0)),
            claim_source=str(data.get("claim_source", "")),
            worktree=str(data.get("worktree", "")),
            worktree_state=str(data.get("worktree_state", "")),
        )


class TaskManager:
    """Manages task graph state under .tasks/ in the workspace."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = (root or Path.cwd()).resolve()
        self.tasks_dir = self.root / ".tasks"
        self.index_path = self.tasks_dir / "index.json"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_index()

    def _ensure_index(self) -> None:
        if self.index_path.exists():
            return
        self._save_index({"next_id": 1, "task_ids": []})

    def _load_index(self) -> dict:
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save_index(self, data: dict) -> None:
        self.index_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _task_path(self, task_id: int) -> Path:
        return self.tasks_dir / f"task_{task_id}.json"

    def _save_task(self, task: Task) -> None:
        self._task_path(task.id).write_text(
            json.dumps(task.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_task(self, task_id: int) -> Task:
        path = self._task_path(task_id)
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        return Task.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_tasks(self) -> list[Task]:
        index = self._load_index()
        tasks = []
        for task_id in index.get("task_ids", []):
            try:
                tasks.append(self._load_task(int(task_id)))
            except ValueError:
                continue
        tasks.sort(key=lambda t: t.id)
        return tasks

    def create_task(
        self,
        title: str,
        description: str = "",
        depends_on: Optional[list[int]] = None,
    ) -> Task:
        index = self._load_index()
        task_id = int(index["next_id"])
        deps = [int(d) for d in (depends_on or [])]

        for dep_id in deps:
            self._load_task(dep_id)

        now = int(time.time())
        task = Task(
            id=task_id,
            title=title.strip(),
            description=description.strip(),
            depends_on=deps,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        self._save_task(task)

        index["next_id"] = task_id + 1
        index.setdefault("task_ids", []).append(task_id)
        self._save_index(index)
        return task

    def update_status(self, task_id: int, status: str) -> Task:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        task = self._load_task(task_id)

        # Enforce dependency rule: pending -> in_progress only when deps completed.
        if status == "in_progress":
            for dep_id in task.depends_on:
                dep = self._load_task(dep_id)
                if dep.status != "completed":
                    raise ValueError(f"Task {task_id} blocked by dependency {dep_id}")

        task.status = status
        task.updated_at = int(time.time())
        self._save_task(task)
        return task

    def is_ready(self, task: Task) -> bool:
        if task.status != "pending":
            return False
        for dep_id in task.depends_on:
            dep = self._load_task(dep_id)
            if dep.status != "completed":
                return False
        return True

    def ready_tasks(self) -> list[Task]:
        return [task for task in self.list_tasks() if self.is_ready(task)]

    def create_tasks_from_plan(self, steps: list[str]) -> dict[int, int]:
        """Create dependency-linked tasks from plan steps.

        Returns:
            Mapping from 1-based plan step id -> persisted task id
        """
        mapping: dict[int, int] = {}
        previous_task_id: Optional[int] = None

        for step_id, step in enumerate(steps, start=1):
            deps = [previous_task_id] if previous_task_id is not None else []
            task = self.create_task(title=step, depends_on=deps)
            mapping[step_id] = task.id
            previous_task_id = task.id

        return mapping

    def render_text(self) -> str:
        tasks = self.list_tasks()
        if not tasks:
            return "No tasks yet. Use /plan to generate tasks."

        lines = []
        for task in tasks:
            deps = ",".join(str(d) for d in task.depends_on) if task.depends_on else "-"
            ready = "ready" if self.is_ready(task) else "blocked"
            owner = f" @{task.owner}" if task.owner else ""
            lines.append(
                f"#{task.id} [{task.status}]{owner} ({ready}) deps:{deps}  {task.title}"
            )
        return "\n".join(lines)

    # s17: Auto-claim support
    
    def find_claimable(self, role: str = None) -> list[dict]:
        """Find tasks that can be auto-claimed.
        
        Args:
            role: Optional role filter
            
        Returns:
            List of claimable task dicts
        """
        claimable = []
        for task in self.list_tasks():
            # Must be pending
            if task.status != "pending":
                continue
            # Must not have owner
            if task.owner:
                continue
            # Dependencies must be completed
            if not self.is_ready(task):
                continue
            # Role must match if specified
            if task.claim_role and role and task.claim_role != role:
                continue
                
            claimable.append(task.to_dict())
        
        return claimable
    
    def claim_task(
        self,
        task_id: int,
        owner: str,
        source: str = "manual",
    ) -> bool:
        """Claim a task.
        
        Args:
            task_id: Task to claim
            owner: Who is claiming
            source: "auto" or "manual"
            
        Returns:
            True if claimed successfully
        """
        try:
            task = self._load_task(task_id)
        except ValueError:
            return False
        
        # Check if already claimed
        if task.owner:
            return False
        
        # Check dependencies
        if not self.is_ready(task):
            return False
        
        # Claim
        task.owner = owner
        task.status = "in_progress"
        task.claimed_at = int(time.time())
        task.claim_source = source
        task.updated_at = int(time.time())
        
        self._save_task(task)
        self._emit_claim_event(task_id, owner, source)
        
        return True
    
    def _emit_claim_event(self, task_id: int, owner: str, source: str):
        """Write claim event to log."""
        events_path = self.tasks_dir / "claim_events.jsonl"
        event = {
            "event": "task.claimed",
            "task_id": task_id,
            "owner": owner,
            "source": source,
            "ts": time.time(),
        }
        with open(events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    
    def bind_worktree(self, task_id: int, worktree_name: str):
        """Bind a worktree to a task (s18).
        
        Args:
            task_id: Task ID
            worktree_name: Worktree name
        """
        task = self._load_task(task_id)
        task.worktree = worktree_name
        task.worktree_state = "active"
        if task.status == "pending":
            task.status = "in_progress"
        task.updated_at = int(time.time())
        self._save_task(task)
    
    def unbind_worktree(self, task_id: int):
        """Unbind worktree from task."""
        task = self._load_task(task_id)
        task.worktree = ""
        task.worktree_state = "unbound"
        task.updated_at = int(time.time())
        self._save_task(task)
