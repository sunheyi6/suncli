"""Main CLI entry point for Sun CLI."""

import asyncio
import getpass
import os
import re
from typing import Iterable, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from . import __app_name__, __version__
from .chat import ChatSession
from .config import get_config, get_config_dir, update_config
from .shell import execute_shell_command, is_shell_command, extract_command
from .prompts import get_prompt_manager
from .skills import get_skill_manager, SkillContext
from .models_presets import (
    get_all_presets,
    get_preset_by_model_id,
    get_presets_by_provider,
    get_provider_names,
    ModelPreset,
)

# Try to import prompt_toolkit for enhanced input with real-time hints
try:
    from prompt_toolkit.application.current import get_app_or_none
    from prompt_toolkit import PromptSession
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.completion import (
        CompleteEvent,
        Completer,
        Completion,
        FuzzyCompleter,
        WordCompleter,
    )
    from prompt_toolkit.data_structures import Point
    from prompt_toolkit.document import Document
    from prompt_toolkit.filters import Condition, has_completions, has_focus, is_done
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
    from prompt_toolkit.layout.containers import ConditionalContainer, Float, FloatContainer, HSplit, Window
    from prompt_toolkit.layout.controls import UIContent, UIControl
    from prompt_toolkit.layout.dimension import Dimension
    from prompt_toolkit.layout.menus import CompletionsMenu
    from prompt_toolkit.shortcuts.prompt import CompleteStyle
    from prompt_toolkit.styles import Style
    from prompt_toolkit.utils import get_cwidth
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False
    get_app_or_none = None
    PromptSession = None
    Buffer = None
    CompleteEvent = None
    Completer = None
    Completion = None
    CompleteStyle = None
    WordCompleter = None
    Point = None
    Document = None
    Condition = None
    has_completions = None
    has_focus = None
    is_done = None
    FormattedText = None
    FuzzyCompleter = None
    KeyBindings = None
    KeyPressEvent = None
    ConditionalContainer = None
    Float = None
    FloatContainer = None
    HSplit = None
    Window = None
    UIContent = None
    UIControl = None
    Dimension = None
    CompletionsMenu = None
    get_cwidth = None
    Style = None

# Rich console for beautiful output
console = Console()


def get_prompt_info() -> str:
    """Get current user and path info for prompt display."""
    try:
        username = os.getenv("USERNAME") or os.getenv("USER") or "user"
        cwd = os.getcwd()
        return f"[cyan]{username}[/cyan]@[dim]{cwd}[/dim]"
    except Exception:
        return "[cyan]user[/cyan]@[dim].[/dim]"


def get_prompt_plain_text() -> str:
    """Get current user and path info for prompt_toolkit prompt display."""
    return ""


# Command hints data
QUICK_HINTS = {
    "?": [
        ("exit, quit", "退出 Sun CLI"),
        ("/help", "显示完整帮助"),
        ("/m", "模型命令"),
        ("/clear", "清除历史"),
        ("/history", "输入历史"),
        ("/new", "新对话"),
        ("/next", "中断当前并切下一条"),
        ("/plan", "计划模式"),
        ("/tasks", "任务板"),
        ("!cmd", "执行shell"),
    ],
}

SLASH_COMMANDS = [
    ("/help", "显示帮助信息", "显示帮助信息"),
    ("/m", "显示模型相关命令", "显示模型相关命令"),
    ("/clear", "清除当前对话历史", "清除当前对话历史"),
    ("/new", "开始一个新对话", "开始一个新对话"),
    ("/config", "显示当前配置信息", "显示当前配置信息"),
    ("/history", "显示输入历史", "显示最近的输入历史"),
    ("/history clear", "清除输入历史", "清除所有输入历史"),
    ("/plan", "进入计划模式", "进入计划模式"),
    ("/approve", "批准当前计划", "批准当前计划"),
    ("/modify", "修改当前计划", "修改当前计划"),
    ("/cancel", "取消计划模式", "取消计划模式"),
    ("/tasks", "显示任务板", "显示任务板"),
    ("/team", "显示团队状态", "显示团队状态"),
    ("/task <id> <status>", "更新任务状态", "更新任务状态"),
    ("/next", "中断当前输出并切换到下一条排队消息", "中断当前输出并切换到下一条排队消息"),
    ("/exit", "退出 Sun CLI", "退出 Sun CLI"),
    ("/quit", "退出 Sun CLI", "退出 Sun CLI"),
]

FORCE_NEXT_SIGNAL = "__SUNCLI_FORCE_NEXT__"


class SlashCommandCompleter(Completer):
    """Realtime completer for slash commands."""

    def __init__(self) -> None:
        self._commands = []
        self._lookup = {}
        words = []
        for cmd, cn_desc, _ in SLASH_COMMANDS:
            base_cmd = cmd.split()[0]
            slash_name = base_cmd[1:]
            self._commands.append((base_cmd, cn_desc))
            self._lookup[slash_name] = (base_cmd, cn_desc)
            words.append(slash_name)

        self._word_pattern = re.compile(r"[^\s]+")
        self._word_completer = WordCompleter(words, WORD=False, pattern=self._word_pattern)
        self._fuzzy = FuzzyCompleter(self._word_completer, WORD=False, pattern=r"^[^\s]*")

    @staticmethod
    def should_complete(document: Document) -> bool:
        text = document.text_before_cursor
        if document.text_after_cursor.strip():
            return False

        last_space = text.rfind(" ")
        token = text[last_space + 1:]
        prefix = text[: last_space + 1] if last_space != -1 else ""
        return not prefix.strip() and token.startswith("/")

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        if not self.should_complete(document):
            return

        text = document.text_before_cursor
        last_space = text.rfind(" ")
        token = text[last_space + 1:]
        typed = token[1:]

        if typed and typed in self._lookup:
            return

        fuzzy_doc = Document(text=typed, cursor_position=len(typed))
        seen = set()
        for candidate in self._fuzzy.get_completions(fuzzy_doc, complete_event):
            match = self._lookup.get(candidate.text)
            if not match:
                continue
            base_cmd, cn_desc = match
            if base_cmd in seen:
                continue
            seen.add(base_cmd)
            yield Completion(
                text=base_cmd,
                start_position=-len(token),
                display=base_cmd,
                display_meta=cn_desc,
            )


