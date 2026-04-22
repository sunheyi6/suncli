"""Teammate - persistent agent with lifecycle (s15/s17)."""

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, List

import httpx

from ..tools.executor import ToolCallParser, ToolExecutor


class TeammateStatus(Enum):
    """Teammate lifecycle status."""
    WORKING = "working"
    IDLE = "idle"
    SHUTDOWN = "shutdown"


@dataclass
class IdentityContext:
    """Identity block for context restoration."""
    name: str
    role: str
    team_name: str


class Teammate:
    """A persistent teammate with independent message history.
    
    Lifecycle: WORK -> IDLE -> WORK or SHUTDOWN
    In IDLE phase, polls inbox and task board for new work.
    """
    
    IDLE_TIMEOUT = 60  # Seconds before shutdown when idle
    POLL_INTERVAL = 5   # Seconds between idle polls
    
    def __init__(
        self,
        name: str,
        role: str,
        team_name: str,
        client: httpx.AsyncClient,
        config: Any,
        mailbox,
        task_board,
    ):
        """Initialize teammate.
        
        Args:
            name: Unique name
            role: Role (coder, tester, reviewer, etc.)
            team_name: Team identifier
            client: HTTP client for API calls
            config: Configuration
            mailbox: Mailbox for receiving messages
            task_board: Task board for auto-claim
        """
        self.name = name
        self.role = role
        self.team_name = team_name
        self.client = client
        self.config = config
        self.mailbox = mailbox
        self.task_board = task_board
        
        self.status = TeammateStatus.WORKING
        self.messages: list[dict] = []
        self.idle_time = 0
        self.output_log: Optional[List[str]] = None  # Shared output buffer
        
        # Initial system prompt
        self._init_messages()
    
    # Role-specific system prompts (Chinese for Chinese-speaking users)
    ROLE_PROMPTS: dict[str, str] = {
        "coder": """你是一名资深软件工程师。你的任务是编写干净、正确、可维护的代码。

工作准则：
- 遵循项目现有的代码风格和约定
- 编写模块化、结构清晰的代码
- 使用清晰的变量名和函数名
- 在适当的地方添加错误处理
- 修改完成后，通过读取文件验证结果
- 报告你修改了哪些文件以及原因

你拥有的工具：read、write、edit、bash。
使用这些工具完成你的工作。""",
        "tester": """你是一名质量保障工程师。你的任务是编写测试并验证代码是否正确工作。

工作准则：
- 编写全面的测试用例，覆盖正常情况、边界情况和异常情况
- 使用项目现有的测试框架（pytest、jest 等）
- 编写测试后运行它们并报告结果
- 如果测试失败，分析错误并判断是测试问题还是代码 bug
- 报告测试覆盖率和未覆盖的边界情况

你拥有的工具：read、write、edit、bash。
使用这些工具完成你的工作。""",
        "reviewer": """你是一名资深代码审查员。你的任务是审查代码的质量、正确性和可维护性。

工作准则：
- 检查 bug、逻辑错误和安全问题
- 发现代码异味：重复、过度复杂的函数、不清晰的命名
- 验证代码是否遵循语言/框架的最佳实践
- 给出具体的改进建议，附带代码示例
- 保持建设性：解释 WHY 有问题，而不只是指出有问题
- **不要自己重写代码** -- 提供审查意见供 coder 处理

你拥有的工具：read、write、edit、bash。
使用这些工具完成你的工作。""",
        "docs": """你是一名技术文档工程师。你的任务是编写清晰、准确的技术文档。

工作准则：
- 面向目标受众写作（用户、开发者或贡献者）
- 使用清晰、简洁的语言，避免不必要的术语
- 在有帮助的地方包含示例
- 代码变更影响文档时，更新现有文档
- 保持格式和结构的一致性
- 完成前检查链接、代码示例和格式

你拥有的工具：read、write、edit、bash。
使用这些工具完成你的工作。""",
        "researcher": """你是一名技术研究员。你的任务是调查问题、分析数据、收集信息。

工作准则：
- 需要时通过网络搜索获取当前、准确的信息
- 仔细阅读源代码、日志和配置文件
- 用证据清晰地总结发现
- 区分事实和假设
- 如果答案不确定，如实说明并解释原因
- 基于研究结果提供可执行的建议

你拥有的工具：read、write、edit、bash、web_search。
使用这些工具完成你的工作。""",
    }

    def _init_messages(self):
        """Initialize message history with identity."""
        role_prompt = self.ROLE_PROMPTS.get(self.role.lower(), f"""You are '{self.name}', a {self.role} on team '{self.team_name}'.

Your responsibilities:
1. Complete assigned tasks using available tools
2. Report progress and results clearly
3. When idle, wait for new assignments
4. Follow team protocols for approvals

You have access to tools: read, write, edit, bash.
Use them to accomplish your work.""")

        self.messages = [
            {
                "role": "system",
                "content": f"""You are '{self.name}' on team '{self.team_name}'.

{role_prompt}"""
            }
        ]
    
    def _log(self, message: str):
        """Append output to shared log if available."""
        if self.output_log is not None:
            self.output_log.append(f"[{self.name}] {message}")

    async def run(self, initial_prompt: str):
        """Main lifecycle loop.
        
        Args:
            initial_prompt: Initial task
        """
        self._log(f"Started with task: {initial_prompt[:60]}...")
        
        # Start with initial work
        self.messages.append({"role": "user", "content": initial_prompt})
        
        shutdown_reason = "unknown"
        while True:
            # WORK PHASE
            phase_result = await self._work_phase()
            if phase_result == "error_fatal":
                shutdown_reason = "LLM call failed repeatedly"
                break
            if phase_result == "shutdown":
                shutdown_reason = "tool errors exhausted"
                break
            if phase_result == "done":
                pass  # Go to idle
            
            # IDLE PHASE
            should_resume = await self._idle_phase()
            if not should_resume:
                self.status = TeammateStatus.SHUTDOWN
                shutdown_reason = "idle timeout"
                break
            
            self.status = TeammateStatus.WORKING
        
        self._log(f"Shutdown: {shutdown_reason}")
        return f"{self.name} shutdown: {shutdown_reason}"
    
    async def _work_phase(self, max_iterations: int = 50) -> str:
        """Execute work until done or need to idle.
        
        Returns:
            "done" - work completed, go to idle
            "shutdown" - too many errors, shutdown
            "error_fatal" - LLM call failed, shutdown
        """
        consecutive_errors = 0
        
        for iteration in range(max_iterations):
            # Call LLM
            response = await self._call_llm()
            
            if not response:
                # LLM call failed -- report and try once more
                self._report_issue_to_lead(
                    f"LLM call failed during work phase (iteration {iteration + 1}). "
                    f"This may be due to API errors or rate limiting."
                )
                # Try once more after a short delay
                await asyncio.sleep(2)
                response = await self._call_llm()
                if not response:
                    self._log("LLM call failed twice, shutting down")
                    return "error_fatal"
            
            # Check for tool calls
            tool_calls = ToolCallParser.parse(response)
            
            if not tool_calls:
                # Work complete
                self.messages.append({"role": "assistant", "content": response})
                self._log(f"Work completed: {response[:100]}...")
                return "done"
            
            # Execute tools
            self.messages.append({"role": "assistant", "content": response})
            
            results = []
            error_count = 0
            for call in tool_calls:
                result = ToolExecutor.execute_native(call)
                if isinstance(result, str) and result.strip().lower().startswith("error"):
                    error_count += 1
                results.append({
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": result if isinstance(result, str) else str(result),
                })
            
            # Track consecutive error rounds
            if error_count == len(tool_calls) and tool_calls:
                consecutive_errors += 1
                self._log(f"All tools failed this round ({consecutive_errors}/3)")
                if consecutive_errors >= 3:
                    self._report_issue_to_lead(
                        f"Tools failed {consecutive_errors} consecutive rounds. "
                        f"Last error: {results[-1]['content'][:200] if results else 'unknown'}. "
                        f"I need guidance to proceed."
                    )
                    return "shutdown"
            else:
                consecutive_errors = 0
            
            self.messages.append({"role": "user", "content": json.dumps(results)})
        
        # Max iterations
        self._log("Reached max work iterations, going idle")
        return "done"
    
    async def _idle_phase(self) -> bool:
        """Poll for new work.
        
        Returns:
            True if should resume work, False if should shutdown
        """
        self.status = TeammateStatus.IDLE
        
        elapsed = 0
        while elapsed < self.IDLE_TIMEOUT:
            # 1. Check inbox first (explicit messages)
            inbox = self.mailbox.read_inbox(self.name)
            if inbox:
                self._ensure_identity()
                for msg in inbox:
                    self.messages.append({
                        "role": "user",
                        "content": f"<inbox from=\"{msg.get('from', 'unknown')}\">{msg.get('content', '')}</inbox>"
                    })
                return True
            
            # 2. Scan for auto-claimable tasks
            claimable = self.task_board.find_claimable(role=self.role)
            if claimable:
                task = claimable[0]
                success = self.task_board.claim_task(
                    task["id"], 
                    self.name, 
                    source="auto"
                )
                if success:
                    self._ensure_identity()
                    self.messages.append({
                        "role": "user",
                        "content": f"<auto-claimed>Task #{task['id']}: {task['subject']}</auto-claimed>"
                    })
                    return True
            
            # 3. Wait
            await asyncio.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL
        
        # Timeout - shutdown
        return False
    
    def _ensure_identity(self):
        """Re-inject identity if messages are short (after compression)."""
        if len(self.messages) <= 3:
            # Context was likely compressed, re-inject identity
            self.messages.insert(0, {
                "role": "user",
                "content": f"<identity>You are '{self.name}', role: {self.role}, team: {self.team_name}. Continue your work.</identity>"
            })
            self.messages.insert(1, {
                "role": "assistant",
                "content": f"I am {self.name}. Continuing."
            })
    
    def _report_issue_to_lead(self, message: str):
        """Report a problem to the team lead via mailbox and output log."""
        self._log(f"REPORT TO LEAD: {message}")
        try:
            if self.mailbox:
                self.mailbox.send(
                    from_agent=self.name,
                    to_agent="lead",
                    content=f"[HELP NEEDED] {message}",
                    msg_type="help_request",
                )
        except Exception:
            pass

    async def _call_llm(self) -> Optional[str]:
        """Call LLM with current messages."""
        try:
            response = await self.client.post(
                "/chat/completions",
                json={
                    "model": self.config.model,
                    "messages": self.messages,
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"] or ""
        except Exception as e:
            self._log(f"LLM call error: {str(e)[:100]}")
            return None
    
    def to_dict(self) -> dict:
        """Serialize teammate state."""
        return {
            "name": self.name,
            "role": self.role,
            "team_name": self.team_name,
            "status": self.status.value,
        }
