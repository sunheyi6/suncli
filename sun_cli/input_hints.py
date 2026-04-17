"""Inline slash command menu for Sun CLI."""

from typing import List, Tuple, Optional

# Try to import prompt_toolkit
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.application import get_app_or_none
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.completion import Completer, Completion, CompleteEvent
    from prompt_toolkit.document import Document
    from prompt_toolkit.filters import Condition, has_focus
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.key_binding.key_processor import KeyPressEvent
    from prompt_toolkit.layout import Layout, HSplit, Window, ConditionalContainer
    from prompt_toolkit.layout.controls import UIContent, UIControl, BufferControl, FormattedTextControl
    from prompt_toolkit.layout.dimension import Dimension
    from prompt_toolkit.layout.processors import BeforeInput
    from prompt_toolkit.patch_stdout import patch_stdout
    from prompt_toolkit.styles import Style
    from prompt_toolkit.utils import get_cwidth
    HAS_UI = True
except ImportError:
    HAS_UI = False


class SimpleSlashCompleter(Completer):
    """Simple completer for slash commands."""
    
    def __init__(self, commands: List[Tuple[str, str]]):
        self.commands = commands  # [(command, description), ...]
    
    def get_completions(self, document: Document, complete_event: CompleteEvent):
        text = document.text_before_cursor
        
        # Only complete if starts with /
        if not text.startswith("/"):
            return
        
        # Get search term (without the /)
        search = text[1:].lower()
        
        # Find matches
        for cmd, desc in self.commands:
            if search in cmd.lower() or search in desc.lower():
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display=cmd,
                    display_meta=desc,
                )


class InlineMenuRenderer:
    """Renders inline command menu below the input line."""
    
    def __init__(self, commands: List[Tuple[str, str]], max_items: int = 6):
        self.commands = commands
        self.max_items = max_items
        self.selected_index = 0
        self.current_matches: List[Tuple[str, str]] = []
        self.visible = False
        self.current_text = ""
    
    def update(self, text: str):
        """Update matches based on current input."""
        self.current_text = text
        
        if not text.startswith("/"):
            self.visible = False
            self.current_matches = []
            return
        
        search = text[1:].lower()
        self.current_matches = [
            (cmd, desc) for cmd, desc in self.commands
            if search in cmd.lower() or search in desc.lower()
        ][:self.max_items]
        
        self.visible = bool(self.current_matches)
        
        # Keep selection in bounds
        if self.selected_index >= len(self.current_matches):
            self.selected_index = 0
    
    def move_up(self):
        if self.current_matches:
            self.selected_index = (self.selected_index - 1) % len(self.current_matches)
    
    def move_down(self):
        if self.current_matches:
            self.selected_index = (self.selected_index + 1) % len(self.current_matches)
    
    def get_selected_command(self) -> Optional[str]:
        if self.current_matches and 0 <= self.selected_index < len(self.current_matches):
            return self.current_matches[self.selected_index][0]
        return None
    
    def render(self, width: int) -> List[str]:
        """Render menu lines."""
        if not self.visible or not self.current_matches:
            return []
        
        lines = []
        cmd_width = max(len(cmd) for cmd, _ in self.current_matches) + 2
        desc_width = max(0, width - cmd_width - 4)
        
        for i, (cmd, desc) in enumerate(self.current_matches):
            is_selected = i == self.selected_index
            
            # Truncate description
            display_desc = desc
            if len(desc) > desc_width:
                display_desc = desc[:desc_width-3] + "..."
            
            # Format line
            if is_selected:
                # Selected: highlight background
                line = f"  \033[44m\033[37m{cmd:<{cmd_width}}\033[0m\033[44m {display_desc:<{desc_width}}\033[0m"
            else:
                # Normal: dark background
                line = f"  \033[36m{cmd:<{cmd_width}}\033[0m\033[90m {display_desc}\033[0m"
            
            lines.append(line)
        
        return lines


