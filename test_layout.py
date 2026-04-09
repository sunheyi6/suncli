"""Test script to debug inline menu layout."""

import asyncio
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter, FuzzyCompleter
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.filters import Condition, has_completions, has_focus, is_done
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout.containers import (
    ConditionalContainer, Float, FloatContainer, HSplit, Window, VSplit
)
from prompt_toolkit.layout.controls import UIContent, UIControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style
from prompt_toolkit.utils import get_cwidth
from typing import Iterable, Optional


# Command data
SLASH_COMMANDS = [
    ("/help", "显示帮助信息"),
    ("/clear", "清除当前对话历史"),
    ("/new", "开始一个新对话"),
    ("/config", "显示当前配置信息"),
    ("/plan", "进入计划模式"),
    ("/exit", "退出 Sun CLI"),
]


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


class SlashCommandCompleter:
    """Realtime completer for slash commands."""

    def __init__(self) -> None:
        self._commands = []
        self._lookup = {}
        words = []
        for cmd, cn_desc in SLASH_COMMANDS:
            base_cmd = cmd.split()[0]
            slash_name = base_cmd[1:]
            self._commands.append((base_cmd, cn_desc))
            self._lookup[slash_name] = (base_cmd, cn_desc)
            words.append(slash_name)

        import re
        self._word_pattern = re.compile(r"[^\s]+")
        from prompt_toolkit.completion import WordCompleter
        self._word_completer = WordCompleter(words, WORD=False, pattern=self._word_pattern)
        from prompt_toolkit.completion import FuzzyCompleter
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

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable:
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
        from prompt_toolkit.completion import Completion
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


class SlashCommandMenuControl(UIControl):
    """Render slash command completions inline below the prompt."""

    _HORIZONTAL_PADDING = 1
    _COLUMN_GAP = 3

    def preferred_width(self, max_available_width: int) -> int | None:
        return max_available_width

    def preferred_height(self, width: int, max_available_height: int, wrap_lines: bool, get_line_prefix) -> int | None:
        from prompt_toolkit.application.current import get_app_or_none
        app = get_app_or_none()
        complete_state = getattr(app.current_buffer, "complete_state", None) if app else None
        if complete_state is None:
            return 0
        return min(max_available_height, len(complete_state.completions))

    def create_content(self, width: int, height: int) -> UIContent:
        from prompt_toolkit.application.current import get_app_or_none
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
            marker = "> " if is_current else "  "
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

        from prompt_toolkit.data_structures import Point
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


def _install_inline_slash_menu(session: PromptSession, completer: SlashCommandCompleter) -> None:
    """Install inline slash command menu below the input line."""
    container = session.layout.container

    float_container = _find_float_container(container)
    if not isinstance(float_container, FloatContainer):
        print(f"\n[DEBUG] FloatContainer not found. Container type: {type(container).__name__}")
        return

    print(f"\n[DEBUG] Found FloatContainer. Floats count: {len(float_container.floats)}")

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
    print(f"[DEBUG] float_container.content type: {type(float_container.content).__name__}")
    if isinstance(float_container.content, HSplit):
        # Add inline menu to existing HSplit (at the end, below input)
        float_container.content.children.append(inline_menu)
        print(f"[DEBUG] Added inline_menu to existing HSplit")
    elif isinstance(float_container.content, VSplit):
        # Wrap VSplit in HSplit with menu at the bottom
        old_content = float_container.content
        float_container.content = HSplit([old_content, inline_menu])
        print(f"[DEBUG] Wrapped VSplit in HSplit with inline_menu")
    else:
        # For any other layout type, wrap in HSplit
        old_content = float_container.content
        float_container.content = HSplit([old_content, inline_menu])
        print(f"[DEBUG] Wrapped {type(old_content).__name__} in HSplit with inline_menu")

    # Hide all default floating completion menus - completely disable them
    floats_to_remove = []
    for i, float_ in enumerate(float_container.floats):
        print(f"[DEBUG] Float {i}: {type(float_.content).__name__}")
        if isinstance(float_.content, CompletionsMenu):
            floats_to_remove.append(i)
            print(f"[DEBUG]   -> Will remove CompletionsMenu")

    # Remove CompletionsMenu floats (in reverse order to preserve indices)
    for i in reversed(floats_to_remove):
        del float_container.floats[i]
        print(f"[DEBUG] Removed float {i}")

    print(f"[DEBUG] Remaining floats: {len(float_container.floats)}")


async def main():
    """Main test function."""
    style = Style.from_dict({
        "bottom-toolbar": "bg:#1e293b #94a3b8",
        "completion-menu": "bg:#0f172a #e2e8f0",
        "completion-menu.completion": "bg:#0f172a #e2e8f0",
        "completion-menu.completion.current": "bg:#3b82f6 #ffffff bold",
        "completion-menu.meta.completion": "bg:#0f172a #94a3b8",
        "completion-menu.meta.completion.current": "bg:#3b82f6 #bfdbfe",
        # Inline slash menu styles
        "slash-menu": "bg:#0f172a #e2e8f0",
        "slash-menu.current": "bg:#3b82f6 #ffffff bold",
        "slash-menu.command": "bg:#0f172a #38bdf8 bold",
        "slash-menu.command.current": "bg:#3b82f6 #ffffff bold",
        "slash-menu.meta": "bg:#0f172a #94a3b8",
        "slash-menu.meta.current": "bg:#3b82f6 #bfdbfe",
    })

    slash_completer = SlashCommandCompleter()

    # Create session
    session = PromptSession(
        style=style,
        multiline=False,
        enable_history_search=True,
        completer=slash_completer,
        complete_while_typing=False,
        reserve_space_for_menu=8,
        key_bindings=_create_prompt_key_bindings(lambda: session, slash_completer),
    )

    # Install inline menu
    _install_inline_slash_menu(session, slash_completer)

    # Auto-trigger completion when typing /
    @session.default_buffer.on_text_changed.add_handler
    def on_text_changed(buffer: Buffer) -> None:
        if slash_completer.should_complete(buffer.document):
            buffer.start_completion(select_first=False)

    print("Type '/' to see inline menu, 'exit' to quit")
    while True:
        try:
            result = await session.prompt_async("> ")
            if result.strip().lower() in ["exit", "quit"]:
                break
            print(f"You entered: {result}")
        except KeyboardInterrupt:
            continue
        except EOFError:
            break


if __name__ == "__main__":
    asyncio.run(main())
