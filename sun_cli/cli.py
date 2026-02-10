"""Main CLI entry point for Sun CLI."""

import asyncio
import os
from typing import Optional

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


def get_multiline_input(prompt: str = "You") -> str:
    """Get input from user.
    
    Press Enter to send. Single-line commands (exit, quit, /help, etc.) are executed immediately.
    Press Ctrl+C to cancel.
    """
    prompt_info = get_prompt_info()
    
    try:
        line = console.input(f"{prompt_info} > ")
        
        # Handle empty line
        if line == "":
            return ""
        
        # Handle single-line commands - execute immediately
        single_line_commands = ["exit", "quit", "/quit", "/exit", "/help", "/clear", "/new", "/config"]
        if line.strip().lower() in single_line_commands:
            return line.strip()
        
        # Handle shell commands - execute immediately
        if line.strip().startswith("!"):
            return line.strip()
        
        # Display user input with border
        console.print(Panel(
            line,
            title=f"[bold yellow]{prompt}[/bold yellow] - {prompt_info}",
            border_style="yellow",
            padding=(0, 1)
        ))
        
        return line
    except KeyboardInterrupt:
        console.print("\n[dim]Input cancelled.[/dim]")
        return ""

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
) -> None:
    """Sun CLI - A Claude-like CLI tool powered by AI.
    
    Run without any command to start interactive chat mode.
    """
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
    show: bool = typer.Option(
        False, "--show", "-s", help="Show current configuration"
    ),
) -> None:
    """Configure Sun CLI settings."""
    cfg = get_config()
    
    if show:
        console.print(Panel.fit(
            f"[bold]Current Configuration[/bold]\n\n"
            f"API Key: {'[green][OK] Set[/green]' if cfg.is_configured else '[red][X] Not set[/red]'}\n"
            f"Base URL: [cyan]{cfg.base_url}[/cyan]\n"
            f"Model: [cyan]{cfg.model}[/cyan]\n"
            f"Temperature: [cyan]{cfg.temperature}[/cyan]",
            title="Sun CLI Config"
        ))
        return
    
    if api_key:
        update_config(api_key=api_key)
        console.print("[green][OK][/green] API key saved successfully!")
    
    if base_url:
        update_config(base_url=base_url)
        console.print(f"[green][OK][/green] Base URL set to: [cyan]{base_url}[/cyan]")
    
    if model:
        update_config(model=model)
        console.print(f"[green][OK][/green] Model set to: [cyan]{model}[/cyan]")
    
    if not api_key and not base_url and not model and not show:
        console.print("[yellow]Use --help to see available options[/yellow]")


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
) -> None:
    """Manage model presets."""
    cfg = get_config()
    
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


async def _chat_async() -> None:
    """Async chat handler - main interactive mode."""
    cfg = get_config()
    
    # Check if configured
    if not cfg.is_configured:
        console.print(Panel(
            "[bold red]API Key Not Configured[/bold red]\n\n"
            "Please set your OpenAI API key:\n"
            "  [cyan]sun config --api-key <your-key>[/cyan]\n\n"
            "Or set environment variable:\n"
            "  [cyan]export SUN_API_KEY=<your-key>[/cyan]",
            border_style="red"
        ))
        raise typer.Exit(1)
    
    # Create chat session
    try:
        session = ChatSession(console)
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    
    # Initialize skill manager with context
    skill_manager = get_skill_manager()
    skill_context = SkillContext(console=console, config=cfg, chat_session=session)
    skill_manager.initialize(skill_context)
    
    # Welcome message
    prompt_info = get_prompt_info()
    console.print(Panel.fit(
        f"[bold blue]Welcome to Sun CLI[/bold blue]\n"
        f"[dim]Current:[/dim] {prompt_info}\n"
        f"Model: [cyan]{cfg.model}[/cyan]\n"
        f"Type [yellow]/help[/yellow] for commands | [yellow]/m[/yellow] for model commands | [yellow]exit[/yellow] or [yellow]/quit[/yellow] to exit",
        title=f"Sun CLI v{__version__}"
    ))
    
    # Interactive loop
    try:
        while True:
            try:
                # Get user input (multiline)
                user_input = get_multiline_input()
                
                # Handle empty input
                if not user_input.strip():
                    continue
                
                # Handle exit commands
                if user_input.lower() in ["exit", "quit", "/quit", "/exit"]:
                    console.print("[dim]Goodbye![/dim]")
                    break
                
                # Handle shell commands (start with !)
                if is_shell_command(user_input):
                    shell_cmd = extract_command(user_input)
                    console.print(f"[dim]$ {shell_cmd}[/dim]")
                    execute_shell_command(shell_cmd, console)
                    continue
                
                # Check for skill intents
                if await skill_manager.handle(user_input):
                    continue
                
                # Handle built-in commands (start with /)
                if user_input.startswith("/"):
                    if user_input == "/help":
                        _show_help(skill_manager)
                    elif user_input == "/m":
                        _show_model_commands()
                    elif user_input == "/clear":
                        session.clear_history()
                    elif user_input == "/new":
                        session = ChatSession(console)
                        skill_context = SkillContext(console=console, config=cfg, chat_session=session)
                        skill_manager.initialize(skill_context)
                        console.print("[dim]Started a new conversation.[/dim]")
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
                    elif user_input == "/approve":
                        if session.is_in_plan_mode():
                            if session.approve_plan():
                                console.print("[green]Plan approved! Executing...[/green]")
                            else:
                                console.print("[yellow]No plan to approve.[/yellow]")
                        else:
                            console.print("[yellow]Not in plan mode. Use /plan to start.[/yellow]")
                    elif user_input == "/modify":
                        if session.is_in_plan_mode():
                            console.print("[cyan]Describe the changes you want to make to the plan:[/cyan]")
                        else:
                            console.print("[yellow]Not in plan mode. Use /plan to start.[/yellow]")
                    elif user_input == "/cancel":
                        if session.is_in_plan_mode():
                            session.cancel_plan_mode()
                        else:
                            console.print("[yellow]Not in plan mode.[/yellow]")
                    else:
                        console.print(f"[red]Unknown command:[/red] {user_input}")
                    continue
                
                # Send message to AI
                await _handle_message(session, user_input)
                
            except KeyboardInterrupt:
                console.print("\n[dim]Interrupted. Type 'exit' to quit.[/dim]")
            except EOFError:
                break
    finally:
        await session.close()


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
    
    prompt_info = get_prompt_info()
    console.print(f"\n{prompt_info} [bold blue]Sun CLI[/bold blue]")
    
    try:
        # Stream response with live display
        await session.stream_message(message)
        console.print()  # Add newline after response
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


