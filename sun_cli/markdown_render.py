"""Enhanced Markdown rendering with syntax highlighting for code blocks."""

import re
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text


class CodeBlock:
    """Represents a code block in markdown."""
    
    def __init__(self, language: str, code: str):
        self.language = language or "text"
        self.code = code
    
    def to_rich(self) -> Panel:
        """Convert to Rich renderable with syntax highlighting."""
        # Map common language aliases
        lang_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "sh": "bash",
            "shell": "bash",
            "zsh": "bash",
            "yml": "yaml",
            "": "text",
        }
        
        syntax_lang = lang_map.get(self.language.lower(), self.language.lower())
        
        # Create syntax highlighted code
        syntax = Syntax(
            self.code,
            syntax_lang,
            theme="monokai",
            line_numbers=False,
            word_wrap=True,
            padding=(1, 2),
        )
        
        # Create header with language and copy hint
        header_text = f"📋 {self.language.upper() if self.language else 'CODE'}"
        
        return Panel(
            syntax,
            title=f"[bold cyan]{header_text}[/bold cyan]",
            title_align="left",
            border_style="cyan",
            subtitle="[dim]💡 选中复制 / Select to copy[/dim]",
            subtitle_align="right",
            padding=(0, 0),
        )


class EnhancedMarkdown:
    """Enhanced markdown renderer with better code block support."""
    
    CODE_BLOCK_PATTERN = re.compile(
        r'```(\w*)\n(.*?)```',
        re.DOTALL
    )
    
    def __init__(self, content: str):
        self.content = content
        self.parts = self._parse()
    
    def _parse(self) -> list:
        """Parse content into parts (text or code blocks)."""
        parts = []
        last_end = 0
        
        for match in self.CODE_BLOCK_PATTERN.finditer(self.content):
            # Add text before code block
            if match.start() > last_end:
                text_part = self.content[last_end:match.start()]
                if text_part.strip():
                    parts.append(("text", text_part))
            
            # Add code block
            language = match.group(1)
            code = match.group(2)
            parts.append(("code", CodeBlock(language, code)))
            
            last_end = match.end()
        
        # Add remaining text
        if last_end < len(self.content):
            text_part = self.content[last_end:]
            if text_part.strip():
                parts.append(("text", text_part))
        
        return parts
    
    def __rich__(self):
        """Render as Rich console output."""
        renderables = []
        
        for part_type, part_content in self.parts:
            if part_type == "text":
                renderables.append(Markdown(part_content))
            elif part_type == "code":
                renderables.append(part_content.to_rich())
        
        return Group(*renderables)
    
    def __str__(self) -> str:
        return self.content


def render_content(content: str, console: Console) -> None:
    """Render content with enhanced code blocks."""
    enhanced = EnhancedMarkdown(content)
    console.print(enhanced)


# Simple inline code formatter for CLI responses
def format_inline_code(text: str) -> str:
    """Format inline code in text."""
    # Replace `code` with styled version
    pattern = r'`([^`]+)`'
    
    def replace_code(match):
        code = match.group(1)
        return f"[bold yellow]`{code}`[/bold yellow]"
    
    return re.sub(pattern, replace_code, text)


def create_command_block(commands: list[str], description: str = "") -> Panel:
    """Create a command block with copy hint."""
    content = "\n".join(commands)
    
    syntax = Syntax(
        content,
        "bash",
        theme="monokai",
        line_numbers=False,
        word_wrap=True,
        padding=(1, 2),
    )
    
    title = "[bold green]⌨️  COMMAND[/bold green]"
    if description:
        title = f"[bold green]⌨️  {description.upper()}[/bold green]"
    
    return Panel(
        syntax,
        title=title,
        title_align="left",
        border_style="green",
        subtitle="[dim]📋 点击复制 / Click to copy[/dim]",
        subtitle_align="right",
        padding=(0, 0),
    )
