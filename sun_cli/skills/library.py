"""Skill library manager for Hermes-style procedural memory."""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..security.scanner import scan_skill_content
from .entry import SkillEntry


class SkillLibrary:
    """Manages procedural skills - reusable task playbooks.
    
    Directory structure:
    .skills/
    ├── INDEX.md              # Lightweight index for system prompt
    ├── devops/
    │   └── flask-k8s-deploy/
    │       └── SKILL.md
    └── software-development/
        └── fix-pytest-fixtures/
            └── SKILL.md
    """
    
    def __init__(self, root: Path = None):
        if root is None:
            root = Path.cwd()
        self.root = Path(root).resolve()
        self.skills_dir = self.root / ".skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        
        self._cache: dict[str, SkillEntry] = {}
        self._ensure_index()
    
    def _ensure_index(self):
        """Create INDEX.md if not exists."""
        index_path = self.skills_dir / "INDEX.md"
        if not index_path.exists():
            index_path.write_text(
                "# Skill Index\n\n"
                "Procedural skills - reusable approaches for recurring task types.\n\n"
                "## Categories\n\n",
                encoding="utf-8"
            )
    
    def create(
        self,
        name: str,
        category: str,
        description: str,
        content: str,
        version: str = "1.0.0"
    ) -> tuple[bool, str]:
        """Create a new skill with security scan. Returns (success, message_or_path)."""
        scan = scan_skill_content(content)
        if not scan.allowed:
            return False, f"Security scan blocked this skill ({scan.reason})"
        
        safe_name = self._sanitize(name)
        safe_category = self._sanitize(category)
        
        skill_dir = self.skills_dir / safe_category / safe_name
        if skill_dir.exists():
            return False, f"Skill '{name}' already exists. Use skill_manage(action='patch') to update."
        
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        skill = SkillEntry(
            name=name,
            description=description,
            category=category,
            version=version,
            content=content,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text(skill.to_frontmatter(), encoding="utf-8")
        
        self._cache[name] = skill
        self._update_index()
        
        return True, str(skill_path)
    
    def load(self, name: str) -> Optional[SkillEntry]:
        """Load a skill by name (with cache)."""
        if name in self._cache:
            return self._cache[name]
        
        for category_dir in self.skills_dir.iterdir():
            if not category_dir.is_dir():
                continue
            skill_path = category_dir / self._sanitize(name) / "SKILL.md"
            if skill_path.exists():
                skill = SkillEntry.from_file(skill_path)
                if skill:
                    self._cache[name] = skill
                    return skill
        
        return None
    
    def load_full(self, name: str) -> Optional[str]:
        """Load raw full content of a skill."""
        skill = self.load(name)
        if skill:
            return skill.to_frontmatter()
        return None
    
    def patch(self, name: str, old_string: str, new_string: str) -> tuple[bool, str]:
        """Targeted find-and-replace within a skill file with security scan."""
        skill = self.load(name)
        if not skill:
            return False, f"Skill '{name}' not found."
        
        skill_path = self._find_skill_path(name)
        if not skill_path:
            return False, f"Skill '{name}' file not found."
        
        current_text = skill_path.read_text(encoding="utf-8")
        new_text, match_count = self._fuzzy_replace(current_text, old_string, new_string)
        
        if match_count == 0:
            return False, (
                f"Could not find the text to replace in skill '{name}'.\n"
                f"Expected:\n{old_string[:200]}..."
            )
        
        scan = scan_skill_content(new_text)
        if not scan.allowed:
            return False, f"Security scan blocked this patch ({scan.reason})"
        
        backup_path = skill_path.with_suffix(".md.bak")
        shutil.copy2(skill_path, backup_path)
        
        skill_path.write_text(new_text, encoding="utf-8")
        
        updated = SkillEntry.parse(new_text)
        if updated:
            updated.updated_at = datetime.now().isoformat()
            self._cache[name] = updated
            self._update_index()
        
        return True, f"Patched skill '{name}' ({match_count} replacement(s)). Backup at {backup_path}"
    
    def delete(self, name: str) -> tuple[bool, str]:
        """Delete a skill."""
        skill_path = self._find_skill_path(name)
        if not skill_path:
            return False, f"Skill '{name}' not found."
        
        skill_dir = skill_path.parent
        shutil.rmtree(skill_dir)
        
        if name in self._cache:
            del self._cache[name]
        self._update_index()
        
        return True, f"Deleted skill '{name}'."
    
    def list_skills(self, include_archived: bool = False) -> list[SkillEntry]:
        """List all skills."""
        skills = []
        for category_dir in self.skills_dir.iterdir():
            if not category_dir.is_dir():
                continue
            for skill_dir in category_dir.iterdir():
                skill_path = skill_dir / "SKILL.md"
                if skill_path.exists():
                    skill = SkillEntry.from_file(skill_path)
                    if skill and (include_archived or not skill.archived):
                        skills.append(skill)
        return skills
    
    def record_usage(self, name: str, success: bool = True):
        """Record that a skill was used."""
        skill = self.load(name)
        if not skill:
            return
        
        skill.record_usage(success)
        
        skill_path = self._find_skill_path(name)
        if skill_path:
            skill_path.write_text(skill.to_frontmatter(), encoding="utf-8")
    
    def build_index_prompt(self) -> str:
        """Build lightweight index for system prompt (only names + descriptions)."""
        skills = self.list_skills(include_archived=False)
        if not skills:
            return ""
        
        by_category: dict[str, list[SkillEntry]] = {}
        for skill in skills:
            by_category.setdefault(skill.category, []).append(skill)
        
        lines = ["<skills>"]
        lines.append("Available skills (use skill_view to load full content):")
        
        for category in sorted(by_category.keys()):
            lines.append(f"  {category}:")
            for skill in sorted(by_category[category], key=lambda s: s.name):
                lines.append(f"    - {skill.name}: {skill.description}")
        
        lines.append("</skills>")
        return "\n".join(lines)
    
    def build_full_prompt(self) -> str:
        """Build full skills prompt (all content) - use sparingly."""
        skills = self.list_skills(include_archived=False)
        if not skills:
            return ""
        
        lines = ["# Loaded Skills"]
        for skill in skills:
            lines.append(f"\n## {skill.name} ({skill.category})")
            lines.append(skill.content)
        
        return "\n".join(lines)
    
    def archive_stale(self, max_age_days: int = 90, min_use_count: int = 3) -> list[str]:
        """Auto-archive skills that are old and rarely used."""
        archived = []
        for skill in self.list_skills(include_archived=False):
            if skill.use_count >= min_use_count:
                continue
            if skill.last_used:
                try:
                    last = datetime.fromisoformat(skill.last_used)
                    age = (datetime.now() - last).days
                    if age > max_age_days:
                        skill.archived = True
                        skill.updated_at = datetime.now().isoformat()
                        skill_path = self._find_skill_path(skill.name)
                        if skill_path:
                            skill_path.write_text(skill.to_frontmatter(), encoding="utf-8")
                            archived.append(skill.name)
                except Exception:
                    pass
        
        if archived:
            self._update_index()
        
        return archived
    
    def get_stats(self) -> dict:
        """Get skill system stats."""
        skills = self.list_skills(include_archived=True)
        active = [s for s in skills if not s.archived]
        archived = [s for s in skills if s.archived]
        
        total_uses = sum(s.use_count for s in skills)
        avg_success = sum(s.success_rate for s in skills) / len(skills) if skills else 0
        
        return {
            "total": len(skills),
            "active": len(active),
            "archived": len(archived),
            "total_uses": total_uses,
            "avg_success_rate": round(avg_success, 2),
        }
    
    def _sanitize(self, name: str) -> str:
        """Sanitize a name for filesystem use."""
        return re.sub(r'[^a-zA-Z0-9_-]', '_', name).lower()
    
    def _find_skill_path(self, name: str) -> Optional[Path]:
        """Find the SKILL.md path for a skill by name."""
        for category_dir in self.skills_dir.iterdir():
            if not category_dir.is_dir():
                continue
            for skill_dir in category_dir.iterdir():
                skill_path = skill_dir / "SKILL.md"
                if skill_path.exists():
                    try:
                        text = skill_path.read_text(encoding="utf-8")
                        match = re.search(r'^name:\s*(.+)$', text, re.MULTILINE)
                        if match and match.group(1).strip() == name:
                            return skill_path
                    except Exception:
                        pass
        return None
    
    def _fuzzy_replace(self, text: str, old: str, new: str) -> tuple[str, int]:
        """Fuzzy find-and-replace that tolerates whitespace differences."""
        if old in text:
            return text.replace(old, new, 1), 1
        
        normalized_text = re.sub(r'\s+', ' ', text)
        normalized_old = re.sub(r'\s+', ' ', old).strip()
        
        if normalized_old in normalized_text:
            idx = normalized_text.find(normalized_old)
            if idx >= 0:
                return text.replace(old.strip(), new, 1), 1
        
        return text, 0
    
    def _update_index(self):
        """Rebuild INDEX.md from all skills."""
        skills = self.list_skills(include_archived=True)
        
        lines = [
            "# Skill Index",
            "",
            "Procedural skills - reusable approaches for recurring task types.",
            "",
            "## Categories",
            "",
        ]
        
        by_category: dict[str, list[SkillEntry]] = {}
        for skill in skills:
            by_category.setdefault(skill.category, []).append(skill)
        
        for category in sorted(by_category.keys()):
            lines.append(f"### {category}")
            for skill in sorted(by_category[category], key=lambda s: s.name):
                status = " [ARCHIVED]" if skill.archived else ""
                lines.append(f"- **{skill.name}** ({skill.version}): {skill.description}{status}")
            lines.append("")
        
        index_path = self.skills_dir / "INDEX.md"
        index_path.write_text("\n".join(lines), encoding="utf-8")


# Global instance
_skill_library: Optional[SkillLibrary] = None


def get_skill_library(root: Path = None) -> SkillLibrary:
    """Get or create global skill library."""
    global _skill_library
    if _skill_library is None:
        _skill_library = SkillLibrary(root)
    return _skill_library
