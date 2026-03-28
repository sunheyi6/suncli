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
            lines.append(
                f"#{task.id} [{task.status}] ({ready}) deps:{deps}  {task.title}"
            )
        return "\n".join(lines)
