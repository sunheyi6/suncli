"""Main CLI entry point for Sun CLI."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from . import __app_name__, __version__
from .chat import ChatSession
from .config import get_config, get_config_dir
from .shell import execute_shell_command, is_shell_command, extract_command
from .prompts import get_prompt_manager
from .smart_git import SmartGitWorkflow

# Rich console for beautiful output
console = Console()

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
    # If no subcommand is invoked, start chat
    if ctx.invoked_subcommand is None:
        asyncio.run(_chat_async())


@app.command()
def config(
    api_key: Optional[str] = typer.Option(
        None, "--api-key", "-k", help="Set OpenAI API key"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Set default model"
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
            f"Model: [cyan]{cfg.model}[/cyan]\n"
            f"Temperature: [cyan]{cfg.temperature}[/cyan]\n"
            f"Base URL: [cyan]{cfg.base_url or 'Default'}[/cyan]",
            title="Sun CLI Config"
        ))
        return
    
    if api_key:
        # Save to .env file
        env_file = get_config_dir() / ".env"
        env_file.write_text(f"SUN_API_KEY={api_key}\n")
        console.print("[green][OK][/green] API key saved successfully!")
    
    if model:
        console.print(f"[green][OK][/green] Model set to: [cyan]{model}[/cyan]")
    
    if not api_key and not model and not show:
        console.print("[yellow]Use --help to see available options[/yellow]")


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
        import os
        
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
    
    # Initialize smart git workflow
    smart_git = SmartGitWorkflow(console, session)
    
    # Welcome message
    console.print(Panel.fit(
        f"[bold blue]Welcome to Sun CLI[/bold blue]\n"
        f"Model: [cyan]{cfg.model}[/cyan]\n"
        f"Type [yellow]/help[/yellow] for commands | [yellow]exit[/yellow] or [yellow]/quit[/yellow] to exit",
        title=f"Sun CLI v{__version__}"
    ))
    
    # Interactive loop
    try:
        while True:
            try:
                # Get user input
                user_input = Prompt.ask("\n[bold green]You[/bold green]")
                
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
                
                # Check for smart git workflow intent
                if await smart_git.handle_intent(user_input):
                    continue
                
                # Handle built-in commands (start with /)
                if user_input.startswith("/"):
                    if user_input == "/help":
                        _show_help()
                    elif user_input == "/clear":
                        session.clear_history()
                    elif user_input == "/new":
                        session = ChatSession(console)
                        smart_git = SmartGitWorkflow(console, session)  # Re-initialize
                        console.print("[dim]Started a new conversation.[/dim]")
                    elif user_input == "/config":
                        console.print(Panel.fit(
                            f"[bold]Current Configuration[/bold]\n\n"
                            f"API Key: {'[green][OK][/green]' if cfg.is_configured else '[red][X][/red]'}\n"
                            f"Model: [cyan]{cfg.model}[/cyan]\n"
                            f"Temperature: [cyan]{cfg.temperature}[/cyan]",
                            title="Config"
                        ))
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
    console.print("\n[bold blue]Sun CLI[/bold blue]")
    
    try:
        # Stream the response with live display
        await session.stream_message(message)
        console.print()  # Add newline after response
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


def _show_help() -> None:
    """Show help for chat commands."""
    help_text = """[bold]Built-in Commands:[/bold]
  [yellow]exit[/yellow], [yellow]quit[/yellow]  - Exit Sun CLI
  [yellow]/help[/yellow]        - Show this help message
  [yellow]/clear[/yellow]       - Clear conversation history
  [yellow]/new[/yellow]         - Start a new conversation
  [yellow]/config[/yellow]      - Show current configuration

[bold]Smart Git Workflow:[/bold]
  Say things like:
    [dim]提交代码[/dim]        - Auto pull, generate commit, push
    [dim]保存并推送[/dim]      - Same as above
    [dim]commit changes[/dim]  - English also works
  
  Workflow:
    1. Pull from remote (with rebase)
    2. Detect and resolve conflicts (interactive)
    3. Stage all changes
    4. AI generates commit message
    5. Commit and push

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


def run() -> None:
    """Entry point for the CLI."""
    app()