def _show_help(skill_manager) -> None:
    """Show help for chat commands."""
    help_text = f"""[bold]Built-in Commands:[/bold]
  [yellow]exit[/yellow], [yellow]quit[/yellow]  - Exit Sun CLI
  [yellow]/help[/yellow]        - Show this help message
  [yellow]/m[/yellow]           - Show model-related commands
  [yellow]/clear[/yellow]       - Clear conversation history
  [yellow]/new[/yellow]         - Start a new conversation
  [yellow]/config[/yellow]      - Show current configuration

[bold]Configuration:[/bold]
  Configure API settings:
    [cyan]suncli config --api-key <key>[/cyan]    - Set API key
    [cyan]suncli config --base-url <url>[/cyan]    - Set API base URL
    [cyan]suncli config --model <model>[/cyan]      - Set model
    [cyan]suncli config --show[/cyan]              - Show current config

[bold]Model Presets:[/bold]
  Manage model presets:
    [cyan]suncli models --list[/cyan]               - List all available model presets
    [cyan]suncli models --provider <name>[/cyan]      - Filter by provider
    [cyan]suncli models --set <preset>[/cyan]        - Set model by preset name or ID

  Available providers: {', '.join(get_provider_names())}

  Example:
    [dim]suncli models --set "GPT-4o"[/dim]
    [dim]suncli models --set "moonshot-v1-128k"[/dim]

{skill_manager.get_help_text()}

[bold]Shell Commands:[/bold]
  [yellow]![command][/yellow]     - Execute shell command locally
  Examples:
    [dim]!dir[/dim]          - List files (Windows)
    [dim]!ls -la[/dim]       - List files (Linux/Mac)
    [dim]!pwd[/dim]          - Show current directory
    [dim]!cd ..[/dim]        - Change directory

[bold]Prompt Management:[/bold]
  [dim]Edit prompt files to customize AI behavior:[/dim]
    [cyan]suncli prompt --list[/cyan]        - List all prompts
    [cyan]suncli prompt --edit system[/cyan]  - Edit system prompt
    [cyan]suncli prompt --edit identity[/cyan]- Edit AI identity
    [cyan]suncli prompt --edit user[/cyan]   - Edit user context

[bold]Tips:[/bold]
  - Type any message without prefix to chat with AI
  - Use [cyan]Ctrl+C[/cyan] to interrupt response generation
  - Conversation history is maintained until you exit
"""
    console.print(Panel(help_text, title="Help", border_style="blue"))


def _show_model_commands() -> None:
    """Show model-related commands."""
    from rich.table import Table
    
    table = Table(show_header=True, header_style="bold magenta", border_style="cyan")
    table.add_column("Command", style="cyan", width=35)
    table.add_column("Description (CN)", style="green", width=40)
    table.add_column("Description (EN)", style="dim", width=40)
    
    table.add_row(
        "suncli models --list",
        "列出所有可用的模型预设",
        "List all available model presets"
    )
    table.add_row(
        "suncli models --provider <name>",
        "按提供商筛选模型",
        "Filter models by provider"
    )
    table.add_row(
        "suncli models --set <preset>",
        "设置模型（支持预设名称或模型ID）",
        "Set model by preset name or ID"
    )
    table.add_row(
        "suncli config --model <model_id>",
        "直接设置模型ID",
        "Set model ID directly"
    )
    table.add_row(
        "suncli config --base-url <url>",
        "设置API基础URL",
        "Set API base URL"
    )
    table.add_row(
        "suncli config --show",
        "显示当前配置",
        "Show current configuration"
    )
    
    console.print(Panel(
        table,
        title="[bold]Model-Related Commands[/bold]",
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
