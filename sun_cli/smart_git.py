"""Smart Git workflow for Sun CLI."""

import asyncio
import json
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn

from .git_helper import GitHelper, GitStatus, format_diff_for_ai, detect_commit_intent
from .conflict_resolver import ConflictResolver, show_conflict_summary
from .config import get_config


class SmartGitWorkflow:
    """Handles intelligent git commit workflow."""
    
    def __init__(self, console: Console, chat_session=None):
        self.console = console
        self.git = GitHelper(console)
        self.chat = chat_session
        self.resolver = ConflictResolver(console, self.git)
        self.config = get_config()
    
    async def handle_intent(self, user_input: str) -> bool:
        """Handle user's commit intent. Returns True if handled."""
        if not detect_commit_intent(user_input):
            return False
        
        # Check if in git repo
        if not self.git.is_git_repo():
            self.console.print("[red]当前目录不是 Git 仓库[/red]")
            return True
        
        # Execute smart workflow
        await self._execute_workflow()
        return True
    
    async def _execute_workflow(self):
        """Execute the complete smart commit workflow."""
        self.console.print(Panel(
            "[bold blue]智能 Git 工作流[/bold blue]\n"
            "1. 拉取远程代码\n"
            "2. 检测冲突\n"
            "3. 生成提交信息\n"
            "4. 提交并推送",
            title="Git Workflow"
        ))
        
        # Step 1: Check current status
        status = self.git.get_status()
        
        if status.has_conflicts:
            self.console.print("[red]当前存在未解决的冲突，请先解决[/red]")
            if self.resolver.resolve_all(status.conflicted_files):
                self.console.print("[green]所有冲突已解决[/green]")
            else:
                return
        
        # Step 2: Pull from remote
        success, message = self.git.pull(rebase=True)
        
        if not success:
            if message == "conflict":
                # Check for new conflicts after pull
                status = self.git.get_status()
                if status.conflicted_files:
                    show_conflict_summary(self.console, status.conflicted_files)
                    
                    if self.resolver.resolve_all(status.conflicted_files):
                        self.console.print("[green]冲突已解决，继续提交流程[/green]")
                        # Continue with commit
                    else:
                        self.console.print("[yellow]提交已中止，请解决冲突后重试[/yellow]")
                        return
            else:
                self.console.print(f"[red]拉取失败: {message}[/red]")
                return
        else:
            self.console.print(f"[dim]{message}[/dim]")
        
        # Step 3: Stage all changes if needed
        status = self.git.get_status()
        
        if not status.has_changes and not status.ahead:
            self.console.print("[dim]没有需要提交的更改[/dim]")
            return
        
        # Stage all changes
        if status.unstaged or status.untracked:
            self.console.print("[dim]正在暂存所有更改...[/dim]")
            self.git.stage_all()
        
        # Step 4: Generate commit message with AI
        commit_message = await self._generate_commit_message()
        
        if not commit_message:
            self.console.print("[red]无法生成提交信息[/red]")
            return
        
        # Show and confirm
        self.console.print(f"\n[bold]建议的提交信息:[/bold]")
        self.console.print(Panel(commit_message, border_style="green"))
        
        if not Confirm.ask("确认提交?", default=True):
            self.console.print("[dim]已取消提交[/dim]")
            return
        
        # Step 5: Commit
        if not self.git.commit(commit_message):
            self.console.print("[red]提交失败[/red]")
            return
        
        self.console.print("[green]提交成功[/green]")
        
        # Step 6: Push
        success, message = self.git.push()
        if success:
            self.console.print("[green]推送成功[/green]")
        else:
            self.console.print(f"[red]推送失败: {message}[/red]")
    
    async def _generate_commit_message(self) -> Optional[str]:
        """Generate commit message using AI."""
        import httpx
        
        # Get diff
        diff = self.git.get_staged_diff()
        if not diff:
            return None
        
        # Get recent commits for context
        recent_commits = self.git.get_recent_commits(3)
        
        # Format diff (limit size)
        formatted_diff = format_diff_for_ai(diff, max_lines=150)
        
        # Build prompt for AI
        prompt = self._build_commit_prompt(formatted_diff, recent_commits)
        
        # Send to AI directly (don't use chat session to avoid polluting conversation)
        try:
            self.console.print("[dim]正在生成提交信息...[/dim]")
            
            async with httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            ) as client:
                response = await client.post(
                    "/chat/completions",
                    json={
                        "model": self.config.model,
                        "messages": [
                            {"role": "system", "content": "You are a Git expert. Generate concise, conventional commit messages."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 200,
                    },
                )
                response.raise_for_status()
                
                data = response.json()
                commit_msg = data["choices"][0]["message"]["content"] or ""
            
            # Clean the response
            commit_msg = commit_msg.strip()
            
            # Remove code blocks if present
            if commit_msg.startswith("```"):
                lines = commit_msg.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                commit_msg = "\n".join(lines).strip()
            
            # Limit length
            if len(commit_msg) > 100:
                # Try to get just the first line (subject)
                first_line = commit_msg.split("\n")[0]
                if len(first_line) > 100:
                    first_line = first_line[:97] + "..."
                commit_msg = first_line
            
            return commit_msg
            
        except Exception as e:
            self.console.print(f"[red]生成提交信息失败: {e}[/red]")
            # Fallback to a default message
            return "update: code changes"
    
    def _build_commit_prompt(self, diff: str, recent_commits: list[str]) -> str:
        """Build prompt for commit message generation."""
        recent_commits_str = "\n".join(f"- {c}" for c in recent_commits) if recent_commits else "无"
        
        prompt = f"""请根据以下代码变更生成一个简洁、规范的 Git 提交信息。

要求：
1. 使用 Conventional Commits 格式（如 feat:, fix:, docs:, refactor: 等）
2. 标题不超过 50 个字符，简洁明了
3. 如有需要，可添加简要描述（可选）
4. 只返回提交信息，不要其他解释
5. 使用中文或英文，保持与代码变更相关

最近的提交记录（供参考风格）：
{recent_commits_str}

代码变更（diff）：
```diff
{diff}
```

请生成提交信息："""
        
        return prompt
