"""Interactive conflict resolver for Sun CLI."""

import re
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Prompt, Confirm
from rich.layout import Layout
from rich.live import Live

from .git_helper import GitHelper, ConflictInfo


class ConflictResolver:
    """Interactive UI for resolving merge conflicts."""
    
    def __init__(self, console: Console, git_helper: GitHelper):
        self.console = console
        self.git = git_helper
    
    def resolve_all(self, conflicted_files: list[str]) -> bool:
        """Resolve all conflicts interactively."""
        self.console.print(Panel(
            f"[bold yellow]检测到 {len(conflicted_files)} 个冲突文件[/bold yellow]\n"
            "需要手动解决冲突后才能继续提交。",
            title="Git 冲突",
            border_style="yellow"
        ))
        
        for file_path in conflicted_files:
            if not self._resolve_single(file_path):
                self.console.print(f"[red]跳过 {file_path}，将在稍后处理[/red]")
        
        # Check if all conflicts are resolved
        status = self.git.get_status()
        if status.conflicted_files:
            self.console.print(f"\n[yellow]仍有 {len(status.conflicted_files)} 个未解决的冲突[/yellow]")
            return False
        
        return True
    
    def _resolve_single(self, file_path: str) -> bool:
        """Resolve a single conflicted file."""
        conflict = self.git.get_conflict_details(file_path)
        if not conflict:
            self.console.print(f"[red]无法读取冲突详情: {file_path}[/red]")
            return False
        
        self.console.print(f"\n[bold cyan]正在处理: {file_path}[/bold cyan]")
        
        # Show conflict overview
        self._show_conflict_overview(conflict)
        
        # Get resolution choice
        while True:
            choice = Prompt.ask(
                "选择解决方案",
                choices=["1", "2", "3", "e", "s", "a"],
                default="1"
            )
            
            if choice == "1":
                # Keep ours (HEAD)
                resolved_content = self._extract_ours(file_path)
                if self.git.resolve_conflict(file_path, "ours", resolved_content):
                    self.console.print("[green]已保留当前分支的修改[/green]")
                    return True
                    
            elif choice == "2":
                # Keep theirs (incoming)
                resolved_content = self._extract_theirs(file_path)
                if self.git.resolve_conflict(file_path, "theirs", resolved_content):
                    self.console.print("[green]已保留远程分支的修改[/green]")
                    return True
                    
            elif choice == "3":
                # Keep both
                resolved_content = self._extract_both(file_path)
                if self.git.resolve_conflict(file_path, "both", resolved_content):
                    self.console.print("[green]已合并双方的修改[/green]")
                    return True
                    
            elif choice == "e":
                # Manual edit - show editor command
                self.console.print(f"\n[dim]请手动编辑文件: {self.git.repo_root / file_path}[/dim]")
                self.console.print("[dim]解决冲突后按 Enter 继续...[/dim]")
                input()
                # Re-stage the file
                self.git.stage_all()
                return True
                
            elif choice == "s":
                # Skip this file
                return False
                
            elif choice == "a":
                # Abort rebase
                if Confirm.ask("确定要中止 rebase 吗？未保存的更改可能会丢失"):
                    if self.git.abort_rebase():
                        self.console.print("[yellow]已中止 rebase[/yellow]")
                    return False
    
    def _show_conflict_overview(self, conflict: ConflictInfo):
        """Display conflict details."""
        # Show OURS (HEAD)
        self.console.print("\n[bold green]选项 1: 保留当前分支 (HEAD/ours)[/bold green]")
        self._show_code_snippet(conflict.ours_content, "green")
        
        # Show THEIRS
        self.console.print("\n[bold blue]选项 2: 保留远程分支 (incoming/theirs)[/bold blue]")
        self._show_code_snippet(conflict.theirs_content, "blue")
        
        # Show options
        self.console.print("\n[bold]选项:[/bold]")
        self.console.print("  [green]1[/green] - 保留当前分支的修改 (ours)")
        self.console.print("  [blue]2[/blue] - 保留远程分支的修改 (theirs)")
        self.console.print("  [yellow]3[/yellow] - 保留双方修改 (合并)")
        self.console.print("  [dim]e[/dim] - 手动编辑文件")
        self.console.print("  [dim]s[/dim] - 跳过此文件")
        self.console.print("  [red]a[/red] - 中止 rebase")
    
    def _show_code_snippet(self, content: str, style: str):
        """Show a code snippet with syntax highlighting."""
        # Limit display length
        max_lines = 20
        lines = content.splitlines()
        
        if len(lines) > max_lines:
            display = "\n".join(lines[:max_lines]) + "\n... (更多内容) ..."
        else:
            display = content
        
        # Try to detect language
        lang = "python" if ".py" in display else "text"
        
        syntax = Syntax(display, lang, theme="monokai", line_numbers=True)
        self.console.print(Panel(syntax, border_style=style))
    
    def _extract_ours(self, file_path: str) -> str:
        """Extract and return 'ours' version of conflicted file."""
        file_full_path = self.git.repo_root / file_path
        content = file_full_path.read_text(encoding="utf-8", errors="replace")
        
        # Remove conflict markers, keep ours (between <<<<<<< and =======)
        pattern = r"<<<<<<< HEAD\n(.*?)=======\n.*?>>>>>>> .*?\n"
        def replace_ours(match):
            return match.group(1)
        
        # Also handle case where markers don't have newline at end
        pattern2 = r"<<<<<<< HEAD\n(.*?)=======\n.*?>>>>>>> .*?$"
        
        result = re.sub(pattern, replace_ours, content, flags=re.DOTALL)
        result = re.sub(pattern2, replace_ours, result, flags=re.DOTALL)
        
        return result
    
    def _extract_theirs(self, file_path: str) -> str:
        """Extract and return 'theirs' version of conflicted file."""
        file_full_path = self.git.repo_root / file_path
        content = file_full_path.read_text(encoding="utf-8", errors="replace")
        
        # Remove conflict markers, keep theirs (between ======= and >>>>>>>)
        pattern = r"<<<<<<< HEAD\n.*?=======(.*?)>>>>>>> .*?\n"
        def replace_theirs(match):
            return match.group(1)
        
        pattern2 = r"<<<<<<< HEAD\n.*?=======(.*?)>>>>>>> .*?$"
        
        result = re.sub(pattern, replace_theirs, content, flags=re.DOTALL)
        result = re.sub(pattern2, replace_theirs, result, flags=re.DOTALL)
        
        return result
    
    def _extract_both(self, file_path: str) -> str:
        """Extract and merge both versions."""
        file_full_path = self.git.repo_root / file_path
        content = file_full_path.read_text(encoding="utf-8", errors="replace")
        
        # Replace conflict markers with a separator comment
        pattern = r"<<<<<<< HEAD\n(.*?)=======(.*?)>>>>>>> .*?\n"
        def replace_both(match):
            ours = match.group(1).strip()
            theirs = match.group(2).strip()
            return f"{ours}\n\n# === Merged from remote ===\n{theirs}\n"
        
        pattern2 = r"<<<<<<< HEAD\n(.*?)=======(.*?)>>>>>>> .*?$"
        
        result = re.sub(pattern, replace_both, content, flags=re.DOTALL)
        result = re.sub(pattern2, replace_both, result, flags=re.DOTALL)
        
        return result


def show_conflict_summary(console: Console, conflicted_files: list[str]):
    """Show a summary of all conflicted files."""
    console.print("\n[bold yellow]冲突文件列表:[/bold yellow]")
    for i, f in enumerate(conflicted_files, 1):
        console.print(f"  {i}. {f}")
