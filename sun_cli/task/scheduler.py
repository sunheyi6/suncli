"""Task scheduler - cron-like scheduling (s14)."""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from croniter import croniter
    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False
    croniter = None


@dataclass
class ScheduleRecord:
    """A scheduled task."""
    schedule_id: str
    name: str
    cron: str
    prompt: str
    recurring: bool
    created_at: float
    last_fired_at: Optional[float] = None
    enabled: bool = True
    
    def to_dict(self) -> dict:
        return {
            "schedule_id": self.schedule_id,
            "name": self.name,
            "cron": self.cron,
            "prompt": self.prompt,
            "recurring": self.recurring,
            "created_at": self.created_at,
            "last_fired_at": self.last_fired_at,
            "enabled": self.enabled,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ScheduleRecord":
        return cls(
            schedule_id=data["schedule_id"],
            name=data["name"],
            cron=data["cron"],
            prompt=data["prompt"],
            recurring=data["recurring"],
            created_at=data["created_at"],
            last_fired_at=data.get("last_fired_at"),
            enabled=data.get("enabled", True),
        )
    
    def should_fire(self, now: datetime) -> bool:
        """Check if schedule should fire now."""
        if not self.enabled:
            return False
        
        if not HAS_CRONITER:
            # Fallback: simple minute-based check for common patterns
            return self._simple_cron_check(now)
        
        try:
            itr = croniter(self.cron, now)
            next_fire = itr.get_next(datetime)
            
            # If next fire is within 60 seconds of now, fire
            diff = abs((next_fire - now).total_seconds())
            return diff < 60
        except Exception:
            return False
    
    def _simple_cron_check(self, now: datetime) -> bool:
        """Simple cron check without croniter library."""
        parts = self.cron.split()
        if len(parts) != 5:
            return False
        
        minute, hour, day, month, weekday = parts
        
        # Check minute (*/n or exact)
        if minute.startswith("*/"):
            try:
                interval = int(minute[2:])
                if now.minute % interval != 0:
                    return False
            except ValueError:
                return False
        elif minute != "*":
            try:
                if now.minute != int(minute):
                    return False
            except ValueError:
                return False
        
        # Check hour
        if hour != "*":
            try:
                if now.hour != int(hour):
                    return False
            except ValueError:
                return False
        
        return True


class Scheduler:
    """Cron-like scheduler for agent tasks.
    
    Stores schedules in .tasks/schedules.json
    """
    
    def __init__(self, tasks_dir: Path = None):
        """Initialize scheduler.
        
        Args:
            tasks_dir: Tasks directory
        """
        if tasks_dir is None:
            tasks_dir = Path(".tasks")
        self.tasks_dir = Path(tasks_dir)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        
        self.schedules_path = self.tasks_dir / "schedules.json"
        self._schedules: dict[str, ScheduleRecord] = {}
        self._load_schedules()
    
    def create(
        self,
        cron: str,
        prompt: str,
        name: str = None,
        recurring: bool = True,
    ) -> str:
        """Create a new schedule.
        
        Args:
            cron: Cron expression (e.g., "0 9 * * 1" for weekly Monday 9am)
            prompt: The prompt/task to execute
            name: Schedule name
            recurring: Whether this repeats
            
        Returns:
            schedule_id
        """
        import uuid
        schedule_id = f"sched_{uuid.uuid4().hex[:8]}"
        
        record = ScheduleRecord(
            schedule_id=schedule_id,
            name=name or f"Schedule {schedule_id}",
            cron=cron,
            prompt=prompt,
            recurring=recurring,
            created_at=time.time(),
        )
        
        self._schedules[schedule_id] = record
        self._save_schedules()
        
        return schedule_id
    
    def remove(self, schedule_id: str) -> bool:
        """Remove a schedule.
        
        Args:
            schedule_id: Schedule ID
            
        Returns:
            True if removed
        """
        if schedule_id in self._schedules:
            del self._schedules[schedule_id]
            self._save_schedules()
            return True
        return False
    
    def list_all(self) -> list[ScheduleRecord]:
        """List all schedules."""
        return list(self._schedules.values())
    
    def get(self, schedule_id: str) -> Optional[ScheduleRecord]:
        """Get a schedule."""
        return self._schedules.get(schedule_id)
    
    def check_and_fire(self) -> list[dict]:
        """Check schedules and return those that should fire.
        
        Returns:
            List of notifications for fired schedules
        """
        now = datetime.now()
        notifications = []
        
        for schedule in self._schedules.values():
            if schedule.should_fire(now):
                # Fire this schedule
                notifications.append({
                    "type": "scheduled_prompt",
                    "schedule_id": schedule.schedule_id,
                    "name": schedule.name,
                    "prompt": schedule.prompt,
                    "timestamp": time.time(),
                })
                
                # Update last_fired
                schedule.last_fired_at = time.time()
                
                # If not recurring, disable
                if not schedule.recurring:
                    schedule.enabled = False
        
        if notifications:
            self._save_schedules()
        
        return notifications
    
    def format_for_prompt(self, notifications: list[dict]) -> str:
        """Format schedule notifications for LLM.
        
        Args:
            notifications: List of schedule notifications
            
        Returns:
            Formatted text
        """
        if not notifications:
            return ""
        
        lines = ["<scheduled-tasks>"]
        for n in notifications:
            lines.append(f"[scheduled:{n['schedule_id']}] {n['name']}: {n['prompt'][:100]}")
        lines.append("</scheduled-tasks>")
        
        return "\n".join(lines)
    
    def _save_schedules(self):
        """Persist schedules to disk."""
        data = {
            "schedules": [s.to_dict() for s in self._schedules.values()]
        }
        self.schedules_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def _load_schedules(self):
        """Load schedules from disk."""
        if not self.schedules_path.exists():
            return
        
        try:
            data = json.loads(self.schedules_path.read_text(encoding="utf-8"))
            for s_data in data.get("schedules", []):
                record = ScheduleRecord.from_dict(s_data)
                self._schedules[record.schedule_id] = record
        except (json.JSONDecodeError, KeyError):
            pass


# Global instance
_scheduler: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    """Get or create global scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler
