"""Skill data model for Hermes-style procedural memory (Self-Improving Phase 1)."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class SkillEntry:
    """A procedural skill - reusable approach for recurring task types."""
    
    name: str
    description: str
    category: str
    version: str = "1.0.0"
    content: str = ""
    
    # Lifecycle metadata (Phase 4)
    last_used: Optional[str] = None
    use_count: int = 0
    success_rate: float = 1.0  # 0.0 - 1.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    archived: bool = False
    
    @property
    def steps(self) -> str:
        """Extract Steps section from content."""
        return self._extract_section("Steps")
    
    @property
    def pitfalls(self) -> str:
        """Extract Pitfalls section from content."""
        return self._extract_section("Pitfalls")
    
    @property
    def when_to_use(self) -> str:
        """Extract When to use section from content."""
        return self._extract_section("When to use")
    
    def _extract_section(self, section_name: str) -> str:
        """Extract a markdown section by heading."""
        pattern = rf"##\s*{re.escape(section_name)}\s*\n(.*?)(?=\n##\s|\Z)"
        match = re.search(pattern, self.content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""
    
    def to_frontmatter(self) -> str:
        """Serialize to YAML frontmatter + markdown body."""
        lines = ["---"]
        lines.append(f"name: {self.name}")
        lines.append(f"description: {self.description}")
        lines.append(f"version: {self.version}")
        lines.append(f"category: {self.category}")
        if self.last_used:
            lines.append(f"last_used: {self.last_used}")
        lines.append(f"use_count: {self.use_count}")
        lines.append(f"success_rate: {self.success_rate}")
        if self.created_at:
            lines.append(f"created_at: {self.created_at}")
        if self.updated_at:
            lines.append(f"updated_at: {self.updated_at}")
        if self.archived:
            lines.append(f"archived: true")
        lines.append("---")
        lines.append("")
        lines.append(self.content)
        return "\n".join(lines)
    
    def to_index_entry(self) -> str:
        """One-line index entry for lightweight system prompt."""
        status = " [ARCHIVED]" if self.archived else ""
        return f"- {self.name}: {self.description} [{self.category}]{status}"
    
    def record_usage(self, success: bool = True):
        """Update lifecycle stats after usage."""
        self.use_count += 1
        self.last_used = datetime.now().isoformat()
        # Bayesian-ish success rate update
        self.success_rate = (self.success_rate * (self.use_count - 1) + (1.0 if success else 0.0)) / self.use_count
        self.updated_at = self.last_used
    
    @classmethod
    def from_file(cls, path: Path) -> Optional["SkillEntry"]:
        """Parse a SKILL.md file into SkillEntry."""
        try:
            content = path.read_text(encoding="utf-8")
            return cls.parse(content)
        except Exception:
            return None
    
    @classmethod
    def parse(cls, text: str) -> Optional["SkillEntry"]:
        """Parse YAML frontmatter + markdown body."""
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', text, re.DOTALL)
        if not match:
            return None
        
        frontmatter = match.group(1)
        body = match.group(2).strip()
        
        meta = {}
        for line in frontmatter.split('\n'):
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                if key in ("use_count",):
                    meta[key] = int(value) if value else 0
                elif key in ("success_rate",):
                    meta[key] = float(value) if value else 1.0
                elif key in ("archived",):
                    meta[key] = value.lower() in ("true", "yes", "1")
                else:
                    meta[key] = value
        
        return cls(
            name=meta.get("name", "unnamed"),
            description=meta.get("description", ""),
            category=meta.get("category", "general"),
            version=meta.get("version", "1.0.0"),
            content=body,
            last_used=meta.get("last_used"),
            use_count=meta.get("use_count", 0),
            success_rate=meta.get("success_rate", 1.0),
            created_at=meta.get("created_at"),
            updated_at=meta.get("updated_at"),
            archived=meta.get("archived", False),
        )
