"""Chat functionality for Sun CLI - Full s01-s19 implementation."""

import asyncio
import json
import os
import uuid
import re
import time
from typing import Any, Optional
from contextlib import nullcontext

import httpx
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text
from rich.align import Align
from rich.panel import Panel

from .config import get_config
from .models import Conversation, MessageRole, Message
from .prompts import get_prompt_manager
from .mirror_manager import get_mirror_manager
from .tools.definitions import build_tools_prompt
from .tools.executor import ToolCallParser, ToolExecutor, ToolCall
from .skills import get_skill_manager, SkillContext
from .skills.git import GitSkill
from .skills.prompt import PromptSkill
from .skills.config import ConfigSkill
from .plan_mode import PlanModeManager, PlanMode
from .context_collector import get_context_collector
from .logging_config import get_logger

# Cached lazy logger to ensure SUN_LOG_LEVEL is set before first call
_cached_logger = None
def _get_logger():
    global _cached_logger
    if _cached_logger is None:
        _cached_logger = get_logger(__name__)
    return _cached_logger

# s04: Subagent
from .subagent import run_subagent

# s08/s13: Background tasks
from .background import get_background_manager

# s09: Memory
from .memory import get_memory_manager

# s12/s18: Worktree
from .worktree import WorktreeManager

# s14: Scheduler
from .task import get_scheduler

# s15-s17: Team
from .team import get_team_manager

# s19: MCP
from .mcp import MCPClient, PluginLoader


