"""Chat functionality for Sun CLI - Full s01-s19 implementation."""

import asyncio
import json
import uuid
import re
from typing import Any, Optional

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
        
        # Build base system prompt
        system_prompt = self.prompt_manager.build_system_prompt(
            self._is_china_mainland, 
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
        
        # s06: Maybe compact context
        self._maybe_compact_context()
        
        # Start multi-round tool calling loop
        return await self._run_tool_loop(max_iterations=max_tool_iterations)
    
    async def _run_tool_loop(self, max_iterations: int = 10) -> str:
        """Run the multi-round tool calling loop (s01 + enhancements)."""
        state = {
            "turn_count": 0,
            "transition_reason": None,
        }
        
        for iteration in range(max_iterations):
            state["turn_count"] = iteration + 1
            
            # s06: Micro-compact before each call
            self._micro_compact()
            
            # Check for scheduled tasks (s14)
            await self._check_scheduled_tasks()
            
            # Check for background task completions (s13)
            await self._check_background_tasks()
            
            # Get AI response (only display on first iteration, suppress for tool rounds)
            should_display = (iteration == 0)
            full_content = await self._stream_ai_response(display_output=should_display)
            
            # Check for tool calls
            tool_calls = ToolCallParser.parse(full_content)
            
            if not tool_calls:
                # No tool calls - final response
                self._try_capture_plan_from_response(full_content)
                self.conversation.add_message(MessageRole.ASSISTANT, full_content)
                # Only print if not already displayed during streaming
                if not should_display:
                    # Show assistant header with border
                    self.console.print("[bold blue]Assistant:[/bold blue]")
                    self.console.print("─" * 80)
                    # Print full content directly to ensure nothing is truncated
                    self.console.print(full_content)
                    self.console.print("─" * 80)
                state["transition_reason"] = None
                return full_content
            
            # Execute tool calls
            if iteration > 0 and self.config.show_tool_traces:
                self.console.print(f"\n[dim][Analyzing... {iteration + 1}/{max_iterations}][/dim]")
            
            tool_results = await self._execute_tool_calls(tool_calls)
            
            # Add assistant message
            self.conversation.add_message(MessageRole.ASSISTANT, full_content)
            
            # Add tool results
            tool_result_blocks = self._build_tool_result_blocks(tool_calls, tool_results)
            self.conversation.add_message(
                MessageRole.USER,
                json.dumps(tool_result_blocks, ensure_ascii=False)
            )
            state["transition_reason"] = "tool_result"
        
        # Max iterations reached
        self.console.print(f"[yellow]Max tool iterations ({max_iterations}) reached, generating final response...[/yellow]")
        final_content = await self._stream_ai_response(display_output=True)
        self._try_capture_plan_from_response(final_content)
        self.conversation.add_message(MessageRole.ASSISTANT, final_content)
        return final_content
    
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
        """Stream AI response."""
        try:
            async with self.client.stream(
                "POST",
                "/chat/completions",
                json={
                    "model": self.config.model,
                    "messages": self.conversation.to_openai_messages(),
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                
                full_content = ""
                
                if display_output:
                    # Show assistant header with border
                    from rich.panel import Panel
                    from rich.text import Text
                    import sys
                    
                    # Print assistant header
                    self.console.print("[bold blue]Assistant:[/bold blue]")
                    self.console.print("─" * 80)
                    
                    # Kimi CLI-like streaming: print incremental deltas directly
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                                delta = chunk["choices"][0]["delta"].get("content", "")
                                if delta:
                                    full_content += delta
                                    # Stream output directly
                                    self.console.print(delta, end="")
                            except (json.JSONDecodeError, KeyError):
                                continue
                    
                    # Print footer line
                    self.console.print()
                    self.console.print("─" * 80)
                else:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                                delta = chunk["choices"][0]["delta"].get("content", "")
                                if delta:
                                    full_content += delta
                            except (json.JSONDecodeError, KeyError):
                                continue
                
                return full_content
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                self._show_api_error()
            raise
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            raise
    
    async def _execute_tool_calls(self, tool_calls: list[ToolCall]) -> list[str]:
        """Execute tool calls with deduplication and compact progress UI."""
        results = []
        executed = {}
        progress_items: list[dict[str, str]] = []
        spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

        with Live(self._render_tool_progress(progress_items), console=self.console, refresh_per_second=12) as live:
            for call in tool_calls:
                # Deduplication key
                args_key = json.dumps(call.args, sort_keys=True, ensure_ascii=False)
                cache_key = (call.name, args_key)

                if cache_key in executed:
                    progress_items.append({
                        "status": "success",
                        "text": f"{self._format_tool_call_label(call)} (cached)",
                    })
                    results.append(executed[cache_key])
                    live.update(self._render_tool_progress(progress_items))
                    continue

                item = {
                    "status": "running",
                    "text": self._format_tool_call_label(call),
                }
                progress_items.append(item)
                live.update(self._render_tool_progress(progress_items, spinner_frames[0]))

                exec_task = asyncio.create_task(self.tool_executor.execute(call))
                spin_index = 0
                while not exec_task.done():
                    live.update(self._render_tool_progress(progress_items, spinner_frames[spin_index % len(spinner_frames)]))
                    spin_index += 1
                    await asyncio.sleep(0.08)

                result = await exec_task
                executed[cache_key] = result
                results.append(result)

                if result.strip().lower().startswith("error"):
                    item["status"] = "error"
                    item["text"] = f"{item['text']} - {self._short_error(result)}"
                else:
                    item["status"] = "success"

                live.update(self._render_tool_progress(progress_items))

        return results

    def _format_tool_call_label(self, call: ToolCall) -> str:
        """Format a concise, user-friendly tool execution label."""
        tool_name_map = {
            "read": "Used ReadFile",
            "write": "Used WriteFile",
            "edit": "Used StrReplaceFile",
            "bash": "Used Bash",
            "web_search": "Used WebSearch",
            "weather_now": "Used WeatherNow",
        }
        base = tool_name_map.get(call.name, f"Used {call.name}")

        context = (
            call.args.get("file_path")
            or call.args.get("location")
            or call.args.get("query")
            or call.args.get("command")
            or ""
        )
        context = str(context).strip()
        if context:
            if len(context) > 56:
                context = context[:53] + "..."
            return f"{base} ({context})"
        return base

    @staticmethod
    def _short_error(result: str) -> str:
        """Extract a short one-line error summary."""
        msg = result.replace("\n", " ").strip()
        if msg.lower().startswith("error:"):
            msg = msg[6:].strip()
        return msg[:72] + ("..." if len(msg) > 72 else "")

    @staticmethod
    def _render_tool_progress(items: list[dict[str, str]], spinner: Optional[str] = None):
        """Render compact tool progress lines with status dots and spinner."""
        lines = []
        for item in items:
            status = item.get("status", "running")
            text = item.get("text", "")
            if status == "success":
                dot = "[green]●[/green]"
            elif status == "error":
                dot = "[red]●[/red]"
            else:
                dot = "[yellow]●[/yellow]"
            lines.append(Text.from_markup(f"{dot} {text}"))

        if spinner:
            lines.append(Text.from_markup(f"[cyan]{spinner} 正在思考执行...[/cyan]"))

        if not lines:
            lines.append(Text.from_markup("[cyan]⠋ 正在思考执行...[/cyan]"))

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
        # Find tool result messages older than 3 turns
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
        
        # Keep last 3, replace older ones with placeholders
        if len(tool_result_indices) > 3:
            for idx in tool_result_indices[:-3]:
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
        """Layer 2: Auto-compact when token threshold exceeded."""
        if not getattr(self.config, 'auto_compact', True):
            return
        
        messages = self.conversation.messages
        trigger = getattr(self.config, 'compact_trigger_messages', 50)
        
        if len(messages) <= trigger:
            return
        
        # Simple summary approach
        keep_recent = 8
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