def _truncate_to_width(text: str, width: int) -> str:
    if width <= 0:
        return ""

    total = 0
    chars = []
    for ch in text:
        ch_width = get_cwidth(ch)
        if total + ch_width > width:
            break
        chars.append(ch)
        total += ch_width

    if total == get_cwidth(text):
        return text + (" " * max(0, width - total))

    ellipsis = "..."
    ellipsis_width = get_cwidth(ellipsis)
    if width <= ellipsis_width:
        return "." * width

    available = width - ellipsis_width
    total = 0
    chars = []
    for ch in text:
        ch_width = get_cwidth(ch)
        if total + ch_width > available:
            break
        chars.append(ch)
        total += ch_width
    return "".join(chars) + ellipsis + (" " * max(0, width - total - ellipsis_width))


class SlashCommandMenuControl(UIControl):
    """Render slash command completions inline below the prompt."""

    _HORIZONTAL_PADDING = 1
    _COLUMN_GAP = 3

    def preferred_width(self, max_available_width: int) -> int | None:
        return max_available_width

    def preferred_height(self, width: int, max_available_height: int, wrap_lines: bool, get_line_prefix) -> int | None:
        app = get_app_or_none()
        complete_state = getattr(app.current_buffer, "complete_state", None) if app else None
        if complete_state is None:
            return 0
        return min(max_available_height, len(complete_state.completions))

    def create_content(self, width: int, height: int) -> UIContent:
        app = get_app_or_none()
        complete_state = getattr(app.current_buffer, "complete_state", None) if app else None
        if complete_state is None or not complete_state.completions:
            return UIContent()

        completions = complete_state.completions[: max(0, height)]
        selected_index = complete_state.complete_index

        usable_width = max(0, width - self._HORIZONTAL_PADDING)
        command_width = min(
            max((get_cwidth(item.display_text) for item in completions), default=16) + 2,
            max(18, usable_width // 4),
        )
        marker_width = 2
        meta_width = max(0, usable_width - marker_width - command_width - self._COLUMN_GAP)

        lines = []
        for index, completion in enumerate(completions):
            is_current = selected_index == index
            marker = "› " if is_current else "  "
            marker_style = "class:slash-menu.current" if is_current else "class:slash-menu"
            command_style = "class:slash-menu.command.current" if is_current else "class:slash-menu.command"
            meta_style = "class:slash-menu.meta.current" if is_current else "class:slash-menu.meta"

            fragments = FormattedText()
            fragments.append(("class:slash-menu", " " * self._HORIZONTAL_PADDING))
            fragments.append((marker_style, marker))
            fragments.append((command_style, _truncate_to_width(completion.display_text, command_width)))
            fragments.append(("class:slash-menu", " " * self._COLUMN_GAP))
            meta_text = _truncate_to_width(completion.display_meta_text, meta_width)
            fragments.append((meta_style, meta_text))
            trailing = max(
                0,
                width
                - self._HORIZONTAL_PADDING
                - marker_width
                - command_width
                - self._COLUMN_GAP
                - get_cwidth(meta_text),
            )
            fragments.append(("class:slash-menu", " " * trailing))
            lines.append(fragments)

        return UIContent(
            get_line=lambda i: lines[i],
            line_count=len(lines),
            cursor_position=Point(x=0, y=0),
        )


def _find_float_container(container) -> Optional[FloatContainer]:
    if isinstance(container, FloatContainer):
        return container

    content = getattr(container, "content", None)
    if content is not None:
        found = _find_float_container(content)
        if found is not None:
            return found

    children = getattr(container, "children", None)
    if children:
        for child in children:
            found = _find_float_container(child)
            if found is not None:
                return found

    return None


def _install_inline_slash_menu(session: PromptSession, completer: SlashCommandCompleter) -> None:
    """Install inline slash command menu below the input line.

    This function modifies the PromptSession layout to display completions
    inline (below the input line) instead of in a floating popup.
    """
    from prompt_toolkit.layout.containers import VSplit

    container = session.layout.container

    float_container = _find_float_container(container)
    if not isinstance(float_container, FloatContainer):
        return

    slash_menu_filter = (
        has_focus(session.default_buffer)
        & has_completions
        & ~is_done
        & Condition(lambda: completer.should_complete(session.default_buffer.document))
    )

    # Create the inline menu container
    inline_menu = ConditionalContainer(
        Window(
            content=SlashCommandMenuControl(),
            dont_extend_height=True,
            height=Dimension(max=10),
            style="class:slash-menu",
        ),
        filter=slash_menu_filter,
    )

    # Get or create the HSplit that contains the input window
    # The default PromptSession layout uses FloatContainer -> HSplit
    if isinstance(float_container.content, HSplit):
        # Add inline menu to existing HSplit (at the end, below input)
        float_container.content.children.append(inline_menu)
    elif isinstance(float_container.content, VSplit):
        # Wrap VSplit in HSplit with menu at the bottom
        old_content = float_container.content
        float_container.content = HSplit([old_content, inline_menu])
    else:
        # For any other layout type, wrap in HSplit
        old_content = float_container.content
        float_container.content = HSplit([old_content, inline_menu])

    # Hide all default floating completion menus - completely disable them
    floats_to_remove = []
    for i, float_ in enumerate(float_container.floats):
        if isinstance(float_.content, CompletionsMenu):
            floats_to_remove.append(i)

    # Remove CompletionsMenu floats (in reverse order to preserve indices)
    for i in reversed(floats_to_remove):
        del float_container.floats[i]


def _create_prompt_key_bindings(session_getter, completer: SlashCommandCompleter):
    """Create key bindings for slash menu behavior."""
    bindings = KeyBindings()

    @bindings.add("enter")
    def _(event: KeyPressEvent) -> None:
        buffer = event.current_buffer
        is_slash = (
            buffer.complete_state
            and buffer.complete_state.completions
            and completer.should_complete(buffer.document)
        )
        if is_slash:
            completion = buffer.complete_state.current_completion or buffer.complete_state.completions[0]
            buffer.apply_completion(completion)
            buffer.validate_and_handle()
            return
        event.app.exit(result=buffer.text)

    @bindings.add("down")
    def _(event: KeyPressEvent) -> None:
        buffer = event.current_buffer
        is_slash = (
            buffer.complete_state
            and buffer.complete_state.completions
            and completer.should_complete(buffer.document)
        )
        if is_slash:
            buffer.complete_next()
            return
        buffer.auto_down()

    @bindings.add("up")
    def _(event: KeyPressEvent) -> None:
        buffer = event.current_buffer
        is_slash = (
            buffer.complete_state
            and buffer.complete_state.completions
            and completer.should_complete(buffer.document)
        )
        if is_slash:
            buffer.complete_previous()
            return
        buffer.auto_up()

    return bindings


def _show_quick_help() -> None:
    """Show quick command hints when user types '?'"""
    from rich.table import Table
    
    table = Table(show_header=True, header_style="bold magenta", border_style="cyan")
    table.add_column("命令", style="cyan", width=20)
    table.add_column("说明", style="green", width=50)
    
    for cmd, desc in QUICK_HINTS["?"]:
        table.add_row(cmd, desc)
    
    console.print(Panel(
        table,
        title="[bold blue]快捷命令提示[/bold blue]",
        border_style="blue"
    ))


def _show_slash_commands() -> None:
    """Show all slash commands with descriptions when user types '/'"""
    from rich.table import Table
    
    table = Table(show_header=True, header_style="bold magenta", border_style="cyan")
    table.add_column("命令", style="cyan", width=20)
    table.add_column("说明", style="green", width=70)
    
    for cmd, cn_desc, en_desc in SLASH_COMMANDS:
        table.add_row(cmd, cn_desc)
    
    console.print(Panel(
        table,
        title="[bold blue]斜杠命令列表[/bold blue] [dim]输入命令后按回车执行[/dim]",
        border_style="blue"
    ))


def _is_interactive() -> bool:
    """Check if running in an interactive terminal."""
    import sys
    return sys.stdin.isatty() and sys.stdout.isatty()


def _get_bottom_toolbar_text(text: str) -> str:
    """Generate bottom toolbar text based on current input."""
    text = text.strip()
    
    # Show hints when typing /
    if text.startswith("/"):
        # Filter matching commands
        search = text[1:]  # Remove the leading /
        matches = []
        for cmd, cn_desc, _ in SLASH_COMMANDS:
            if search.lower() in cmd.lower() or search.lower() in cn_desc.lower():
                matches.append((cmd, cn_desc))
        
        if matches:
            # Format matches for display (limit to 3)
            lines = []
            for i, (cmd, desc) in enumerate(matches[:3]):
                lines.append(f"<b>{cmd}</b> {desc}")
            if len(matches) > 3:
                lines.append(f"... 还有 {len(matches) - 3} 个命令")
            return f"<style bg='#1e293b' fg='#94a3b8'> {' | '.join(lines)} </style>"
        else:
            return "<style bg='#1e293b' fg='#64748b'> 无匹配命令 </style>"
    
    # Show hint for ?
    if text == "?":
        hints = " | ".join([f"<b>{cmd}</b>" for cmd, desc in QUICK_HINTS["?"][:5]])
        return f"<style bg='#1e293b' fg='#94a3b8'> {hints}... </style>"
    
    # Default hint
    return "<style bg='#1e293b' fg='#64748b'> [?]快捷提示 [/]斜杠命令 [Enter]发送 [Ctrl+O]切到下一条 [Ctrl+C]取消 </style>"


async def _get_input_with_hints(prompt_info: str) -> str:
    """Get input with inline slash command menu and history navigation."""
    # Check if we're in an interactive terminal
    if not _is_interactive():
        return _get_input_simple(prompt_info)
    
    try:
        from .input_hints import get_input_with_inline_menu
        from .history import get_history
        
        # Get history instance for up/down navigation
        history = get_history().get_history()
        
        return await get_input_with_inline_menu(
            get_prompt_plain_text(), 
            SLASH_COMMANDS,
            history=history,
        )
    except Exception as e:
        # Fall back to simple input
        return _get_input_simple(prompt_info)


def _get_input_simple(prompt_info: str) -> str:
    """Get input using standard console (fallback when prompt_toolkit not available)."""
    return console.input(f"{prompt_info} > ")


async def get_multiline_input(prompt: str = "You") -> str:
    """Get input from user with real-time command hints.
    
    Press Enter to send. Single-line commands (exit, quit, /help, etc.) are executed immediately.
    Press Ctrl+C to cancel.
    
    Real-time hints (when prompt_toolkit is available):
      - Type '?' to see quick command hints in bottom toolbar
      - Type '/' to see slash commands in bottom toolbar
      - Press Ctrl+O to interrupt current output and switch to next queued message
    """
    prompt_info = get_prompt_plain_text()
    
    try:
        if HAS_PROMPT_TOOLKIT:
            line = await _get_input_with_hints(prompt_info)
        else:
            line = _get_input_simple(prompt_info)
        
        # Handle control signal from prompt_toolkit key bindings
        if line == FORCE_NEXT_SIGNAL:
            return line

        # Handle empty line
        if line == "":
            return ""
        
        # Handle '?' for quick help (show full panel)
        if line.strip() == "?":
            _show_quick_help()
            return ""  # Return empty to continue input loop
        
        # Handle '/' for slash command hints (show full panel)
        if line.strip() == "/":
            _show_slash_commands()
            return ""  # Return empty to continue input loop
        
        # Handle single-line commands - execute immediately
        single_line_commands = ["exit", "quit", "/quit", "/exit", "/help", "/clear", "/new", "/config", "/next"]
        if line.strip().lower() in single_line_commands:
            return line.strip()
        
        # Handle shell commands - execute immediately
        if line.strip().startswith("!"):
            return line.strip()
        
        return line
    except KeyboardInterrupt:
        console.print("\n[dim]Input cancelled.[/dim]")
        return ""
    except EOFError:
        return "exit"

# Create Typer app with invoke_without_command=True
app = typer.Typer(
    name=__app_name__,
    help="A Claude-like CLI tool powered by AI",
    add_completion=True,
    invoke_without_command=True,
)


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"[bold blue]{__app_name__}[/bold blue] version [green]{__version__}[/green]")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version information."
    ),
    debug: bool = typer.Option(
        False, "--debug", "-d",
        help="Enable debug mode with detailed logging."
    ),
) -> None:
    """Sun CLI - A Claude-like CLI tool powered by AI.
    
    Run without any command to start interactive chat mode.
    """
    # Set debug mode if requested - must be done BEFORE any other imports
    if debug:
        os.environ["SUN_LOG_LEVEL"] = "DEBUG"
        console.print("[yellow]Debug mode enabled: Detailed logging will be shown.[/yellow]")
    
    # Initialize logging configuration first
    from .logging_config import get_logger
    logger = get_logger()
    logger.debug("Sun CLI 启动中...")
    
    from .mirror_manager import init_mirrors
    
    # Initialize mirrors (auto-detect China mainland and switch to domestic mirrors)
    init_mirrors(console)
    
    # If no subcommand is invoked, start chat
    if ctx.invoked_subcommand is None:
        asyncio.run(_chat_async())


