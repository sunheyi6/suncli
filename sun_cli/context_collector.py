"""Automatic context collection for Sun CLI.

This module provides intelligent project context gathering, similar to Claude Code's
automatic project awareness. It detects project type, reads key files, and builds
a comprehensive context for the AI.
"""

import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.tree import Tree
from rich.panel import Panel


@dataclass
class ProjectContext:
    """Collected project context."""
    project_type: str = "unknown"
    project_name: str = ""
    root_path: Path = field(default_factory=Path)
    key_files: Dict[str, str] = field(default_factory=dict)
    directory_tree: str = ""
    python_modules: List[str] = field(default_factory=list)
    recent_changes: List[str] = field(default_factory=list)
    git_info: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""


class ContextCollector:
    """Collects and manages project context."""
    
    # Project type detection patterns
    PROJECT_PATTERNS = {
        "python": ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"],
        "nodejs": ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"],
        "rust": ["Cargo.toml", "Cargo.lock"],
        "go": ["go.mod", "go.sum"],
        "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
        "ruby": ["Gemfile", "*.gemspec"],
    }
    
    # Key files to read for each project type
    KEY_FILES = {
        "python": ["pyproject.toml", "setup.py", "requirements.txt", "README.md", "README.rst"],
        "nodejs": ["package.json", "README.md", "tsconfig.json"],
        "rust": ["Cargo.toml", "README.md"],
        "go": ["go.mod", "README.md"],
        "java": ["pom.xml", "build.gradle", "README.md"],
        "ruby": ["Gemfile", "*.gemspec", "README.md"],
        "unknown": ["README.md", "README.rst", "LICENSE", "CHANGELOG.md"],
    }
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self._context_cache: Optional[ProjectContext] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: int = 60  # Cache TTL in seconds
    
    def collect(self, root_path: Optional[Path] = None, force_refresh: bool = False) -> ProjectContext:
        """Collect project context.
        
        Args:
            root_path: Project root path (default: current working directory)
            force_refresh: Force refresh cache
            
        Returns:
            ProjectContext with collected information
        """
        root = root_path or Path.cwd()
        
        # Check cache
        if not force_refresh and self._context_cache is not None:
            import time
            if time.time() - self._cache_timestamp < self._cache_ttl:
                return self._context_cache
        
        context = ProjectContext(root_path=root)
        
        # Detect project type
        context.project_type = self._detect_project_type(root)
        
        # Read key files
        context.key_files = self._read_key_files(root, context.project_type)
        
        # Get project name from key files
        context.project_name = self._extract_project_name(context)
        
        # Build directory tree
        context.directory_tree = self._build_directory_tree(root)
        
        # Find Python modules (if applicable)
        if context.project_type == "python":
            context.python_modules = self._find_python_modules(root)
        
        # Get git info
        context.git_info = self._get_git_info(root)
        
        # Get recent changes
        context.recent_changes = self._get_recent_changes(root)
        
        # Generate summary
        context.summary = self._generate_summary(context)
        
        # Cache result
        self._context_cache = context
        import time
        self._cache_timestamp = time.time()
        
        return context
    
    def _detect_project_type(self, root: Path) -> str:
        """Detect project type based on files present."""
        files = {f.name for f in root.iterdir() if f.is_file()}
        
        for project_type, patterns in self.PROJECT_PATTERNS.items():
            for pattern in patterns:
                if pattern.startswith("*"):
                    # Handle glob patterns
                    if any(f.endswith(pattern[1:]) for f in files):
                        return project_type
                elif pattern in files:
                    return project_type
        
        return "unknown"
    
    def _read_key_files(self, root: Path, project_type: str) -> Dict[str, str]:
        """Read key configuration files."""
        key_files = {}
        files_to_read = self.KEY_FILES.get(project_type, self.KEY_FILES["unknown"])
        
        for pattern in files_to_read:
            if pattern.startswith("*"):
                # Handle glob patterns
                for file_path in root.glob(pattern):
                    if file_path.is_file():
                        try:
                            content = file_path.read_text(encoding="utf-8", errors="ignore")
                            key_files[file_path.name] = content[:2000]  # Limit content size
                        except Exception:
                            pass
            else:
                file_path = root / pattern
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        key_files[pattern] = content[:2000]  # Limit content size
                    except Exception:
                        pass
        
        return key_files
    
    def _extract_project_name(self, context: ProjectContext) -> str:
        """Extract project name from key files."""
        # Try different sources based on project type
        if context.project_type == "python":
            if "pyproject.toml" in context.key_files:
                match = re.search(r'name\s*=\s*"([^"]+)"', context.key_files["pyproject.toml"])
                if match:
                    return match.group(1)
        
        elif context.project_type == "nodejs":
            if "package.json" in context.key_files:
                import json
                try:
                    data = json.loads(context.key_files["package.json"])
                    return data.get("name", "")
                except Exception:
                    pass
        
        elif context.project_type == "rust":
            if "Cargo.toml" in context.key_files:
                match = re.search(r'^name\s*=\s*"([^"]+)"', context.key_files["Cargo.toml"], re.MULTILINE)
                if match:
                    return match.group(1)
        
        # Fallback to directory name
        return context.root_path.name
    
    def _build_directory_tree(self, root: Path, max_depth: int = 3) -> str:
        """Build a simplified directory tree."""
        lines = [f"📁 {root.name}/"]
        
        def add_tree(path: Path, prefix: str = "", depth: int = 0):
            if depth >= max_depth:
                return
            
            try:
                entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            except PermissionError:
                return
            
            # Filter out common ignore patterns
            ignore_patterns = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv", "*.pyc"}
            entries = [e for e in entries if not any(
                e.match(pattern) or e.name == pattern for pattern in ignore_patterns
            )]
            
            # Limit entries per directory
            entries = entries[:20]
            
            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "
                
                if entry.is_dir():
                    lines.append(f"{prefix}{connector}📁 {entry.name}/")
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    add_tree(entry, new_prefix, depth + 1)
                else:
                    icon = self._get_file_icon(entry.name)
                    lines.append(f"{prefix}{connector}{icon} {entry.name}")
        
        add_tree(root, "")
        return "\n".join(lines)
    
    def _get_file_icon(self, filename: str) -> str:
        """Get appropriate icon for file type."""
        icons = {
            ".py": "🐍",
            ".js": "📜",
            ".ts": "📘",
            ".json": "📋",
            ".md": "📝",
            ".toml": "⚙️",
            ".yaml": "⚙️",
            ".yml": "⚙️",
            ".txt": "📄",
            ".rs": "🦀",
            ".go": "🔵",
            ".java": "☕",
        }
        ext = Path(filename).suffix
        return icons.get(ext, "📄")
    
    def _find_python_modules(self, root: Path) -> List[str]:
        """Find Python module structure."""
        modules = []
        
        # Look for Python packages (directories with __init__.py)
        for init_file in root.rglob("__init__.py"):
            if init_file.parent != root:
                rel_path = init_file.parent.relative_to(root)
                module_name = str(rel_path).replace(os.sep, ".")
                modules.append(module_name)
        
        return sorted(set(modules))[:10]  # Limit to 10 modules
    
    def _get_git_info(self, root: Path) -> Dict[str, Any]:
        """Get git repository information."""
        import subprocess
        
        git_info = {"is_repo": False, "branch": "", "remote": ""}
        
        try:
            # Check if git repo
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=root,
                capture_output=True,
                text=True
            )
            git_info["is_repo"] = result.returncode == 0
            
            if git_info["is_repo"]:
                # Get current branch
                result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=root,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    git_info["branch"] = result.stdout.strip()
                
                # Get remote URL
                result = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=root,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    git_info["remote"] = result.stdout.strip()
        
        except Exception:
            pass
        
        return git_info
    
    def _get_recent_changes(self, root: Path, count: int = 5) -> List[str]:
        """Get recent git changes."""
        import subprocess
        
        changes = []
        
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-n", str(count)],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore"
            )
            if result.returncode == 0:
                changes = result.stdout.strip().split("\n")
        except Exception:
            pass
        
        return changes
    
    def _generate_summary(self, context: ProjectContext) -> str:
        """Generate a human-readable summary."""
        parts = []
        
        # Project info
        parts.append(f"Project: {context.project_name}")
        parts.append(f"Type: {context.project_type}")
        parts.append(f"Path: {context.root_path}")
        
        # Git info
        if context.git_info.get("is_repo"):
            parts.append(f"Git Branch: {context.git_info.get('branch', 'unknown')}")
        
        # Key files summary
        if context.key_files:
            parts.append(f"\nKey Files: {', '.join(context.key_files.keys())}")
        
        # Python modules
        if context.python_modules:
            parts.append(f"\nPython Modules: {', '.join(context.python_modules[:5])}")
        
        # Recent changes
        if context.recent_changes:
            parts.append(f"\nRecent Commits:")
            for change in context.recent_changes[:3]:
                parts.append(f"  - {change}")
        
        return "\n".join(parts)
    
    def build_system_context(self, root_path: Optional[Path] = None) -> str:
        """Build a system context string for the AI.
        
        This creates a comprehensive context that can be added to the system prompt.
        
        Returns:
            Formatted context string
        """
        context = self.collect(root_path)
        
        lines = [
            "# 项目上下文",
            "",
            f"你正在一个 {context.project_type} 项目中工作: {context.project_name}",
            f"项目根目录: {context.root_path}",
            "",
        ]
        
        # Directory structure
        lines.extend([
            "## 目录结构",
            "```",
            context.directory_tree,
            "```",
            "",
        ])
        
        # Key files
        if context.key_files:
            lines.append("## 关键配置文件")
            for filename, content in context.key_files.items():
                lines.extend([
                    f"\n### {filename}",
                    "```",
                    content[:1000],  # Limit content
                    "```" if len(content) <= 1000 else "... (已截断)",
                ])
            lines.append("")
        
        # Python modules
        if context.python_modules:
            lines.extend([
                "## Python 模块",
                ", ".join(context.python_modules),
                "",
            ])
        
        # Git info
        if context.git_info.get("is_repo"):
            lines.extend([
                "## Git 信息",
                f"分支: {context.git_info.get('branch', 'unknown')}",
            ])
            if context.recent_changes:
                lines.extend([
                    "",
                    "最近提交:",
                ])
                for change in context.recent_changes[:5]:
                    lines.append(f"  - {change}")
            lines.append("")
        
        lines.extend([
            "## 工作指南",
            "- 修改前请先查看相关文件",
            "- 使用目录结构了解项目布局",
            "- 遵循现有的代码风格和约定",
            "",
        ])
        
        return "\n".join(lines)
    
    def display_context(self, root_path: Optional[Path] = None) -> None:
        """Display the collected context in the console."""
        context = self.collect(root_path)
        
        self.console.print(Panel(
            context.summary,
            title=f"[bold blue]📂 项目信息: {context.project_name}[/bold blue]",
            border_style="blue"
        ))
        
        self.console.print("\n[dim]目录结构:[/dim]")
        self.console.print(context.directory_tree)


# Global instance
_context_collector: Optional[ContextCollector] = None


def get_context_collector(console: Optional[Console] = None) -> ContextCollector:
    """Get or create global context collector."""
    global _context_collector
    if _context_collector is None:
        _context_collector = ContextCollector(console)
    return _context_collector


def collect_context(root_path: Optional[Path] = None, console: Optional[Console] = None) -> ProjectContext:
    """Convenience function to collect project context."""
    return get_context_collector(console).collect(root_path)


def build_system_context(root_path: Optional[Path] = None, console: Optional[Console] = None) -> str:
    """Convenience function to build system context string."""
    return get_context_collector(console).build_system_context(root_path)
