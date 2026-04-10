"""Input history management for Sun CLI."""

from pathlib import Path
from typing import Optional, List

try:
    from prompt_toolkit.history import History, InMemoryHistory
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False
    History = None
    InMemoryHistory = None


class SimpleHistory(History):
    """Simple file-based history for prompt_toolkit."""
    
    def __init__(self, history_file: Path):
        super().__init__()
        self.history_file = Path(history_file)
        self._strings: List[str] = []
        self._load()
    
    def _load(self):
        """Load history from file."""
        if self.history_file.exists():
            try:
                text = self.history_file.read_text(encoding='utf-8')
                # Split by newlines, filter empty lines
                self._strings = [line for line in text.split('\n') if line.strip()]
            except Exception:
                self._strings = []
        else:
            self._strings = []
    
    def load_history_strings(self):
        """Load history strings (newest first)."""
        # Return in reverse order (newest first) like prompt_toolkit expects
        return iter(reversed(self._strings))
    
    def store_string(self, string: str):
        """Store a string in history (called by prompt_toolkit)."""
        # Don't add duplicates of the last entry
        if self._strings and self._strings[-1] == string:
            return
        
        self._strings.append(string)
        
        # Persist to file
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, 'a', encoding='utf-8') as f:
                f.write(string + '\n')
        except Exception:
            pass
    
    def append_string(self, string: str):
        """Append a string to history (manual API)."""
        # Keep prompt_toolkit internal cache (`_loaded_strings`) in sync.
        super().append_string(string)


class InputHistory:
    """Manages input history for the CLI."""
    
    def __init__(self, history_file: Optional[Path] = None):
        """Initialize history manager.
        
        Args:
            history_file: Path to history file. Defaults to ~/.sun-cli/history
        """
        if history_file is None:
            from .config import get_config_dir
            config_dir = get_config_dir()
            history_file = config_dir / "history"
        
        self.history_file = Path(history_file)
        self._history: Optional[SimpleHistory] = None
        
        if HAS_PROMPT_TOOLKIT:
            # Ensure parent directory exists
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            self._history = SimpleHistory(self.history_file)
    
    def get_history(self) -> Optional[SimpleHistory]:
        """Get the History instance for prompt_toolkit."""
        return self._history
    
    def add(self, text: str):
        """Manually add an entry to history."""
        if not text or not text.strip():
            return
        
        if self._history:
            self._history.append_string(text.strip())
    
    def get_recent(self, limit: int = 20) -> List[str]:
        """Get recent history entries.
        
        Args:
            limit: Maximum number of entries
            
        Returns:
            List of recent inputs (oldest first)
        """
        if not self._history:
            return []
        
        # Get all strings and reverse to get chronological order
        strings = list(self._history.load_history_strings())
        strings.reverse()  # Now oldest first
        
        return strings[-limit:] if len(strings) > limit else strings
    
    def clear(self):
        """Clear all history."""
        if self.history_file.exists():
            self.history_file.write_text("", encoding="utf-8")
        if self._history:
            self._history._strings = []
            # Also reset prompt_toolkit's internal loaded cache.
            self._history._loaded_strings = []


# Global history instance
_history_instance: Optional[InputHistory] = None


def get_history() -> InputHistory:
    """Get or create global history instance."""
    global _history_instance
    if _history_instance is None:
        _history_instance = InputHistory()
    return _history_instance