@app.command()
def config(
    api_key: Optional[str] = typer.Option(
        None, "--api-key", "-k", help="Set API key"
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", "-b", help="Set API base URL (e.g., https://api.moonshot.cn/v1 for Kimi)"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Set default model (e.g., moonshot-v1-128k for Kimi)"
    ),
    auto_confirm: Optional[bool] = typer.Option(
        None, "--yolo", "-y", help="Enable auto-confirm mode (skip all confirmations)"
    ),
    no_confirm: Optional[bool] = typer.Option(
        None, "--no-yolo", help="Disable auto-confirm mode"
    ),
    show_tools: Optional[bool] = typer.Option(
        None, "--show-tools", help="Show tool execution traces in chat"
    ),
    hide_tools: Optional[bool] = typer.Option(
        None, "--hide-tools", help="Hide tool execution traces in chat (default)"
    ),
    show: bool = typer.Option(
        False, "--show", "-s", help="Show current configuration"
    ),
) -> None:
    """Configure Sun CLI settings."""
    cfg = get_config()
    
    if show:
        yolo_status = "[green][OK] 已启用[/green]" if cfg.yolo_mode else "[dim]已禁用[/dim]"
        tool_trace_status = "[green][OK] 已显示[/green]" if cfg.show_tool_traces else "[dim]已隐藏[/dim]"
        console.print(Panel.fit(
            f"[bold]Current Configuration[/bold]\n\n"
            f"API Key: {'[green][OK] Set[/green]' if cfg.is_configured else '[red][X] Not set[/red]'}\n"
            f"Base URL: [cyan]{cfg.base_url}[/cyan]\n"
            f"Model: [cyan]{cfg.model}[/cyan]\n"
            f"Temperature: [cyan]{cfg.temperature}[/cyan]\n"
            f"Auto Confirm (Yolo): {yolo_status}\n"
            f"Tool Traces: {tool_trace_status}",
            title="Sun CLI Config"
        ))
        return
    
    api_related_changed = False
    
    if api_key:
        update_config(api_key=api_key)
        console.print("[green][OK][/green] API key saved successfully!")
        api_related_changed = True
    
    if base_url:
        update_config(base_url=base_url)
        console.print(f"[green][OK][/green] Base URL set to: [cyan]{base_url}[/cyan]")
        api_related_changed = True
    
    if model:
        update_config(model=model)
        console.print(f"[green][OK][/green] Model set to: [cyan]{model}[/cyan]")
        api_related_changed = True
    
    # Test API connection after API-related config changes
    if api_related_changed:
        from .config import test_api_connection
        cfg = get_config(reload=True)
        success, msg = test_api_connection(cfg)
        if success:
            console.print(f"[green][OK][/green] {msg}")
        else:
            console.print(Panel(
                f"[bold yellow]API 连接测试未通过[/bold yellow]\n\n"
                f"{msg}\n\n"
                f"[dim]请检查配置后重试：[/dim]\n"
                f"  [cyan]sun config --show[/cyan]  查看当前配置",
                title="[yellow]配置警告[/yellow]",
                border_style="yellow"
            ))
    
    if auto_confirm is True:
        update_config(auto_confirm=True)
        console.print("[green][OK][/green] 自动确认模式已启用！[/green] 所有操作将直接执行，不再询问确认。")
        console.print("[yellow][!] 警告：此模式下文件修改和Git操作将自动执行，请谨慎使用！[/yellow]")
    
    if no_confirm is True:
        update_config(auto_confirm=False)
        console.print("[green][OK][/green] 自动确认模式已禁用，恢复手动确认。")

    if show_tools is True:
        update_config(show_tool_traces=True)
        console.print("[green][OK][/green] 已启用工具调用过程展示。")

    if hide_tools is True:
        update_config(show_tool_traces=False)
        console.print("[green][OK][/green] 已关闭工具调用过程展示（默认）。")
    
    if (
        not api_key
        and not base_url
        and not model
        and auto_confirm is None
        and no_confirm is None
        and show_tools is None
        and hide_tools is None
        and not show
    ):
        console.print("[yellow]Use --help to see available options[/yellow]")


def _interactive_model_setup() -> None:
    """Interactive model selection and API key configuration."""
    from .models_presets import MODEL_PRESETS

    providers = get_provider_names()

    # Step 1: Show all providers
    console.print(Panel.fit(
        "[bold]请选择模型提供商[/bold]\n",
        title="模型配置",
        border_style="blue"
    ))

    for idx, provider_name in enumerate(providers, 1):
        console.print(f"  [cyan]{idx}.[/cyan] {provider_name}")

    # Get provider selection
    while True:
        choice = Prompt.ask("\n请输入编号选择提供商", default="1")
        try:
            provider_idx = int(choice) - 1
            if 0 <= provider_idx < len(providers):
                selected_provider = providers[provider_idx]
                break
            else:
                console.print("[red]无效的编号，请重新输入[/red]")
        except ValueError:
            console.print("[red]请输入数字编号[/red]")

    # Step 2: Show models for selected provider
    provider_presets = MODEL_PRESETS.get(selected_provider, [])
    if not provider_presets:
        console.print(f"[red]提供商 '{selected_provider}' 没有可用模型[/red]")
        return

    console.print(Panel.fit(
        f"[bold]{selected_provider}[/bold] - 可用模型\n",
        title="选择模型",
        border_style="blue"
    ))

    for idx, preset in enumerate(provider_presets, 1):
        console.print(f"  [cyan]{idx}.[/cyan] [green]{preset.name}[/green]")
        console.print(f"     [dim]模型 ID:[/dim] [yellow]{preset.model_id}[/yellow]")
        console.print(f"     [dim]上下文:[/dim] {preset.context_length}  [dim]价格:[/dim] {preset.pricing}")
        console.print()

    # Get model selection
    while True:
        choice = Prompt.ask("请输入编号选择模型", default="1")
        try:
            model_idx = int(choice) - 1
            if 0 <= model_idx < len(provider_presets):
                selected_preset = provider_presets[model_idx]
                break
            else:
                console.print("[red]无效的编号，请重新输入[/red]")
        except ValueError:
            console.print("[red]请输入数字编号[/red]")

    # Step 3: Input API Key
    console.print(Panel.fit(
        f"[bold]配置 {selected_preset.name}[/bold]\n"
        f"Base URL: [cyan]{selected_preset.base_url}[/cyan]\n"
        f"Model ID: [cyan]{selected_preset.model_id}[/cyan]\n",
        title="API 配置",
        border_style="blue"
    ))

    console.print("[yellow]提示:[/yellow] 输入 API Key 时不会显示字符（安全输入）")
    api_key = getpass.getpass("请输入 API Key: ").strip()

    if not api_key:
        console.print("[red]API Key 不能为空，配置已取消[/red]")
        return

    # Save config
    update_config(api_key=api_key, base_url=selected_preset.base_url, model=selected_preset.model_id)
    console.print("[green][OK][/green] 配置已保存！")

    # Test connection
    console.print("[dim]正在测试 API 连接...[/dim]")
    from .config import test_api_connection
    cfg = get_config(reload=True)
    success, msg = test_api_connection(cfg)
    if success:
        console.print(Panel.fit(
            f"[bold green]API 连接成功！[/bold green]\n\n"
            f"模型: [cyan]{selected_preset.name}[/cyan]\n"
            f"提供商: [cyan]{selected_preset.provider}[/cyan]",
            title="配置完成",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[bold yellow]API 连接测试未通过[/bold yellow]\n\n"
            f"{msg}\n\n"
            f"[dim]请检查 API Key 是否正确，或确认 Key 与平台是否匹配。[/dim]",
            title="[yellow]配置警告[/yellow]",
            border_style="yellow"
        ))

@app.command()
def models(
    list: bool = typer.Option(
        False, "--list", "-l", help="List all available model presets"
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="Filter by provider"
    ),
    set_model: Optional[str] = typer.Option(
        None, "--set", "-s", help="Set model by preset name or model ID"
    ),
    setup: bool = typer.Option(
        False, "--setup", help="Interactive setup: choose model and enter API key"
    ),
) -> None:
    """Manage model presets."""
    cfg = get_config()

    if setup:
        _interactive_model_setup()
        return

    if set_model:
        # Try to find preset by name or model ID
        preset = get_preset_by_model_id(set_model)

        if not preset:
            # Try to find by name
            for p in get_all_presets():
                if p.name.lower() == set_model.lower():
                    preset = p
                    break

        if preset:
            update_config(model=preset.model_id, base_url=preset.base_url)
            console.print(Panel.fit(
                f"[bold]Model Selected:[/bold]\n"
                f"Name: [cyan]{preset.name}[/cyan]\n"
                f"Provider: [cyan]{preset.provider}[/cyan]\n"
                f"Model ID: [cyan]{preset.model_id}[/cyan]\n"
                f"Base URL: [cyan]{preset.base_url}[/cyan]\n"
                f"Context: [cyan]{preset.context_length}[/cyan]\n"
                f"Pricing: [cyan]{preset.pricing}[/cyan]",
                title="Model Preset"
            ))
            console.print("[green][OK][/green] Model configuration saved!")
        else:
            console.print(f"[red]Model preset not found: {set_model}[/red]")
            console.print("[dim]Use --list to see available presets[/dim]")
        return

    # List models
    if provider:
        presets = get_presets_by_provider(provider)
        if not presets:
            console.print(f"[red]Provider not found: {provider}[/red]")
            console.print(f"[dim]Available providers: {', '.join(get_provider_names())}[/dim]")
            return
    else:
        presets = get_all_presets()

    # Display models
    from rich.table import Table

    table = Table(show_header=True, header_style="bold magenta", border_style="cyan")
    table.add_column("Provider", style="cyan", width=15)
    table.add_column("Name", style="green", width=20)
    table.add_column("Model ID", style="yellow", width=25)
    table.add_column("Context", style="blue", width=8)
    table.add_column("Pricing", style="dim", width=20)

    for preset in presets:
        table.add_row(
            preset.provider,
            preset.name,
            preset.model_id,
            preset.context_length,
            preset.pricing,
        )

    console.print(table)

    # Show current model
    current_preset = get_preset_by_model_id(cfg.model)
    if current_preset:
        console.print(f"\n[dim]Current model: [cyan]{current_preset.name}[/cyan] ({current_preset.provider})[/dim]")
    else:
        console.print(f"\n[dim]Current model: [cyan]{cfg.model}[/cyan] (custom)[/dim]")


@app.command()
def prompt(
    list: bool = typer.Option(
        False, "--list", "-l", help="List all prompt files"
    ),
    show: Optional[str] = typer.Option(
        None, "--show", "-s", help="Show a prompt file content"
    ),
    edit: Optional[str] = typer.Option(
        None, "--edit", "-e", help="Edit a prompt file"
    ),
    path: bool = typer.Option(
        False, "--path", "-p", help="Show prompts directory path"
    ),
) -> None:
    """Manage AI prompt files (system.md, identity.md, user.md, etc.)"""
    pm = get_prompt_manager()
    
    if path:
        console.print(f"[dim]Prompts directory:[/dim] [cyan]{pm.prompts_dir}[/cyan]")
        return
    
    if list:
        prompts = pm.list_prompts()
        if prompts:
            console.print(Panel.fit(
                "\n".join(f"[cyan]{p}.md[/cyan]" for p in prompts),
                title="Available Prompts"
            ))
        else:
            console.print("[dim]No prompt files found.[/dim]")
        return
    
    if show:
        content = pm.read_prompt(show)
        if content:
            console.print(Panel(
                content,
                title=f"{show}.md",
                border_style="blue"
            ))
        else:
            console.print(f"[red]Prompt file '{show}.md' not found.[/red]")
        return
    
    if edit:
        import subprocess
        
        # Create file if it doesn't exist
        prompt_path = pm.get_prompt_path(edit)
        if not prompt_path.exists():
            prompt_path.write_text(f"# {edit.title()} Prompt\n\n", encoding="utf-8")
            console.print(f"[green][OK][/green] Created {edit}.md")
        
        # Open with default editor
        editor = os.environ.get("EDITOR", "notepad" if os.name == "nt" else "nano")
        try:
            subprocess.run([editor, str(prompt_path)], check=False)
            console.print(f"[green][OK][/green] Saved {edit}.md")
        except FileNotFoundError:
            console.print(f"[red]Editor '{editor}' not found.[/red]")
            console.print(f"[dim]File location: {prompt_path}[/dim]")
        return
    
    # Default: show current system prompt preview
    system = pm.build_system_prompt()
    console.print(Panel(
        system[:2000] + "..." if len(system) > 2000 else system,
        title="Current System Prompt Preview",
        border_style="green"
    ))
    console.print("\n[dim]Use [cyan]--list[/cyan] to see all prompts, [cyan]--edit <name>[/cyan] to edit[/dim]")


def _clear_api_config() -> None:
    """Clear corrupted API configuration files."""
    from .config import get_api_config_file_path, get_env_file_path
    
    # Remove .api_config file
    api_file = get_api_config_file_path()
    if api_file.exists():
        api_file.unlink()
    
    # Clean API-related lines from .env file
    env_file = get_env_file_path()
    if env_file.exists():
        content = env_file.read_text(encoding="utf-8")
        lines = content.split("\n")
        cleaned = [
            line for line in lines
            if not any(line.startswith(f"{var}=") for var in ("SUN_API_KEY", "SUN_BASE_URL", "SUN_MODEL"))
        ]
        while cleaned and cleaned[-1].strip() == "":
            cleaned.pop()
        env_file.write_text("\n".join(cleaned) + "\n", encoding="utf-8")


async def _chat_async() -> None:
    """Async chat handler - main interactive mode."""
    cfg = get_config()
    
    # Check if configured - if not, enter interactive setup automatically
    if not cfg.is_configured:
        console.print(Panel(
            "[bold yellow]欢迎使用 Sun CLI[/bold yellow]\n\n"
            "检测到尚未配置 API，即将进入交互式配置...",
            title="首次启动",
            border_style="yellow"
        ))
        _interactive_model_setup()
        cfg = get_config(reload=True)
        if not cfg.is_configured:
            console.print("[red]配置未完成，程序退出。[/red]")
            raise typer.Exit(1)
    
    # Create chat session
    try:
        session = ChatSession(console)
    except RuntimeError as e:
        err_msg = str(e)
        # If API key contains non-ASCII chars, auto-clear and enter interactive setup
        if "non-ASCII" in err_msg or "CJK" in err_msg:
            console.print(Panel(
                "[bold yellow]API Key 包含非法字符，配置已损坏[/bold yellow]\n\n"
                "已自动清除损坏的配置，即将进入交互式配置...",
                title="配置错误",
                border_style="yellow"
            ))
            _clear_api_config()
            _interactive_model_setup()
            cfg = get_config(reload=True)
            if not cfg.is_configured:
                console.print("[red]配置未完成，程序退出。[/red]")
                raise typer.Exit(1)
            session = ChatSession(console)
        else:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
    
    # Initialize skill manager with context
    skill_manager = get_skill_manager()
    skill_context = SkillContext(console=console, config=cfg, chat_session=session)
    skill_manager.initialize(skill_context)
    
    # Welcome message
    prompt_info = get_prompt_info()
    console.print(Panel.fit(
        f"[bold blue]欢迎使用 Sun CLI[/bold blue]\n"
        f"[dim]当前目录:[/dim] {prompt_info}\n"
        f"当前模型: [cyan]{cfg.model}[/cyan]\n"
        f"输入 [yellow]/help[/yellow] 查看命令 | 输入 [yellow]?[/yellow] 查看快捷提示 | 输入 [yellow]/[/yellow] 查看斜杠命令 | 输入 [yellow]exit[/yellow] 退出",
        title=f"Sun CLI v{__version__}"
    ))
    
    # Auto-analyze project on startup (only if no AGENTS.md)
    from .context_collector import get_context_collector
    context_collector = get_context_collector(console)
    context_summary = context_collector.collect()
    
    if not context_summary.agents_md_found:
        # No AGENTS.md found - do automatic project analysis
        console.print("\n[dim]正在分析项目...[/dim]")
        try:
            await session.stream_message("简要介绍这个项目", max_tool_iterations=3)
            console.print()
        except Exception as e:
            console.print(f"[dim]项目分析跳过: {e}[/dim]\n")
    
    # Interactive loop
    awaiting_plan_input = False
    awaiting_plan_modify = False
    message_queue: asyncio.Queue[tuple[ChatSession, str]] = asyncio.Queue()
    worker_state: dict[str, Optional[asyncio.Task]] = {"current_task": None}
    all_sessions: list[ChatSession] = [session]

    async def _message_worker() -> None:
        while True:
            item = await message_queue.get()
            if item is None:
                message_queue.task_done()
                break

            target_session, queued_message = item
            task = asyncio.create_task(_handle_message(target_session, queued_message))
            worker_state["current_task"] = task
            try:
                await task
            except asyncio.CancelledError:
                console.print("[yellow]已中断当前输出，切换到下一条排队消息。[/yellow]")
            finally:
                worker_state["current_task"] = None
                message_queue.task_done()

    worker_task = asyncio.create_task(_message_worker())

    try:
        def _print_teammate_outputs():
            """Print any output from background teammates."""
            for sess in all_sessions:
                outputs = sess.team.drain_output()
                for line in outputs:
                    console.print(f"[dim]{line}[/dim]")
        
        while True:
            try:
                # Check teammate outputs before prompting
                _print_teammate_outputs()
                
                # Get user input (multiline)
                user_input = await get_multiline_input()

                # Force switch: interrupt current output and continue with queue
                if user_input == FORCE_NEXT_SIGNAL or user_input.strip().lower() == "/next":
                    current_task = worker_state["current_task"]
                    if current_task and not current_task.done():
                        current_task.cancel()
                    else:
                        console.print("[dim]当前没有正在执行的消息。[/dim]")
                    continue
                
                # Handle empty input
                if not user_input.strip():
                    continue
                
                # Handle exit commands
                if user_input.lower() in ["exit", "quit", "/quit", "/exit"]:
                    console.print("[dim]再见！[/dim]")
                    break
                
                # Handle shell commands (start with !)
                if is_shell_command(user_input):
                    shell_cmd = extract_command(user_input)
                    console.print(f"[dim]$ {shell_cmd}[/dim]")
                    execute_shell_command(shell_cmd, console)
                    continue

                # Handle plan mode input states
                if awaiting_plan_input and not user_input.startswith("/"):
                    awaiting_plan_input = False
                    session.enter_plan_mode(user_input)
                    await message_queue.put((session, user_input))
                    console.print(f"[dim]已加入队列，等待执行（队列: {message_queue.qsize()}）。[/dim]")
                    continue

                if awaiting_plan_modify and not user_input.startswith("/"):
                    awaiting_plan_modify = False
                    await message_queue.put((session, f"Please modify the current plan based on this feedback:\n{user_input}"))
                    console.print(f"[dim]已加入队列，等待执行（队列: {message_queue.qsize()}）。[/dim]")
                    continue
                
                # Check for skill intents
                if await skill_manager.handle(user_input):
                    continue
                
                # Handle built-in commands (start with /)
                if user_input.startswith("/"):
                    parts = user_input.strip().split()
                    if user_input == "/help":
                        _show_help(skill_manager)
                    elif user_input == "/m":
                        _show_model_commands()
                    elif user_input == "/clear":
                        session.clear_history()
                    elif user_input == "/new":
                        session = ChatSession(console)
                        all_sessions.append(session)
                        skill_context = SkillContext(console=console, config=cfg, chat_session=session)
                        skill_manager.initialize(skill_context)
                        console.print("[dim]已开始新对话。[/dim]")
                    elif user_input == "/config":
                        console.print(Panel.fit(
                            f"[bold]Current Configuration[/bold]\n\n"
                            f"API Key: {'[green][OK] Set[/green]' if cfg.is_configured else '[red][X][/red]'}\n"
                            f"Base URL: [cyan]{cfg.base_url}[/cyan]\n"
                            f"Model: [cyan]{cfg.model}[/cyan]\n"
                            f"Temperature: [cyan]{cfg.temperature}[/cyan]",
                            title="Config"
                        ))
                    elif user_input == "/plan":
                        if session.is_in_plan_mode():
                            console.print("[yellow]Already in plan mode.[/yellow]")
                        else:
                            console.print("[cyan]Enter your task to create a plan:[/cyan]")
                            awaiting_plan_input = True
                            awaiting_plan_modify = False
                    elif user_input == "/approve":
                        awaiting_plan_input = False
                        awaiting_plan_modify = False
                        if session.is_in_plan_mode():
                            if session.approve_plan():
                                console.print("[green]计划已批准，开始执行...[/green]")
                            else:
                                console.print("[yellow]当前没有可批准的计划。[/yellow]")
                        else:
                            console.print("[yellow]当前不在计划模式。请先使用 /plan 开始。[/yellow]")
                    elif user_input == "/modify":
                        if session.is_in_plan_mode():
                            console.print("[cyan]Describe the changes you want to make to the plan:[/cyan]")
                            awaiting_plan_modify = True
                            awaiting_plan_input = False
                        else:
                            console.print("[yellow]当前不在计划模式。请先使用 /plan 开始。[/yellow]")
                    elif user_input == "/cancel":
                        awaiting_plan_input = False
                        awaiting_plan_modify = False
                        if session.is_in_plan_mode():
                            session.cancel_plan_mode()
                        else:
                            console.print("[yellow]当前不在计划模式。[/yellow]")
                    elif user_input == "/team":
                        status = session.team.get_status()
                        from rich.table import Table
                        table = Table(show_header=True, header_style="bold", border_style="cyan")
                        table.add_column("属性", style="cyan")
                        table.add_column("值", style="green")
                        table.add_row("Team", status["team_name"])
                        table.add_row("Members", str(status["member_count"]))
                        table.add_row("Active", str(status["active_teammates"]))
                        table.add_row("Running", ", ".join(status["running"]) or "none")
                        table.add_row("Pending Requests", str(status["pending_requests"]))
                        console.print(Panel(
                            table,
                            title="Team Status",
                            border_style="blue"
                        ))
                    elif user_input == "/tasks":
                        console.print(Panel(
                            session.list_tasks_text(),
                            title="Task Board (.tasks)",
                            border_style="cyan"
                        ))
                    elif user_input == "/history":
                        from .history import get_history
                        history = get_history()
                        recent = history.get_recent(limit=20)
                        
                        if not recent:
                            console.print("[dim]没有输入历史[/dim]")
                        else:
                            from rich.table import Table
                            table = Table(show_header=True, header_style="bold", border_style="cyan")
                            table.add_column("#", style="dim", width=4)
                            table.add_column("输入", style="green")
                            
                            for i, entry in enumerate(recent, 1):
                                # Truncate long entries
                                display = entry[:80] + "..." if len(entry) > 80 else entry
                                table.add_row(str(i), display)
                            
                            console.print(Panel(
                                table,
                                title="Input History",
                                border_style="blue"
                            ))
                            console.print("[dim]按 ↑/↓ 键在历史中导航 | /history clear 清除历史[/dim]")
                    elif user_input == "/history clear":
                        from .history import get_history
                        history = get_history()
                        history.clear()
                        console.print("[green]输入历史已清除[/green]")
                    elif len(parts) == 3 and parts[0] == "/task":
                        try:
                            task_id = int(parts[1])
                            status = parts[2]
                            session.update_task_status(task_id, status)
                            console.print(f"[green]Task #{task_id} -> {status}[/green]")
                        except ValueError as e:
                            console.print(f"[red]{e}[/red]")
                    else:
                        console.print(f"[red]未知命令:[/red] {user_input}")
                    continue
                
                # Send message to AI
                await message_queue.put((session, user_input))
                if worker_state["current_task"] is not None:
                    console.print(f"[dim]已加入等待队列（队列: {message_queue.qsize()}）。按 Ctrl+O 或 /next 可切到下一条。[/dim]")
                
            except KeyboardInterrupt:
                console.print("\n[dim]Interrupted. Type 'exit' to quit.[/dim]")
            except EOFError:
                break
    finally:
        # Stop all background teammates
        for sess in all_sessions:
            try:
                sess.team.stop_all()
            except Exception:
                pass
        await message_queue.join()
        await message_queue.put(None)
        await worker_task
        for s in all_sessions:
            try:
                await s.close()
            except Exception:
                pass


async def _handle_message(session: ChatSession, message: str) -> None:
    """Handle sending a message and displaying the response."""
    cfg = get_config()
    
    # Check if API is configured
    if not cfg.is_configured:
        error_panel = Panel(
            "[bold red]API Not Configured[/bold red]\n\n"
            "You need to configure an API key to use AI features.\n\n"
            "[cyan]Run: suncli config --api-key sk-xxx --base-url https://api.moonshot.cn/v1 --model moonshot-v1-128k[/cyan]",
            title="[red]Configuration Required[/red]",
            border_style="red"
        )
        console.print(error_panel)
        return
    
    try:
        # Display user input with border
        console.print(Panel(
            message,
            title="[bold green]You[/bold green]",
            border_style="green"
        ))
        
        # Stream response with live display
        await session.stream_message(message)
        console.print()  # Add newline after response
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


def _show_help(skill_manager) -> None:
    """Show help for chat commands."""
    help_text = f"""[bold]内置命令:[/bold]
  [yellow]exit[/yellow], [yellow]quit[/yellow]  - 退出 Sun CLI
  [yellow]/help[/yellow]        - 显示帮助信息
  [yellow]/m[/yellow]           - 显示模型相关命令
  [yellow]/clear[/yellow]       - 清除对话历史
  [yellow]/new[/yellow]         - 开始新对话
  [yellow]/config[/yellow]      - 显示当前配置
  [yellow]/next[/yellow]        - 中断当前输出并切到下一条排队消息
  [yellow]/tasks[/yellow]       - 显示持久化任务板（.tasks）
  [yellow]/task <id> <status>[/yellow] - 更新任务状态（pending/in_progress/completed）

[bold]快捷提示:[/bold]
  [yellow]?[/yellow]             - 显示快捷命令提示
  [yellow]/[/yellow]             - 显示所有斜杠命令列表
  [yellow]Ctrl+O[/yellow]        - 中断当前输出并切到下一条排队消息

[bold]配置命令:[/bold]
  配置 API 参数:
    [cyan]suncli config --api-key <key>[/cyan]    - 设置 API Key
    [cyan]suncli config --base-url <url>[/cyan]    - 设置 API 基础地址
    [cyan]suncli config --model <model>[/cyan]      - 设置默认模型
    [cyan]suncli config --show[/cyan]              - 显示当前配置

[bold]模型预设:[/bold]
  管理模型预设:
    [cyan]suncli models --list[/cyan]               - 列出所有可用模型预设
    [cyan]suncli models --provider <name>[/cyan]      - 按提供商筛选
    [cyan]suncli models --set <preset>[/cyan]        - 按预设名或模型 ID 设置

  可用提供商: {', '.join(get_provider_names())}

  示例:
    [dim]suncli models --set "GPT-4o"[/dim]
    [dim]suncli models --set "moonshot-v1-128k"[/dim]

{skill_manager.get_help_text()}

[bold]Shell 命令:[/bold]
  [yellow]![command][/yellow]     - 在本地执行 shell 命令
  示例:
    [dim]!dir[/dim]          - 列出文件（Windows）
    [dim]!ls -la[/dim]       - 列出文件（Linux/Mac）
    [dim]!pwd[/dim]          - 显示当前目录
    [dim]!cd ..[/dim]        - 切换目录

[bold]提示词管理:[/bold]
  [dim]编辑提示词文件以定制 AI 行为:[/dim]
    [cyan]suncli prompt --list[/cyan]        - 列出全部提示词
    [cyan]suncli prompt --edit system[/cyan]  - 编辑 system 提示词
    [cyan]suncli prompt --edit identity[/cyan]- 编辑 identity 提示词
    [cyan]suncli prompt --edit user[/cyan]   - 编辑 user 提示词

[bold]使用提示:[/bold]
  - 直接输入文本即可与 AI 对话（无需前缀）
  - 使用 [cyan]Ctrl+C[/cyan] 可中断回答生成
  - 对话历史会持续保留，直到你退出
  - 输入 [yellow]?[/yellow] 查看快捷提示，输入 [yellow]/[/yellow] 查看斜杠命令
"""
    console.print(Panel(help_text, title="帮助", border_style="blue"))


def _show_model_commands() -> None:
    """Show model-related commands."""
    from rich.table import Table
    
    table = Table(show_header=True, header_style="bold magenta", border_style="cyan")
    table.add_column("命令", style="cyan", width=35)
    table.add_column("说明", style="green", width=60)
    
    table.add_row(
        "suncli models --list",
        "列出所有可用的模型预设"
    )
    table.add_row(
        "suncli models --provider <name>",
        "按提供商筛选模型"
    )
    table.add_row(
        "suncli models --set <preset>",
        "设置模型（支持预设名称或模型ID）"
    )
    table.add_row(
        "suncli config --model <model_id>",
        "直接设置模型ID"
    )
    table.add_row(
        "suncli config --base-url <url>",
        "设置 API 基础 URL"
    )
    table.add_row(
        "suncli config --show",
        "显示当前配置"
    )
    
    console.print(Panel(
        table,
        title="[bold]模型相关命令[/bold]",
        border_style="blue"
    ))
    
    # Show current model
    cfg = get_config()
    current_preset = get_preset_by_model_id(cfg.model)
    if current_preset:
        console.print(f"\n[dim]Current model: [cyan]{current_preset.name}[/cyan] ({current_preset.provider})[/dim]")
    else:
        console.print(f"\n[dim]Current model: [cyan]{cfg.model}[/cyan] (custom)[/dim]")


def run() -> None:
    """Entry point for the CLI."""
    app()
