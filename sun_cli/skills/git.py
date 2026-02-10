"""Git workflow skill for Sun CLI."""

from typing import Optional
from ..skills import Skill, SkillContext
from ..git_helper import GitHelper, detect_commit_intent
from ..conflict_resolver import ConflictResolver, show_conflict_summary
from ..config import get_config
from ..notification import get_notification_manager
from rich.panel import Panel
from rich.prompt import Confirm


class GitSkill(Skill):
    """Smart Git workflow skill."""
    
    @property
    def name(self) -> str:
        return "git"
    
    @property
    def description(self) -> str:
        return "Intelligent Git workflow: auto pull, conflict resolution, commit message generation, and push"
    
    @property
    def trigger_keywords(self) -> list[str]:
        return [
            "提交代码", "保存并推送", "commit code", "push code",
            "git commit", "git push", "提交", "推送"
        ]
    
    @property
    def system_prompt(self) -> Optional[str]:
        return """## Git Workflow

You have access to a smart Git workflow that can:
1. Pull from remote (with rebase)
2. Detect and resolve conflicts interactively
3. Generate conventional commit messages using AI
4. Commit and push changes

When user wants to commit code, suggest using the git workflow.
The workflow handles all steps automatically with user confirmation.
"""
    
    def initialize(self, context: SkillContext) -> None:
        super().initialize(context)
        self.git = GitHelper(self.context.console)
        self.resolver = ConflictResolver(self.context.console, self.git)
        self.config = get_config()
        self.notification = get_notification_manager(self.context.console)
    
    async def handle(self, user_input: str) -> bool:
        if not detect_commit_intent(user_input):
            return False
        
        if not self.git.is_git_repo():
            self.context.console.print("[red]当前目录不是 Git 仓库[/red]")
            return True
        
        await self._execute_workflow()
        return True
    
    async def _execute_workflow(self):
        self.context.console.print(Panel(
            "[bold blue]智能 Git 工作流[/bold blue]\n"
            "1. 拉取远程代码\n"
            "2. 检测冲突\n"
            "3. 生成提交信息\n"
            "4. 提交并推送",
            title="Git Workflow"
        ))
        
        status = self.git.get_status()
        
        if status.has_conflicts:
            self.context.console.print("[red]当前存在未解决的冲突，请先解决[/red]")
            if self.resolver.resolve_all(status.conflicted_files):
                self.context.console.print("[green]所有冲突已解决[/green]")
            else:
                return
        
        success, message = self.git.pull(rebase=True)
        
        if not success:
            if message == "conflict":
                status = self.git.get_status()
                if status.conflicted_files:
                    show_conflict_summary(self.context.console, status.conflicted_files)
                    
                    if self.resolver.resolve_all(status.conflicted_files):
                        self.context.console.print("[green]冲突已解决，继续提交流程[/green]")
                    else:
                        self.context.console.print("[yellow]提交已中止，请解决冲突后重试[/yellow]")
                        return
            else:
                self.context.console.print(f"[red]拉取失败: {message}[/red]")
                return
        else:
            self.context.console.print(f"[dim]{message}[/dim]")
        
        status = self.git.get_status()
        
        if not status.has_changes and not status.ahead:
            self.context.console.print("[dim]没有需要提交的更改[/dim]")
            return
        
        if status.unstaged or status.untracked:
            self.context.console.print("[dim]正在暂存所有更改...[/dim]")
            self.git.stage_all()
        
        commit_message = await self._generate_commit_message()
        
        if not commit_message:
            self.context.console.print("[red]无法生成提交信息[/red]")
            return
        
        self.context.console.print(f"\n[bold]建议的提交信息:[/bold]")
        self.context.console.print(Panel(commit_message, border_style="green"))
        
        if not Confirm.ask("确认提交?", default=True):
            self.context.console.print("[dim]已取消提交[/dim]")
            return
        
        if not self.git.commit(commit_message):
            self.context.console.print("[red]提交失败[/red]")
            return
        
        self.context.console.print("[green]提交成功[/green]")
        
        success, message = self.git.push()
        if success:
            self.context.console.print("[green]推送成功[/green]")
            self.notification.notify_success("代码已成功推送到远程仓库")
        else:
            self.context.console.print(f"[red]推送失败: {message}[/red]")
    
    async def _generate_commit_message(self) -> Optional[str]:
        import httpx
        
        diff = self.git.get_staged_diff()
        if not diff:
            return None
        
        recent_commits = self.git.get_recent_commits(3)
        formatted_diff = self._format_diff_for_ai(diff, max_lines=150)
        prompt = self._build_commit_prompt(formatted_diff, recent_commits)
        
        try:
            self.context.console.print("[dim]正在生成提交信息...[/dim]")
            
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
            
            commit_msg = commit_msg.strip()
            
            if commit_msg.startswith("```"):
                lines = commit_msg.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                commit_msg = "\n".join(lines).strip()
            
            if len(commit_msg) > 100:
                first_line = commit_msg.split("\n")[0]
                if len(first_line) > 100:
                    first_line = first_line[:97] + "..."
                commit_msg = first_line
            
            return commit_msg
            
        except Exception as e:
            self.context.console.print(f"[red]生成提交信息失败: {e}[/red]")
            return "update: code changes"
    
    def _format_diff_for_ai(self, diff: str, max_lines: int = 150) -> str:
        lines = diff.splitlines()
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines.append("... (diff truncated)")
        return "\n".join(lines)
    
    def _build_commit_prompt(self, diff: str, recent_commits: list[str]) -> str:
        recent_commits_str = "\n".join(f"- {c}" for c in recent_commits) if recent_commits else "无"
        
        return f"""请根据以下代码变更生成一个简洁、规范的 Git 提交信息。

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