async def get_input_with_inline_menu(
    prompt: str, 
    commands: List[Tuple[str, str, str]],
    history=None,
) -> str:
    """Get user input with inline slash command menu and history support.
    
    Args:
        prompt: Prompt text to display
        commands: List of (command, chinese_desc, english_desc) tuples
        history: Optional FileHistory instance for up/down navigation
    
    Returns:
        User input string
    """
    if not HAS_UI:
        # Fallback to standard input
        try:
            return input(f"{prompt} > ")
        except (EOFError, KeyboardInterrupt):
            return ""
    
    try:
        # Prepare command list (use chinese description)
        cmd_list = [(cmd, cn_desc) for cmd, cn_desc, _ in commands]
        
        # Create menu renderer
        menu = InlineMenuRenderer(cmd_list)
        
        # Key bindings
        kb = KeyBindings()
        
        # Track if we're navigating the menu
        is_navigating = [False]
        
        @kb.add('up')
        def _(event):
            if menu.visible:
                menu.move_up()
                is_navigating[0] = True
                event.app.invalidate()
            else:
                # Normal history navigation
                buffer = event.app.current_buffer
                buffer.history_backward(count=1)
        
        @kb.add('down')
        def _(event):
            if menu.visible:
                menu.move_down()
                is_navigating[0] = True
                event.app.invalidate()
            else:
                # Normal history navigation
                buffer = event.app.current_buffer
                buffer.history_forward(count=1)
        
        def _persist_history(text: str) -> None:
            """Persist accepted input into prompt history."""
            if history is None:
                return

            value = text.strip()
            if not value:
                return

            try:
                history.append_string(value)
            except Exception:
                # Keep input flow stable even if history persistence fails.
                pass

        @kb.add('enter')
        def _(event):
            buffer = event.app.current_buffer
            if menu.visible:
                # Use selected command
                selected = menu.get_selected_command()
                if selected:
                    buffer.text = selected
                    buffer.cursor_position = len(selected)
            _persist_history(buffer.text)
            event.app.exit(result=buffer.text)
        
        @kb.add('c-c')
        def _(event):
            event.app.exit(result="")
        
        @kb.add('c-d')
        def _(event):
            event.app.exit(result="exit")
        
        @kb.add('c-o')
        def _(event):
            # Force switch to next queued message:
            # interrupt current output and continue with waiting queue.
            event.app.exit(result="__SUNCLI_FORCE_NEXT__")
        
        @kb.add('tab')
        def _(event):
            # Tab to select current item
            if menu.visible:
                selected = menu.get_selected_command()
                if selected:
                    buffer = event.app.current_buffer
                    buffer.text = selected
                    buffer.cursor_position = len(selected)
                    menu.update(selected)
                    is_navigating[0] = True
        
        # Create buffer with change handler and history
        buffer = Buffer(
            multiline=False,
            history=history,  # Enable up/down history navigation
        )
        
        @buffer.on_text_changed.add_handler
        def on_change(_):
            menu.update(buffer.text)
            is_navigating[0] = False  # Reset navigation flag on text change
        
        # Create the application
        from prompt_toolkit.application import Application

        separator_line = FormattedTextControl(
            lambda: [("class:input-separator", "─" * 2000)]
        )
        
        app = Application(
            layout=Layout(
                HSplit([
                    # Upper area (chat history scrolls in terminal output)
                    Window(
                        content=FormattedTextControl(""),
                        height=Dimension(weight=1),
                    ),
                    # Inline slash menu stays above the separator/input area
                    ConditionalContainer(
                        content=Window(
                            content=InlineMenuControl(menu),
                            height=Dimension(max=menu.max_items),
                            style="",
                        ),
                        filter=Condition(lambda: menu.visible),
                    ),
                    # Separator between history and fixed input area
                    Window(
                        content=separator_line,
                        height=Dimension.exact(1),
                        dont_extend_height=True,
                    ),
                    # Input line
                    Window(
                        content=BufferControl(
                            buffer=buffer,
                            input_processors=[
                                BeforeInput(lambda: f"{prompt} > "),
                            ],
                            include_default_input_processors=True,
                        ),
                        height=Dimension.exact(1),
                        style="class:input-line",
                    ),
                ])
            ),
            key_bindings=kb,
            style=Style.from_dict({
                "": "",
                "input-separator": "fg:#475569",
                "input-line": "bg:#020617",
            }),
            mouse_support=False,
        )

        # Run the app
        with patch_stdout(raw=True):
            result = await app.run_async()
        return result if result else ""
        
    except Exception as e:
        # Fallback on error
        try:
            return input(f"{prompt} > ")
        except (EOFError, KeyboardInterrupt):
            return ""


class InlineMenuControl(UIControl):
    """UI Control for rendering the inline menu."""
    
    def __init__(self, menu: InlineMenuRenderer):
        super().__init__()
        self.menu = menu
    
    def preferred_width(self, max_available_width: int):
        return max_available_width
    
    def preferred_height(self, width: int, max_available_height: int, wrap_lines: bool, get_line_prefix):
        if not self.menu.visible:
            return 0
        return len(self.menu.current_matches)
    
    def create_content(self, width: int, height: int) -> UIContent:
        if not self.menu.visible:
            return UIContent()
        
        cmd_width = max(len(cmd) for cmd, _ in self.menu.current_matches) + 2
        desc_width = max(0, width - cmd_width - 4)
        
        lines = []
        for i, (cmd, desc) in enumerate(self.menu.current_matches):
            is_selected = i == self.menu.selected_index
            
            # Truncate description
            display_desc = desc
            if len(desc) > desc_width:
                display_desc = desc[:desc_width-3] + "..."
            display_desc = display_desc.ljust(desc_width)
            
            # Build formatted line
            if is_selected:
                # Selected: blue background
                line = FormattedText([
                    ("", "  "),
                    ("bg:#2563eb fg:#ffffff bold", f"{cmd:<{cmd_width}}"),
                    ("bg:#2563eb fg:#e2e8f0", f" {display_desc}"),
                ])
            else:
                # Normal
                line = FormattedText([
                    ("", "  "),
                    ("fg:#38bdf8 bold", f"{cmd:<{cmd_width}}"),
                    ("fg:#94a3b8", f" {display_desc}"),
                ])
            
            lines.append(line)
        
        return UIContent(
            get_line=lambda i: lines[i] if i < len(lines) else [],
            line_count=len(lines),
        )
