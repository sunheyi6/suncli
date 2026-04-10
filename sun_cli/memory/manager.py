"""Memory manager - save and load cross-session memories (s09)."""

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


# Memory types - only save info that:
# 1. Has value across sessions
# 2. Cannot be easily re-derived from code
VALID_TYPES = ("user", "feedback", "project", "reference")


@dataclass
class MemoryEntry:
    """A single memory entry."""
    name: str
    type: str
    description: str
    content: str
    created_at: str
    updated_at: str


class MemoryManager:
    """Manages persistent memory across sessions.
    
    Memory directory structure:
    .memory/
    ├── MEMORY.md              # Index
    ├── user/
    │   └── prefer_tabs.md
    ├── feedback/
    │   └── avoid_mock.md
    ├── project/
    │   └── conventions.md
    └── reference/
        └── external_resources.md
    """
    
    def __init__(self, root: Path = None):
        """Initialize memory manager.
        
        Args:
            root: Project root directory
        """
        if root is None:
            root = Path.cwd()
        self.root = Path(root).resolve()
        self.memory_dir = self.root / ".memory"
        
        # Create directories for each type
        for mem_type in VALID_TYPES:
            (self.memory_dir / mem_type).mkdir(parents=True, exist_ok=True)
        
        self._ensure_index()
    
    def _ensure_index(self):
        """Create MEMORY.md index if not exists."""
        index_path = self.memory_dir / "MEMORY.md"
        if not index_path.exists():
            index_path.write_text(
                "# Memory Index\n\n"
                "Cross-session memories for this project.\n\n"
                "## Types\n\n"
                "- **user**: User preferences\n"
                "- **feedback**: Corrections and feedback\n"
                "- **project**: Non-obvious project conventions\n"
                "- **reference**: External resources\n\n"
                "## Entries\n\n",
                encoding="utf-8"
            )
    
    def save(
        self, 
        name: str, 
        mem_type: str, 
        content: str, 
        description: str = ""
    ) -> str:
        """Save a memory entry.
        
        Args:
            name: Entry name (used as filename)
            mem_type: Type of memory (user, feedback, project, reference)
            content: Memory content
            description: Short description
            
        Returns:
            Path to saved file
        """
        if mem_type not in VALID_TYPES:
            raise ValueError(f"Invalid memory type: {mem_type}. Must be one of {VALID_TYPES}")
        
        # Sanitize name
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        
        now = datetime.now().isoformat()
        
        # Build frontmatter + content
        frontmatter = f"""---
name: {name}
type: {mem_type}
description: {description}
created_at: {now}
updated_at: {now}
---

"""
        
        file_path = self.memory_dir / mem_type / f"{safe_name}.md"
        file_path.write_text(frontmatter + content, encoding="utf-8")
        
        # Update index
        self._update_index(name, mem_type, description)
        
        return str(file_path)
    
    def load(self, name: str, mem_type: str = None) -> Optional[MemoryEntry]:
        """Load a specific memory entry.
        
        Args:
            name: Entry name
            mem_type: Optional type to narrow search
            
        Returns:
            MemoryEntry or None
        """
        types_to_search = [mem_type] if mem_type else VALID_TYPES
        
        for t in types_to_search:
            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
            file_path = self.memory_dir / t / f"{safe_name}.md"
            
            if file_path.exists():
                return self._parse_entry(file_path)
        
        return None
    
    def load_all(self, mem_type: str = None) -> list[MemoryEntry]:
        """Load all memory entries.
        
        Args:
            mem_type: Optional type filter
            
        Returns:
            List of memory entries
        """
        entries = []
        types_to_load = [mem_type] if mem_type else VALID_TYPES
        
        for t in types_to_load:
            type_dir = self.memory_dir / t
            if not type_dir.exists():
                continue
                
            for file_path in type_dir.glob("*.md"):
                entry = self._parse_entry(file_path)
                if entry:
                    entries.append(entry)
        
        return entries
    
    def load_for_session(self) -> str:
        """Load all memories formatted for system prompt injection.
        
        Returns:
            Formatted memory section
        """
        entries = self.load_all()
        
        if not entries:
            return ""
        
        lines = ["<memories>"]
        
        for entry in entries:
            lines.append(f'<memory name="{entry.name}" type="{entry.type}">')
            lines.append(f"<description>{entry.description}</description>")
            lines.append(entry.content)
            lines.append("</memory>")
        
        lines.append("</memories>")
        
        return "\n".join(lines)
    
    def list_memories(self) -> list[dict]:
        """List all memory entries with metadata.
        
        Returns:
            List of memory metadata
        """
        entries = []
        
        for mem_type in VALID_TYPES:
            type_dir = self.memory_dir / mem_type
            if not type_dir.exists():
                continue
                
            for file_path in type_dir.glob("*.md"):
                entry = self._parse_entry(file_path)
                if entry:
                    entries.append({
                        "name": entry.name,
                        "type": entry.type,
                        "description": entry.description,
                        "updated_at": entry.updated_at,
                    })
        
        return entries
    
    def delete(self, name: str, mem_type: str = None) -> bool:
        """Delete a memory entry.
        
        Args:
            name: Entry name
            mem_type: Optional type to narrow search
            
        Returns:
            True if deleted, False if not found
        """
        types_to_search = [mem_type] if mem_type else VALID_TYPES
        
        for t in types_to_search:
            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
            file_path = self.memory_dir / t / f"{safe_name}.md"
            
            if file_path.exists():
                file_path.unlink()
                self._rebuild_index()
                return True
        
        return False
    
    def _parse_entry(self, file_path: Path) -> Optional[MemoryEntry]:
        """Parse a memory file into MemoryEntry."""
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Parse frontmatter
            match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
            if not match:
                return None
            
            frontmatter_text = match.group(1)
            body = match.group(2).strip()
            
            # Parse YAML-like frontmatter
            meta = {}
            for line in frontmatter_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    meta[key.strip()] = value.strip()
            
            return MemoryEntry(
                name=meta.get('name', file_path.stem),
                type=meta.get('type', 'unknown'),
                description=meta.get('description', ''),
                content=body,
                created_at=meta.get('created_at', ''),
                updated_at=meta.get('updated_at', ''),
            )
        except Exception:
            return None
    
    def _update_index(self, name: str, mem_type: str, description: str):
        """Add entry to index."""
        index_path = self.memory_dir / "MEMORY.md"
        content = index_path.read_text(encoding="utf-8")
        
        # Check if already exists
        pattern = rf"- \*{name}\*.*?\[{mem_type}\]"
        if re.search(pattern, content):
            # Update existing
            content = re.sub(
                rf"- \*{name}\*.*?\[{mem_type}\].*?\n",
                f"- *{name}*: {description} [{mem_type}]\n",
                content
            )
        else:
            # Add new
            content += f"- *{name}*: {description} [{mem_type}]\n"
        
        index_path.write_text(content, encoding="utf-8")
    
    def _rebuild_index(self):
        """Rebuild index from all memory files."""
        entries = self.list_memories()
        
        lines = [
            "# Memory Index",
            "",
            "Cross-session memories for this project.",
            "",
            "## Types",
            "",
            "- **user**: User preferences",
            "- **feedback**: Corrections and feedback",
            "- **project**: Non-obvious project conventions",
            "- **reference**: External resources",
            "",
            "## Entries",
            "",
        ]
        
        for entry in entries:
            lines.append(f"- *{entry['name']}*: {entry['description']} [{entry['type']}]\n")
        
        index_path = self.memory_dir / "MEMORY.md"
        index_path.write_text("\n".join(lines), encoding="utf-8")


# Global instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get or create global memory manager."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