class ChatSession:
    """A chat session with full agent capabilities (s01-s19)."""
    COMPACT_MARKER = "[CONTEXT_COMPACT_SUMMARY]"
    
    def __init__(self, console: Console) -> None:
        self.console = console
        self.config = get_config()
        self.conversation = Conversation(id=str(uuid.uuid4())[:8])
        self.prompt_manager = get_prompt_manager()
        
        # Plan mode manager
        self.plan_manager = PlanModeManager(console)
        
        # Skill manager
        self.skill_manager = get_skill_manager()
        self.skill_manager.register(GitSkill())
        self.skill_manager.register(PromptSkill())
        self.skill_manager.register(ConfigSkill())
        
        # Detect location
        self._is_china_mainland = False
        try:
            mm = get_mirror_manager()
            self._is_china_mainland = mm.detect_location()
        except Exception:
            pass
        
        if not self.config.is_configured:
            raise RuntimeError(
                "API key not configured. Run `sun config` to set it up, "
                "or set SUN_API_KEY environment variable."
            )
        
        self.client = httpx.AsyncClient(
            base_url=self.config.base_url,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )
        
        # s08/s13: Background manager
        self.background = get_background_manager()
        
        # s09: Memory manager
        self.memory = get_memory_manager()
        
        # s12/s18: Worktree manager
        self.worktree = WorktreeManager()
        
        # s14: Scheduler
        self.scheduler = get_scheduler()
        
        # s15-s17: Team manager
        self.team = get_team_manager(self.client, self.config)
        
        # s19: MCP client
        self.mcp_client = MCPClient()
        self._mcp_connected = False
        
        # Tool executor with custom handlers
        self.tool_executor = ToolExecutor()
        self._register_custom_tools()
        
        # Initialize with system prompt
        self._initialize_system_prompt()
    
    def _register_custom_tools(self):
        """Register extended tool handlers."""
        # Web Search (async handler)
        self.tool_executor.register_handler("web_search", self._do_web_search)
        self.tool_executor.register_handler("weather_now", self._do_weather_now)
        
        # s04: Subagent
        self.tool_executor.register_handler("subagent", self._handle_subagent)
        
        # s13: Background tasks
        self.tool_executor.register_handler("background_run", self._handle_background_run)
        self.tool_executor.register_handler("background_check", self._handle_background_check)
        
        # s14: Scheduler
        self.tool_executor.register_handler("schedule_create", self._handle_schedule_create)
        self.tool_executor.register_handler("schedule_list", self._handle_schedule_list)
        self.tool_executor.register_handler("schedule_remove", self._handle_schedule_remove)
        
        # s15-s17: Team
        self.tool_executor.register_handler("team_spawn", self._handle_team_spawn)
        self.tool_executor.register_handler("team_send", self._handle_team_send)
        self.tool_executor.register_handler("team_list", self._handle_team_list)
        
        # s16: Protocol
        self.tool_executor.register_handler("request_approval", self._handle_request_approval)
        
        # s18: Worktree
        self.tool_executor.register_handler("worktree_create", self._handle_worktree_create)
        self.tool_executor.register_handler("worktree_enter", self._handle_worktree_enter)
        self.tool_executor.register_handler("worktree_closeout", self._handle_worktree_closeout)
        
        # s09: Memory
        self.tool_executor.register_handler("save_memory", self._handle_save_memory)
        self.tool_executor.register_handler("load_memory", self._handle_load_memory)
    
    # ========== Web Search ==========
    
    async def _do_web_search(self, query: str, max_results: int = 5) -> str:
        """Async implementation of web search."""
        normalized = (query or "").strip()
        lower_q = normalized.lower()
        if normalized and (
            "天气" in normalized
            or "气温" in normalized
            or "weather" in lower_q
            or "temperature" in lower_q
        ):
            location = self._extract_weather_location(normalized)
            return await self._do_weather_now(location=location)

        from .tools.web_search import DuckDuckGoSearch
        
        searcher = DuckDuckGoSearch()
        try:
            results = await searcher.search(normalized, max(1, min(10, int(max_results) if max_results else 5)))
            await searcher.close()
            
            if not results:
                return "No results found. Try a different query."
            
            lines = [f"Search results for: '{query}'\n"]
            for i, result in enumerate(results, 1):
                lines.append(f"{i}. {result.title}")
                if result.href:
                    lines.append(f"   URL: {result.href}")
                if result.body:
                    snippet = result.body[:200] + "..." if len(result.body) > 200 else result.body
                    lines.append(f"   {snippet}")
                lines.append("")
            
            return "\n".join(lines)
        except Exception as e:
            await searcher.close()
            return f"Search failed: {str(e)}"

    @staticmethod
    def _extract_weather_location(query: str) -> str:
        """Extract a best-effort location from weather query."""
        if "北京" in query:
            return "北京"

        m = re.search(r"([\u4e00-\u9fffA-Za-z\s]{1,20})天气", query)
        if m:
            location = m.group(1).strip()
            for noise in ["今日", "今天", "实时", "当前", "温度", "降水", "预报", "查询", "搜索"]:
                location = location.replace(noise, "")
            location = "".join(location.split()).strip()
            if location:
                return location

        return "Beijing"

    async def _do_weather_now(self, location: str = "Beijing") -> str:
        """Fetch current weather and today's forecast from wttr.in."""
        from urllib.parse import quote

        url = f"https://wttr.in/{quote(location)}?format=j1"
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
                resp.raise_for_status()
                data = resp.json()

            current = (data.get("current_condition") or [{}])[0]
            today = (data.get("weather") or [{}])[0]
            desc_items = current.get("weatherDesc") or []
            desc = desc_items[0].get("value", "") if desc_items else ""

            lines = [
                f"Weather for {location}",
                f"- Condition: {desc or 'N/A'}",
                f"- Current Temp: {current.get('temp_C', 'N/A')}°C",
                f"- Feels Like: {current.get('FeelsLikeC', current.get('feelslike_C', 'N/A'))}°C",
                f"- Humidity: {current.get('humidity', 'N/A')}%",
                f"- Wind: {current.get('windspeedKmph', 'N/A')} km/h {current.get('winddir16Point', '')}".strip(),
                f"- Precipitation: {current.get('precipMM', 'N/A')} mm",
                f"- UV Index: {current.get('uvIndex', 'N/A')}",
                f"- Today's High/Low: {today.get('maxtempC', 'N/A')}°C / {today.get('mintempC', 'N/A')}°C",
                "- Source: wttr.in",
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"Weather lookup failed: {e}"
    
    def _initialize_system_prompt(self) -> None:
        """Load system prompt with all extensions."""
        tools_prompt = build_tools_prompt()
        skills_prompt = self.skill_manager.get_all_system_prompts()
        
        # Add plan mode prompt if active
        plan_mode_prompt = ""
        if self.plan_manager.is_active:
            plan_mode_prompt = self.plan_manager.get_system_prompt()
        
        # Get system type
        system_type = self._get_system_type()
        shell_type = self._get_tool_shell_type()
        
        # Build base system prompt
        system_prompt = self.prompt_manager.build_system_prompt(
            self._is_china_mainland, 
            system_type=system_type,
            shell_type=shell_type,
            tools_prompt=tools_prompt,
            skills_prompt=skills_prompt
        )
        
        # Add project context
        try:
            context_collector = get_context_collector(self.console)
            project_context = context_collector.build_system_context()
            
            context_summary = context_collector.collect()
            if context_summary.agents_md_found:
                self.console.print(Panel(
                    f"[bold]{context_summary.root_path.name}[/bold]\n"
                    f"[dim]{context_summary.root_path}[/dim]\n"
                    f"[green][OK] AGENTS.md loaded[/green]",
                    title="[blue][Project] Context loaded[/blue]",
                    border_style="blue"
                ))
            
            system_prompt = f"{system_prompt}\n\n{project_context}"
        except Exception as e:
            self.console.print(f"[dim][!] Could not load project context: {e}[/dim]")
        
        # s09: Load memories
        memory_section = self.memory.load_for_session()
        if memory_section:
            system_prompt = f"{system_prompt}\n\n{memory_section}"
        
        # Combine all prompts
        if plan_mode_prompt:
            system_prompt = f"{system_prompt}\n\n{plan_mode_prompt}"
        
        if system_prompt:
            _get_logger().debug(f"系统提示词构建完成，长度: {len(system_prompt)} 字符")
            _get_logger().debug(f"系统提示词内容: {system_prompt[:1000]}...")
            self.conversation.add_message(MessageRole.SYSTEM, system_prompt)
    
    # ========== s04: Subagent ==========
    
    def _handle_subagent(self, prompt: str, tools: list = None) -> str:
        """Handle subagent tool call."""
        import asyncio
        
        self.console.print(f"[dim]Spawning subagent for: {prompt[:50]}...[/dim]")
        
        # Run subagent synchronously (since we're in tool context)
        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                run_subagent(self.client, self.config, prompt, tools)
            )
            return f"Subagent result:\n{result}"
        except Exception as e:
            return f"Subagent error: {e}"
    
    # ========== s13: Background Tasks ==========
    
    def _handle_background_run(self, command: str, description: str = "") -> str:
        """Handle background_run tool."""
        task_id = self.background.run(command, description)
        return f"Background task started: {task_id}\nUse background_check to get results."
    
    def _handle_background_check(self, task_id: str = None) -> str:
        """Handle background_check tool."""
        tasks = self.background.check(task_id)
        
        lines = []
        for task in tasks:
            lines.append(f"Task {task.id}:")
            lines.append(f"  Command: {task.command}")
            lines.append(f"  Status: {task.status}")
            if task.result_preview:
                lines.append(f"  Preview: {task.result_preview[:200]}")
            if task.status in ("completed", "failed", "timeout"):
                # Read full output
                output = self.background.read_output(task.id, max_chars=2000)
                lines.append(f"  Output:\n{output}")
        
        return "\n".join(lines) if lines else "No background tasks found"
    
    # ========== s14: Scheduler ==========
    
    def _handle_schedule_create(self, cron: str, prompt: str, recurring: bool = True, name: str = None) -> str:
        """Handle schedule_create tool."""
        schedule_id = self.scheduler.create(cron, prompt, name, recurring)
        return f"Schedule created: {schedule_id}\nCron: {cron}\nPrompt: {prompt[:100]}..."
    
    def _handle_schedule_list(self) -> str:
        """Handle schedule_list tool."""
        schedules = self.scheduler.list_all()
        
        if not schedules:
            return "No scheduled tasks"
        
        lines = ["Scheduled tasks:"]
        for s in schedules:
            status = "enabled" if s.enabled else "disabled"
            last = f" (last: {s.last_fired_at})" if s.last_fired_at else ""
            lines.append(f"  {s.schedule_id}: {s.name} [{s.cron}] {status}{last}")
        
        return "\n".join(lines)
    
    def _handle_schedule_remove(self, schedule_id: str) -> str:
        """Handle schedule_remove tool."""
        success = self.scheduler.remove(schedule_id)
        return f"Schedule {schedule_id} {'removed' if success else 'not found'}"
    
    # ========== s15-s17: Team ==========
    
    def _handle_team_spawn(self, name: str, role: str, prompt: str) -> str:
        """Handle team_spawn tool."""
        from .task_manager import TaskManager
        
        task_board = TaskManager()
        teammate = self.team.spawn(name, role, prompt, task_board)
        
        # Start teammate in background (would need async handling in production)
        return f"Teammate spawned: {name} (role: {role})\nStatus: {teammate.status.value}"
    
    def _handle_team_send(self, to: str, content: str) -> str:
        """Handle team_send tool."""
        msg_id = self.team.send_message("lead", to, content)
        return f"Message sent to {to}: {msg_id}"
    
    def _handle_team_list(self) -> str:
        """Handle team_list tool."""
        members = self.team.list_members()
        
        if not members:
            return "No teammates yet"
        
        lines = ["Team members:"]
        for m in members:
            lines.append(f"  {m['name']} ({m['role']}): {m.get('status', 'unknown')}")
        
        return "\n".join(lines)
    
    # ========== s16: Protocol ==========
    
    def _handle_request_approval(self, action: str, request_id: str) -> str:
        """Handle request_approval tool."""
        # In a real implementation, this would queue for user approval
        return f"Approval request '{request_id}' queued for: {action}\n(Use /approve or /reject to respond)"
    
    # ========== s18: Worktree ==========
    
    def _handle_worktree_create(self, name: str, task_id: int) -> str:
        """Handle worktree_create tool."""
        try:
            record = self.worktree.create(name, task_id)
            return f"Worktree created: {name}\nPath: {record.path}\nBranch: {record.branch}\nBound to task: {task_id}"
        except Exception as e:
            return f"Error creating worktree: {e}"
    
    def _handle_worktree_enter(self, name: str) -> str:
        """Handle worktree_enter tool."""
        try:
            path = self.worktree.enter(name)
            return f"Entered worktree: {name}\nPath: {path}\nSubsequent commands will run in this directory."
        except Exception as e:
            return f"Error entering worktree: {e}"
    
    def _handle_worktree_closeout(self, name: str, action: str, reason: str = "", complete_task: bool = False) -> str:
        """Handle worktree_closeout tool."""
        from .task_manager import TaskManager
        
        try:
            task_manager = TaskManager() if complete_task else None
            record = self.worktree.closeout(name, action, reason, complete_task, task_manager)
            
            result = f"Worktree {name} {action}ed"
            if reason:
                result += f" (reason: {reason})"
            if complete_task and record.task_id:
                result += f"\nTask {record.task_id} marked as completed"
            
            return result
        except Exception as e:
            return f"Error in worktree closeout: {e}"
    
    # ========== s09: Memory ==========
    
    def _handle_save_memory(self, name: str, mem_type: str, content: str, description: str = "") -> str:
        """Handle save_memory tool."""
        try:
            path = self.memory.save(name, mem_type, content, description)
            return f"Memory saved: {name}\nType: {mem_type}\nPath: {path}"
        except Exception as e:
            return f"Error saving memory: {e}"
    
    def _handle_load_memory(self, name: str = None, mem_type: str = None) -> str:
        """Handle load_memory tool."""
        if name:
            entry = self.memory.load(name, mem_type)
            if entry:
                return f"Memory: {entry.name}\nType: {entry.type}\nContent:\n{entry.content}"
            return f"Memory not found: {name}"
        
        # List all memories
        memories = self.memory.list_memories()
        if not memories:
            return "No memories stored"
        
        lines = ["Memories:"]
        for m in memories:
            lines.append(f"  {m['name']} [{m['type']}]: {m['description']}")
        
        return "\n".join(lines)
    
    # ========== Core Message Handling ==========
    
    async def stream_message(self, content: str, max_tool_iterations: int = 10) -> str:
        """Send a message with full multi-round tool calling."""
        # Add user message
        self.conversation.add_message(MessageRole.USER, content)

        # Prefetch workspace structure when user asks about current project/folder context.
        if self._should_prefetch_workspace_structure(content):
            await self._prefetch_workspace_structure()
        
        # s06: Maybe compact context
        self._maybe_compact_context()
        
        # Start multi-round tool calling loop
        return await self._run_tool_loop(max_iterations=max_tool_iterations)

    async def _prefetch_workspace_structure(self) -> None:
        """Run one deterministic directory listing and inject it as tool_result context."""
        if os.name == "nt":
            command = "Get-ChildItem -Force | Select-Object -First 200 Mode,Length,LastWriteTime,Name"
        else:
            command = "ls -la"

        _get_logger().debug("触发目录结构预取：先获取当前工作区目录列表")
        preflight_call = ToolCall(
            id="toolu_prefetch_workspace_structure",
            name="bash",
            args={"command": command},
        )
        results = await self._execute_tool_calls([preflight_call])
        tool_result_blocks = self._build_tool_result_blocks([preflight_call], results)
        self.conversation.add_message(
            MessageRole.USER,
            json.dumps(tool_result_blocks, ensure_ascii=False),
        )

    @staticmethod
    def _should_prefetch_workspace_structure(content: str) -> bool:
        """Decide whether current query needs a directory-first context pass."""
        if not content:
            return False
        text = content.strip()
        lower = text.lower()

        # If user already points to concrete files/paths, avoid extra prefetch.
        explicit_path_hints = ("\\", "/", ".py", ".md", ".json", ".yaml", ".yml", ".toml", ".txt")
        if any(h in text for h in explicit_path_hints):
            return False

        folder_scope_keywords = (
            "当前文件夹",
            "当前目录",
            "目录结构",
            "项目结构",
            "项目",
            "仓库",
            "代码库",
            "file structure",
            "project structure",
            "repository",
            "repo",
        )
        analysis_intent_keywords = (
            "看",
            "分析",
            "了解",
            "介绍",
            "说说",
            "逻辑",
            "内容",
            "结构",
            "调用",
            "调用逻辑",
            "analyze",
            "explain",
            "overview",
            "how",
        )

        has_scope = any(k in text for k in folder_scope_keywords) or any(k in lower for k in folder_scope_keywords)
        has_intent = any(k in text for k in analysis_intent_keywords) or any(k in lower for k in analysis_intent_keywords)
        return has_scope and has_intent
    
    async def _run_tool_loop(self, max_iterations: int = 10) -> str:
        """Run the multi-round tool calling loop (s01 + enhancements)."""
        state = {
            "turn_count": 0,
            "transition_reason": None,
            "consecutive_tool_fail_rounds": 0,
        }
        
        for iteration in range(max_iterations):
            state["turn_count"] = iteration + 1
            _get_logger().debug(f"开始第 {state['turn_count']} 轮工具调用循环")
            
            # s06: Micro-compact before each call
            self._micro_compact()
            
            # Check for scheduled tasks (s14)
            await self._check_scheduled_tasks()
            
            # Check for background task completions (s13)
            await self._check_background_tasks()
            
            # Get AI response (only display on first iteration if no tool calls)
            _get_logger().debug("正在获取AI响应...")
            thinking_ctx = (
                nullcontext()
                if self._is_debug_mode()
                else self.console.status("[cyan]正在思考...[/cyan]", spinner="dots")
            )
            with thinking_ctx:
                full_content = await self._stream_ai_response(display_output=False)
            _get_logger().debug(f"AI响应内容:\n{self._format_debug_json(full_content)}")

            # Check for tool calls
            tool_calls = ToolCallParser.parse(full_content)
            _get_logger().debug(f"解析到 {len(tool_calls)} 个工具调用")
            for i, call in enumerate(tool_calls):
                _get_logger().debug(f"工具调用 {i+1}: {call.name} - {call.args}")
            
            if not tool_calls:
                # No tool calls - final response
                # Note: We removed the weak tool_nudge fallback because system prompt now enforces strict JSON-only tool calls.
                _get_logger().debug("无工具调用，返回最终响应")
                cleaned_content = self._sanitize_assistant_output(full_content)
                self._try_capture_plan_from_response(cleaned_content)
                self.conversation.add_message(MessageRole.ASSISTANT, cleaned_content)
                # Display the response
                if cleaned_content:
                    self.console.print(Markdown(cleaned_content))
                state["transition_reason"] = None
                return cleaned_content
            
            # Execute tool calls
            if iteration > 0 and self.config.show_tool_traces:
                self.console.print(f"\n[dim][Analyzing... {iteration + 1}/{max_iterations}][/dim]")
            
            _get_logger().debug("开始执行工具调用")
            tool_results = await self._execute_tool_calls(tool_calls)
            _get_logger().debug(f"工具执行完成，获得 {len(tool_results)} 个结果")

            error_results = [
                r for r in tool_results
                if (r or "").strip().lower().startswith("error")
            ]
            if tool_results and len(error_results) == len(tool_results):
                state["consecutive_tool_fail_rounds"] += 1
                _get_logger().warning(
                    f"本轮工具全部失败，连续失败轮次: {state['consecutive_tool_fail_rounds']}"
                )
            else:
                state["consecutive_tool_fail_rounds"] = 0

            if state["consecutive_tool_fail_rounds"] >= 3:
                latest = self._short_error(error_results[-1]) if error_results else "未知错误"
                stop_msg = (
                    "工具调用连续失败（3 轮），已停止自动重试。\n"
                    f"最近错误：{latest}\n"
                    "常见原因及修正:\n"
                    "- 文件不存在: 先用 bash 列目录确认路径\n"
                    "- 目录传给 read: read 只接受文件，目录请用 bash\n"
                    "- old_str 不匹配: 用 read 获取精确内容后复制粘贴\n"
                    "- 未知工具名: 检查工具名拼写\n"
                    "请修正后重试，或开启新对话 (/new)。"
                )
                self.console.print(f"[red]{stop_msg}[/red]")
                self.conversation.add_message(MessageRole.ASSISTANT, stop_msg)
                return stop_msg
            
            # Add assistant message
            self.conversation.add_message(MessageRole.ASSISTANT, full_content)
            
            # Add tool results
            tool_result_blocks = self._build_tool_result_blocks(tool_calls, tool_results)
            _get_logger().debug(f"构建工具结果块:\n{json.dumps(tool_result_blocks, indent=2, ensure_ascii=False)}")
            self.conversation.add_message(
                MessageRole.USER,
                json.dumps(tool_result_blocks, ensure_ascii=False)
            )
            state["transition_reason"] = "tool_result"
        
        # Max iterations reached
        self.console.print(f"[yellow]Max tool iterations ({max_iterations}) reached, generating final response...[/yellow]")
        final_ctx = (
            nullcontext()
            if self._is_debug_mode()
            else self.console.status("[cyan]正在思考...[/cyan]", spinner="dots")
        )
        with final_ctx:
            final_content = await self._stream_ai_response(display_output=False)
        cleaned_final = self._sanitize_assistant_output(final_content)
        self._try_capture_plan_from_response(cleaned_final)
        self.conversation.add_message(MessageRole.ASSISTANT, cleaned_final)
        if cleaned_final:
            self.console.print(Markdown(cleaned_final))
        return cleaned_final

    @staticmethod
    def _format_debug_json(text: str, max_len: int = 2000) -> str:
        """Format text as indented JSON if possible, otherwise return as-is."""
        if not text or not isinstance(text, str):
            return str(text)[:max_len]
        # Skip JSON formatting for very large text to avoid performance issues
        if len(text) > 5000:
            return text[:max_len] + "\n... (truncated)"
        stripped = text.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                data = json.loads(stripped)
                formatted = json.dumps(data, indent=2, ensure_ascii=False)
                if len(formatted) > max_len:
                    return formatted[:max_len] + "\n... (truncated)"
                return formatted
            except (json.JSONDecodeError, TypeError):
                pass
        if len(text) > max_len:
            return text[:max_len] + "\n... (truncated)"
        return text

    @staticmethod
    def _sanitize_assistant_output(content: str) -> str:
        """Remove raw tool-call payloads from user-facing assistant text."""
        if not content:
            return content

        cleaned = ToolCallParser.XML_PATTERN.sub("", content)
        cleaned = ToolCallParser.JSON_PATTERN.sub("", cleaned)

        # Remove empty code fences left after stripping tool JSON snippets.
        cleaned = re.sub(r"```(?:json)?\s*```", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    async def _check_scheduled_tasks(self):
        """Check and inject scheduled task notifications (s14)."""
        notifications = self.scheduler.check_and_fire()
        if notifications:
            text = self.scheduler.format_for_prompt(notifications)
            self.conversation.add_message(MessageRole.USER, text)
    
    async def _check_background_tasks(self):
        """Check and inject background task notifications (s13)."""
        notifications = self.background.drain_notifications()
        if notifications:
            text = self.background.format_for_prompt(notifications)
            self.conversation.add_message(MessageRole.USER, text)
    
    async def _stream_ai_response(self, display_output: bool = True) -> str:
        """Stream AI response with retry for rate limiting."""
        retries = 3
        for attempt in range(retries):
            try:
                openai_messages = self.conversation.to_openai_messages()
                runtime_context = self._build_runtime_execution_context()
                openai_messages.append({
                    "role": "system",
                    "content": runtime_context,
                })
                _get_logger().debug(f"第 {attempt+1}/{retries} 次尝试调用AI API")
                _get_logger().debug(f"模型: {self.config.model}")
                _get_logger().debug(f"基础URL: {self.config.base_url}")
                _get_logger().debug(f"发送给大模型的消息数量: {len(openai_messages)}")
                if len(openai_messages) > 30:
                    _get_logger().warning(f"消息数量较多 ({len(openai_messages)} 条)，建议尽快完成当前任务或开启新对话以避免上下文混乱。")
                
                # 记录最后一条用户消息
                for i, msg in enumerate(openai_messages):
                    if msg['role'] == 'user':
                        _get_logger().debug(f"用户消息 {i}:\n{self._format_debug_json(msg['content'], max_len=500)}")
                    elif msg['role'] == 'assistant' and i == len(openai_messages) - 1:
                        _get_logger().debug(f"助手消息 {i}:\n{self._format_debug_json(msg['content'], max_len=500)}")
                
                async with self.client.stream(
                    "POST",
                    "/chat/completions",
                    json={
                        "model": self.config.model,
                        "messages": openai_messages,
                        "temperature": self.config.temperature,
                        "max_tokens": self.config.max_tokens,
                        "stream": True,
                    },
                ) as response:
                    _get_logger().debug(f"API响应状态码: {response.status_code}")
                    
                    if response.status_code == 429:
                        if attempt < retries - 1:
                            wait_time = (2 ** attempt) * 1
                            _get_logger().warning(f"速率限制，等待 {wait_time} 秒后重试")
                            self.console.print(f"[yellow]Rate limited. Waiting {wait_time}s before retrying...[/yellow]")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            response.raise_for_status()
                    response.raise_for_status()
                    
                    full_content = ""
                    
                    if display_output:
                        _get_logger().debug("开始流式输出AI响应")
                        with Live(Markdown(""), console=self.console, refresh_per_second=10) as live:
                            async for line in response.aiter_lines():
                                if line.startswith("data: "):
                                    data = line[6:]
                                    if data == "[DONE]":
                                        _get_logger().debug("AI响应流结束")
                                        break
                                    try:
                                        chunk = json.loads(data)
                                        delta = chunk["choices"][0]["delta"].get("content", "")
                                        if delta:
                                            full_content += delta
                                            live.update(Markdown(full_content))
                                    except (json.JSONDecodeError, KeyError):
                                        continue
                    else:
                        _get_logger().debug("获取AI响应（非流式）")
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    _get_logger().debug("AI响应流结束")
                                    break
                                try:
                                    chunk = json.loads(data)
                                    delta = chunk["choices"][0]["delta"].get("content", "")
                                    if delta:
                                        full_content += delta
                                except (json.JSONDecodeError, KeyError):
                                    continue
                    
                    _get_logger().debug(f"AI响应获取完成，长度: {len(full_content)} 字符")
                    return full_content
                    
            except httpx.HTTPStatusError as e:
                status = e.response.status_code if e.response is not None else "unknown"
                body = ""
                if e.response is not None:
                    try:
                        body = (e.response.text or "").strip()
                    except Exception:
                        body = ""
                body_preview = body[:300] + ("..." if len(body) > 300 else "")
                _get_logger().error(f"调用大模型失败 HTTP {status}: {body_preview}")
                self.console.print(f"[red]调用大模型失败 (HTTP {status})[/red]")
                if body_preview:
                    self.console.print(f"[dim]返回信息: {body_preview}[/dim]")
                if e.response.status_code == 401:
                    self._show_api_error()
                if e.response.status_code != 429:
                    raise
            except Exception as e:
                _get_logger().error(f"调用大模型失败: {e}")
                self.console.print(f"[red]调用大模型失败: {e}[/red]")
                if attempt == retries - 1:
                    raise
                wait_time = (2 ** attempt) * 1
                self.console.print(f"[yellow]请求异常，{wait_time}s 后重试...[/yellow]")
                await asyncio.sleep(wait_time)

    @staticmethod
    def _get_system_type() -> str:
        """Get concise system type string for prompts."""
        return "Windows" if os.name == "nt" else "Linux/Mac"

    @staticmethod
    def _get_tool_shell_type() -> str:
        """Get the shell type actually used by the bash tool."""
        if os.name == "nt":
            return "PowerShell"
        shell_path = os.environ.get("SHELL", "")
        if shell_path:
            return os.path.basename(shell_path)
        return "sh"

    def _build_runtime_execution_context(self) -> str:
        """Build a dynamic runtime context system message for each API call."""
        system_type = self._get_system_type()
        shell_type = self._get_tool_shell_type()
        cwd = os.getcwd()
        path_style = "Windows path (e.g. D:\\\\project\\\\file.py)" if os.name == "nt" else "POSIX path (e.g. /home/user/project/file.py)"
        return (
            "Runtime execution context (authoritative for tool calls):\n"
            f"- OS: {system_type}\n"
            f"- Tool command shell: {shell_type}\n"
            f"- Current working directory: {cwd}\n"
            f"- Path style: {path_style}\n"
            "- For bash tool calls, generate commands that run directly in the shell above.\n"
            "- For read/write/edit tool calls, use valid file paths under current workspace.\n"
            "- REMINDER: read tool ONLY accepts files, NEVER directories. Use bash for directory listings.\n"
            "- REMINDER: Do NOT invent file paths. Only use paths confirmed by prior bash/read results."
        )
    
    async def _execute_tool_calls(self, tool_calls: list[ToolCall]) -> list[str]:
        """Execute tool calls with deduplication and compact progress UI."""
        results = []
        executed = {}
        progress_items: list[dict[str, str]] = []
        spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        show_spinner_ui = not self._is_debug_mode()

        live_ctx = (
            Live(self._render_tool_progress(progress_items), console=self.console, refresh_per_second=12)
            if show_spinner_ui
            else nullcontext(None)
        )
        with live_ctx as live:
            for call in tool_calls:
                # Deduplication key
                args_key = json.dumps(call.args, sort_keys=True, ensure_ascii=False)
                cache_key = (call.name, args_key)

                if cache_key in executed:
                    _get_logger().debug(f"工具调用缓存命中: {call.name} - {call.args}")
                    progress_items.append({
                        "status": "success",
                        "text": f"{self._format_tool_call_label(call)} (cached)",
                    })
                    results.append(executed[cache_key])
                    if show_spinner_ui and live is not None:
                        live.update(self._render_tool_progress(progress_items))
                    continue

                _get_logger().debug(f"开始执行工具: {call.name}")
                _get_logger().debug(f"工具参数: {call.args}")
                
                item = {
                    "status": "running",
                    "text": self._format_tool_call_label(call),
                }
                progress_items.append(item)
                if show_spinner_ui and live is not None:
                    live.update(self._render_tool_progress(progress_items, spinner_frames[0]))

                exec_task = asyncio.create_task(self.tool_executor.execute(call))
                spin_index = 0
                current_action = self._format_tool_call_action(call)
                start_time = time.monotonic()
                if show_spinner_ui and live is not None:
                    while not exec_task.done():
                        live.update(self._render_tool_progress(progress_items, spinner_frames[spin_index % len(spinner_frames)], current_action))
                        spin_index += 1
                        await asyncio.sleep(0.08)

                result = await exec_task
                if show_spinner_ui:
                    # Ensure spinner is visible for at least 300ms so user can see it
                    elapsed = time.monotonic() - start_time
                    if elapsed < 0.3:
                        await asyncio.sleep(0.3 - elapsed)
                _get_logger().debug(f"工具执行完成: {call.name}")
                _get_logger().debug(f"工具执行结果: {result[:100]}...")
                
                executed[cache_key] = result
                results.append(result)

                if result.strip().lower().startswith("error"):
                    _get_logger().warning(f"工具执行错误: {result}")
                    item["status"] = "error"
                    item["text"] = f"{item['text']} - {self._short_error(result)}"
                else:
                    item["status"] = "success"

                if show_spinner_ui and live is not None:
                    live.update(self._render_tool_progress(progress_items))

        _get_logger().debug(f"所有工具调用执行完成，共 {len(results)} 个结果")
        return results

    @staticmethod
    def _is_debug_mode() -> bool:
        """Check whether debug logging mode is enabled."""
        return os.environ.get("SUN_LOG_LEVEL", "").upper() == "DEBUG"

    def _format_tool_call_label(self, call: ToolCall) -> str:
        """Format a concise, user-friendly tool execution label."""
        tool_name_map = {
            "read": "读取文件",
            "write": "写入文件",
            "edit": "编辑文件",
            "bash": "执行命令",
            "web_search": "搜索网页",
            "weather_now": "查询天气",
        }
        base = tool_name_map.get(call.name, f"Used {call.name}")

        context = self._get_tool_call_context(call)
        if context:
            if len(context) > 56:
                context = context[:53] + "..."
            return f"{base} ({context})"
        return base

    def _format_tool_call_action(self, call: ToolCall) -> str:
        """Format a Chinese action description for the spinner."""
        action_map = {
            "read": "正在读取文件",
            "write": "正在写入文件",
            "edit": "正在编辑文件",
            "bash": "正在执行命令",
            "web_search": "正在搜索",
            "weather_now": "正在查询天气",
        }
        action = action_map.get(call.name, f"正在执行 {call.name}")

        context = self._get_tool_call_context(call)
        if context:
            if len(context) > 56:
                context = context[:53] + "..."
            return f"{action} {context}"
        return action

    @staticmethod
    def _get_tool_call_context(call: ToolCall) -> str:
        """Extract display context from a tool call."""
        context = (
            call.args.get("file_path")
            or call.args.get("location")
            or call.args.get("query")
            or call.args.get("command")
            or ""
        )
        return str(context).strip()

    @staticmethod
    def _short_error(result: str) -> str:
        """Extract a short one-line error summary."""
        msg = result.replace("\n", " ").strip()
        if msg.lower().startswith("error:"):
            msg = msg[6:].strip()
        return msg[:72] + ("..." if len(msg) > 72 else "")

    @staticmethod
    def _render_tool_progress(items: list[dict[str, str]], spinner: Optional[str] = None, current_action: Optional[str] = None):
        """Render compact tool progress lines with status dots and spinner."""
        lines = []
        for item in items:
            status = item.get("status", "running")
            text = item.get("text", "")
            if status == "running":
                continue
            if status == "success":
                dot = "[green]●[/green]"
            elif status == "error":
                dot = "[red]●[/red]"
            else:
                dot = "[yellow]●[/yellow]"
            lines.append(Text.from_markup(f"{dot} {text}"))

        if spinner:
            action_text = current_action or "正在执行工具"
            lines.append(Text.from_markup(f"[cyan]{spinner} {action_text}...[/cyan]"))

        if not lines:
            action_text = current_action or "正在执行工具"
            lines.append(Text.from_markup(f"[cyan]⠋ {action_text}...[/cyan]"))

        return Group(*lines)
    
    def _build_tool_result_blocks(self, tool_calls: list[ToolCall], results: list[str]) -> list[dict]:
        """Build structured tool_result blocks."""
        blocks = []
        for call, result in zip(tool_calls, results):
            blocks.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": result,
            })
        return blocks
    
    # ========== s06: Context Compression ==========
    
    def _micro_compact(self):
        """Layer 1: Replace old tool results with placeholders."""
        messages = self.conversation.messages
        tool_result_indices = []

        for i, msg in enumerate(messages):
            if msg.role == MessageRole.USER and msg.content:
                try:
                    content = msg.content if isinstance(msg.content, str) else str(msg.content)
                    if content.strip().startswith('[') and '"tool_result"' in content:
                        tool_result_indices.append(i)
                except Exception:
                    pass

        # Keep last 2 tool results, replace older ones with placeholders to prevent context bloat
        if len(tool_result_indices) > 2:
            for idx in tool_result_indices[:-2]:
                try:
                    content = messages[idx].content
                    if isinstance(content, str):
                        data = json.loads(content)
                        if isinstance(data, list):
                            # Replace with placeholders
                            placeholders = []
                            for item in data:
                                if isinstance(item, dict) and item.get("type") == "tool_result":
                                    placeholders.append({
                                        "type": "tool_result",
                                        "tool_use_id": item.get("tool_use_id", "unknown"),
                                        "content": "[Previous tool result - see earlier context]"
                                    })
                            messages[idx].content = json.dumps(placeholders)
                except Exception:
                    pass
    
    def _maybe_compact_context(self):
        """Layer 2: Auto-compact when message count threshold exceeded."""
        if not getattr(self.config, 'auto_compact', True):
            return

        messages = self.conversation.messages
        trigger = getattr(self.config, 'compact_trigger_messages', 24)

        if len(messages) <= trigger:
            return

        # Keep recent messages to preserve working context
        keep_recent = getattr(self.config, 'compact_keep_recent', 10)
        anchor = messages[0] if messages and messages[0].role == MessageRole.SYSTEM else None
        tail = messages[-keep_recent:] if keep_recent < len(messages) else list(messages)

        # Remove old COMPACT_MARKER messages
        tail = [
            msg for msg in tail
            if not (msg.role == MessageRole.SYSTEM and isinstance(msg.content, str) and msg.content.startswith(self.COMPACT_MARKER))
        ]

        # Build summary
        middle_start = 1 if anchor else 0
        middle_end = max(middle_start, len(messages) - keep_recent)
        middle = messages[middle_start:middle_end]

        if not middle:
            return

        summary = self._build_compact_summary(middle)
        compact_message = Message(role=MessageRole.SYSTEM, content=f"{self.COMPACT_MARKER}\n{summary}")

        new_messages = []
        if anchor:
            new_messages.append(anchor)
        new_messages.append(compact_message)
        new_messages.extend(tail)

        self.conversation.messages = new_messages
        self.console.print(f"[dim]Context compacted: {len(messages)} -> {len(new_messages)} messages[/dim]")
    
    def _build_compact_summary(self, messages) -> str:
        """Build summary of old messages."""
        lines = ["Conversation history was compacted. Key points:"]
        
        for msg in messages:
            content = (msg.content or "").strip()
            if not content:
                continue
            if content.startswith(self.COMPACT_MARKER):
                continue
            
            role = msg.role.value
            single_line = " ".join(content.split())
            snippet = single_line[:180] + ("..." if len(single_line) > 180 else "")
            lines.append(f"- {role}: {snippet}")
            
            if len(lines) >= 40:
                lines.append("- ...")
                break
        
        return "\n".join(lines)
    
    # ========== Other Methods ==========
    
    def _show_api_error(self) -> None:
        """Show API configuration error."""
        from rich.table import Table
        
        error_panel = Panel(
            "[bold red]API Authentication Failed[/bold red]\n\n"
            "Your API key is invalid or not configured properly.\n\n"
            "[bold]Recommended AI Services:[/bold]",
            title="[red]Configuration Error[/red]",
            border_style="red"
        )
        self.console.print(error_panel)
        
        table = Table(show_header=True, header_style="bold magenta", border_style="cyan")
        table.add_column("Service", style="cyan", width=20)
        table.add_column("Base URL", style="yellow", width=35)
        table.add_column("Model", style="green", width=20)
        
        table.add_row("Kimi (Moonshot)", "https://api.moonshot.cn/v1", "moonshot-v1-128k")
        table.add_row("Qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-turbo")
        table.add_row("DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat")
        
        self.console.print(table)
    
    def clear_history(self) -> None:
        """Clear conversation history but keep system prompt."""
        system_messages = [m for m in self.conversation.messages if m.role == MessageRole.SYSTEM]
        self.conversation.messages.clear()
        self.conversation.messages.extend(system_messages)
        self.console.print("[dim]Conversation history cleared.[/dim]")
    
    def enter_plan_mode(self, user_input: str) -> None:
        """Enter plan mode."""
        self.plan_manager.start_planning(user_input)
        self._initialize_system_prompt()
    
    def approve_plan(self) -> bool:
        """Approve current plan."""
        return self.plan_manager.approve()
    
    def cancel_plan_mode(self) -> None:
        """Cancel plan mode."""
        self.plan_manager.cancel()
        self._initialize_system_prompt()
    
    def is_in_plan_mode(self) -> bool:
        """Check if in plan mode."""
        return self.plan_manager.is_active
    
    def get_plan_mode(self):
        """Get current plan mode."""
        return self.plan_manager.mode
    
    def list_tasks_text(self) -> str:
        """Get task board text."""
        return self.plan_manager.list_tasks_text()
    
    def update_task_status(self, task_id: int, status: str) -> None:
        """Update task status."""
        self.plan_manager.update_task_status(task_id, status)
    
    def _try_capture_plan_from_response(self, content: str) -> None:
        """Parse plan from assistant response."""
        if not self.plan_manager.is_active or self.plan_manager.mode != PlanMode.PLANNING:
            return
        
        title, description, steps = self._extract_plan_sections(content)
        if len(steps) < 2:
            return
        
        self.plan_manager.set_plan(title=title, description=description, steps=steps)
    
    def _extract_plan_sections(self, content: str) -> tuple[str, str, list[str]]:
        """Extract plan sections from markdown."""
        lines = [line.strip() for line in content.splitlines()]
        title = "Implementation Plan"
        description = "Plan generated from assistant response."
        steps: list[str] = []
        
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip() or title
                break
        
        for i, line in enumerate(lines):
            normalized = line.lower().strip()
            if normalized.startswith("## implementation steps") or normalized.startswith("## steps"):
                description_lines = [x for x in lines[:i] if x and not x.startswith("#")]
                if description_lines:
                    description = description_lines[-1]
                break
        
        step_patterns = [
            re.compile(r"^\d+\.\s+(.+)$"),
            re.compile(r"^[-*]\s+(.+)$"),
            re.compile(r"^(?:⏳|✅|🔄)?\s*\*\*step\s*\d+\s*:\*\*\s*(.+)$", re.IGNORECASE),
        ]
        
        for line in lines:
            for pattern in step_patterns:
                match = pattern.match(line)
                if match:
                    step = match.group(1).strip()
                    if step:
                        steps.append(step)
                    break
        
        deduped_steps = []
        seen = set()
        for step in steps:
            key = step.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped_steps.append(step)
        
        return title, description, deduped_steps
    
    async def close(self) -> None:
        """Close the HTTP client and cleanup."""
        await self.client.aclose()
        # Disconnect MCP servers
        self.mcp_client.disconnect_all()
