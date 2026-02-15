"""Chat functionality for Sun CLI."""

import json
import uuid
import re

import httpx
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text
from rich.align import Align
from rich.panel import Panel

from .config import get_config
from .models import Conversation, MessageRole
from .prompts import get_prompt_manager
from .mirror_manager import get_mirror_manager
from .tools import TOOL_DEFINITIONS
from .tools.executor import ToolCallParser, ToolExecutor, ToolCall
from .skills import get_skill_manager, SkillContext
from .skills.git import GitSkill
from .skills.prompt import PromptSkill
from .skills.config import ConfigSkill
from .plan_mode import PlanModeManager, PlanMode
from .context_collector import get_context_collector


class ChatSession:
    """A chat session with an AI model."""
    
    def __init__(self, console: Console) -> None:
        self.console = console
        self.config = get_config()
        self.conversation = Conversation(id=str(uuid.uuid4())[:8])
        self.prompt_manager = get_prompt_manager()
        
        # Initialize plan mode manager
        self.plan_manager = PlanModeManager(console)
        
        # Initialize skill manager
        self.skill_manager = get_skill_manager()
        
        # Register skills
        self.skill_manager.register(GitSkill())
        self.skill_manager.register(PromptSkill())
        self.skill_manager.register(ConfigSkill())
        
        # Detect location for language preference
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
        
        # Initialize with system prompt
        self._initialize_system_prompt()
    
    def _initialize_system_prompt(self) -> None:
        """Load system prompt from prompt files, skills, and project context."""
        tools_prompt = TOOL_DEFINITIONS
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
        
        # Collect and add project context
        try:
            context_collector = get_context_collector(self.console)
            project_context = context_collector.build_system_context()
            
            # Show context summary to user
            context_summary = context_collector.collect()
            if context_summary.project_name:
                self.console.print(Panel(
                    f"[bold]{context_summary.project_name}[/bold] ({context_summary.project_type})\n"
                    f"[dim]{context_summary.root_path}[/dim]",
                    title="[blue]📂 已加载项目信息[/blue]",
                    border_style="blue"
                ))
            
            # Add project context to system prompt
            system_prompt = f"{system_prompt}\n\n{project_context}"
        except Exception as e:
            # Don't fail if context collection fails
            self.console.print(f"[dim]⚠️ 无法加载项目信息: {e}[/dim]")
        
        # Combine all prompts
        if plan_mode_prompt:
            system_prompt = f"{system_prompt}\n\n{plan_mode_prompt}"
        
        if system_prompt:
            self.conversation.add_message(MessageRole.SYSTEM, system_prompt)
    
    def _render_with_code_highlight(self, content: str) -> None:
        """Render content with enhanced code block highlighting."""
        import re
        from rich.console import Group
        
        # Pattern to match code blocks
        code_block_pattern = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
        
        parts = []
        last_end = 0
        
        for match in code_block_pattern.finditer(content):
            # Add text before code block as Markdown
            if match.start() > last_end:
                text_part = content[last_end:match.start()]
                if text_part.strip():
                    parts.append(Markdown(text_part))
            
            # Create syntax highlighted code block
            language = match.group(1) or "text"
            code = match.group(2).rstrip('\n')
            
            # Map common aliases
            lang_map = {
                "py": "python", "js": "javascript", "ts": "typescript",
                "sh": "bash", "shell": "bash", "zsh": "bash",
                "yml": "yaml", "": "text",
            }
            syntax_lang = lang_map.get(language.lower(), language.lower())
            
            # Create syntax highlighted panel
            syntax = Syntax(
                code,
                syntax_lang,
                theme="monokai",
                line_numbers=True,
                word_wrap=True,
                padding=(1, 2),
            )
            
            lang_display = language.upper() if language else "CODE"
            panel = Panel(
                syntax,
                title=f"[bold cyan]📋 {lang_display}[/bold cyan]",
                title_align="left",
                border_style="cyan",
                subtitle="[dim]💡 选中复制 / Select to copy[/dim]",
                subtitle_align="right",
                padding=(0, 0),
            )
            parts.append(panel)
            
            last_end = match.end()
        
        # Add remaining text
        if last_end < len(content):
            text_part = content[last_end:]
            if text_part.strip():
                parts.append(Markdown(text_part))
        
        # Render all parts
        if parts:
            self.console.print(Group(*parts))
        else:
            # No code blocks, just render as markdown
            self.console.print(Markdown(content))
    
    async def send_message(self, content: str) -> str:
        """Send a message and get the complete response."""
        # Add user message
        self.conversation.add_message(MessageRole.USER, content)
        
        # Call API
        response = await self.client.post(
            "/chat/completions",
            json={
                "model": self.config.model,
                "messages": self.conversation.to_openai_messages(),
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            },
        )
        response.raise_for_status()
        
        data = response.json()
        assistant_content = data["choices"][0]["message"]["content"] or ""
        self.conversation.add_message(MessageRole.ASSISTANT, assistant_content)
        
        return assistant_content
    
    async def stream_message(self, content: str, max_tool_iterations: int = 10) -> str:
        """Send a message and stream the response with multi-round tool calling support.
        
        This method supports iterative tool calling where the AI can:
        1. Analyze the user's request
        2. Call tools to gather information
        3. Analyze the results
        4. Call more tools if needed
        5. Provide the final answer
        
        Args:
            content: User's message
            max_tool_iterations: Maximum number of tool call rounds (default: 10)
            
        Returns:
            Final assistant response
        """
        # Add user message
        self.conversation.add_message(MessageRole.USER, content)
        
        # Start multi-round tool calling loop
        return await self._run_tool_loop(max_iterations=max_tool_iterations)
    
    async def _run_tool_loop(self, max_iterations: int = 10) -> str:
        """Run the multi-round tool calling loop.
        
        Only displays output for the final round (when no more tool calls are needed).
        Intermediate rounds with tool calls are processed silently.
        
        Args:
            max_iterations: Maximum number of tool call rounds
            
        Returns:
            Final assistant response
        """
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Get AI response (without displaying for intermediate rounds)
            # We check if this is the final round after parsing tool calls
            full_content = await self._stream_ai_response(display_output=False)
            
            # Check for tool calls
            tool_calls = ToolCallParser.parse(full_content)
            
            if not tool_calls:
                # No tool calls, this is the final response - display it now
                self.conversation.add_message(MessageRole.ASSISTANT, full_content)
                self.console.print(Markdown(full_content))
                return full_content
            
            # There are tool calls - execute them silently
            self.console.print(f"\n[dim][正在分析... {iteration}/{max_iterations}][/dim]")
            tool_results = await self._execute_tool_calls(tool_calls)
            
            # Add assistant message with tool calls to conversation
            self.conversation.add_message(MessageRole.ASSISTANT, full_content)
            
            # Add tool results to conversation
            tool_results_message = self._format_tool_results(tool_calls, tool_results)
            self.conversation.add_message(MessageRole.SYSTEM, tool_results_message)
        
        # Max iterations reached - get final response with display
        self.console.print(f"[yellow]已达到最大工具调用次数 ({max_iterations})，生成最终回复...[/yellow]")
        final_content = await self._stream_ai_response(display_output=True)
        self.conversation.add_message(MessageRole.ASSISTANT, final_content)
        return final_content
    
    async def _stream_ai_response(self, display_output: bool = True) -> str:
        """Stream AI response and return the full content.
        
        Args:
            display_output: Whether to display the streaming output to the user.
                          Set to False for intermediate tool-calling rounds.
        
        Returns:
            Full response content
        """
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
                    # Stream to user
                    with Live(Markdown(""), console=self.console, refresh_per_second=10) as live:
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
                                        live.update(Markdown(full_content))
                                except (json.JSONDecodeError, KeyError):
                                    continue
                else:
                    # Silent mode - just collect the content
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
        """Execute tool calls and display results.
        
        Automatically deduplicates identical tool calls to avoid redundant execution.
        
        Args:
            tool_calls: List of tool calls to execute
            
        Returns:
            List of tool results
        """
        results = []
        executed = {}  # Cache for deduplication: {(name, args_key): result}
        
        for i, call in enumerate(tool_calls, 1):
            # Create a key for deduplication
            args_key = json.dumps(call.args, sort_keys=True, ensure_ascii=False)
            cache_key = (call.name, args_key)
            
            # Check if this exact call was already executed
            if cache_key in executed:
                self.console.print(Panel(
                    f"[dim]{call.to_string()}[/dim]",
                    title=f"[bold blue]Tool {i}/{len(tool_calls)}[/bold blue] [yellow](duplicate, skipped)[/yellow]",
                    border_style="yellow"
                ))
                results.append(executed[cache_key])
                continue
            
            # Show tool call
            self.console.print(Panel(
                f"[cyan]{call.to_string()}[/cyan]",
                title=f"[bold blue]Tool {i}/{len(tool_calls)}[/bold blue]",
                border_style="blue"
            ))
            
            # Execute tool
            result = ToolExecutor.execute(call)
            executed[cache_key] = result
            results.append(result)
            
            # Show result (truncate if too long)
            display_result = result[:800] + "..." if len(result) > 800 else result
            self.console.print(Panel(
                display_result,
                title="[dim]Result[/dim]",
                border_style="green" if "Error" not in result else "red"
            ))
        
        return results
    
    def _format_tool_results(self, tool_calls: list[ToolCall], results: list[str]) -> str:
        """Format tool calls and results for the conversation context.
        
        Args:
            tool_calls: List of tool calls
            results: List of tool results
            
        Returns:
            Formatted message for conversation
        """
        parts = ["[Tool Execution Results]"]
        
        for call, result in zip(tool_calls, results):
            parts.append(f"\nTool: {call.name}")
            parts.append(f"Arguments: {json.dumps(call.args, ensure_ascii=False)}")
            parts.append(f"Result: {result}")
        
        parts.append("\n[End of Tool Results]")
        parts.append("\nBased on the above tool results, please continue with your task.")
        
        return "\n".join(parts)
    
    def _show_api_error(self) -> None:
        """Show API configuration error with recommendations."""
        from rich.table import Table
        
        error_panel = Panel(
            "[bold red]API Authentication Failed[/bold red]\n\n"
            "Your API key is invalid or not configured properly.\n\n"
            "[bold]Recommended AI Services for Chinese Users:[/bold]",
            title="[red]Configuration Error[/red]",
            border_style="red"
        )
        self.console.print(error_panel)
        
        # Create table with AI service recommendations
        table = Table(show_header=True, header_style="bold magenta", border_style="cyan")
        table.add_column("Service", style="cyan", width=20)
        table.add_column("Base URL", style="yellow", width=35)
        table.add_column("Model", style="green", width=20)
        
        table.add_row(
            "Kimi (Moonshot)",
            "https://api.moonshot.cn/v1",
            "moonshot-v1-128k"
        )
        table.add_row(
            "通义千问 (Qwen)",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "qwen-turbo"
        )
        table.add_row(
            "智谱 AI (GLM)",
            "https://open.bigmodel.cn/api/paas/v4",
            "glm-4"
        )
        table.add_row(
            "DeepSeek",
            "https://api.deepseek.com/v1",
            "deepseek-chat"
        )
        
        self.console.print(table)
        
        # Show configuration examples
        self.console.print("\n[bold]Configuration Examples:[/bold]")
        self.console.print("\n[cyan]Kimi API:[/cyan]")
        self.console.print("  suncli config --api-key sk-xxx --base-url https://api.moonshot.cn/v1 --model moonshot-v1-128k")
        
        self.console.print("\n[cyan]通义千问:[/cyan]")
        self.console.print("  suncli config --api-key sk-xxx --base-url https://dashscope.aliyuncs.com/compatible-mode/v1 --model qwen-turbo")
        
        self.console.print("\n[cyan]智谱 AI:[/cyan]")
        self.console.print("  suncli config --api-key sk-xxx --base-url https://open.bigmodel.cn/api/paas/v4 --model glm-4")
        
        self.console.print("\n[dim]Get your API key from the respective service's official website.[/dim]")
    
    def clear_history(self) -> None:
        """Clear conversation history but keep system prompt."""
        system_messages = [m for m in self.conversation.messages if m.role == MessageRole.SYSTEM]
        self.conversation.messages.clear()
        self.conversation.messages.extend(system_messages)
        self.console.print("[dim]Conversation history cleared. (System prompt preserved)[/dim]")
    
    def enter_plan_mode(self, user_input: str) -> None:
        """Enter plan mode for the given user input."""
        self.plan_manager.start_planning(user_input)
        # Reinitialize system prompt with plan mode instructions
        self._initialize_system_prompt()
    
    def approve_plan(self) -> bool:
        """Approve the current plan."""
        return self.plan_manager.approve()
    
    def cancel_plan_mode(self) -> None:
        """Cancel plan mode."""
        self.plan_manager.cancel()
        # Reinitialize system prompt without plan mode
        self._initialize_system_prompt()
    
    def exit_plan_mode(self, title: str, plan: str) -> None:
        """Exit plan mode after successful completion."""
        self.plan_manager.cancel()
        self.console.print(Panel(
            f"[bold green]✅ Plan Completed: {title}[/bold green]\n\n"
            f"[dim]{plan[:200]}{'...' if len(plan) > 200 else ''}[/dim]",
            border_style="green"
        ))
        # Reinitialize system prompt without plan mode
        self._initialize_system_prompt()
    
    def is_in_plan_mode(self) -> bool:
        """Check if currently in plan mode."""
        return self.plan_manager.is_active
    
    def get_plan_mode(self) -> PlanMode:
        """Get current plan mode state."""
        return self.plan_manager.mode
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
