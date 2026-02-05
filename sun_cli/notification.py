"""Notification and sound effects for Sun CLI."""

import os
import platform
from pathlib import Path
from typing import Optional

from rich.console import Console


class NotificationManager:
    """Manages desktop notifications and sound effects."""
    
    def __init__(self, console: Console):
        self.console = console
        self._sound_enabled = True
        self._notification_enabled = True
        
        # Check if we're in a terminal that supports notifications
        self._is_windows = platform.system() == "Windows"
        self._is_macos = platform.system() == "Darwin"
        self._is_linux = platform.system() == "Linux"
    
    def show_notification(self, title: str, message: str) -> None:
        """Show desktop notification."""
        if not self._notification_enabled:
            return
        
        try:
            if self._is_windows:
                self._show_windows_notification(title, message)
            elif self._is_macos:
                self._show_macos_notification(title, message)
            elif self._is_linux:
                self._show_linux_notification(title, message)
        except Exception as e:
            self.console.print(f"[dim]Notification failed: {e}[/dim]")
    
    def _show_windows_notification(self, title: str, message: str) -> None:
        """Show Windows notification using toast."""
        try:
            import win10toast
            toast = win10toast.ToastNotifier()
            toast.show_toast(
                title=title,
                msg=message,
                duration=3,
                threaded=True
            )
        except ImportError:
            self._show_windows_powershell_notification(title, message)
        except Exception:
            pass
    
    def _show_windows_powershell_notification(self, title: str, message: str) -> None:
        """Show Windows notification using PowerShell."""
        import subprocess
        escaped_title = title.replace('"', '`"')
        escaped_message = message.replace('"', '`"')
        ps_command = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]::new().ShowToastNotification(
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]::new().LoadXml(
                "<toast><visual><binding template='ToastGeneric'><text>{escaped_title}</text><text>{escaped_message}</text></binding></visual></toast>"
            )
        )
        '''
        subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            timeout=2
        )
    
    def _show_macos_notification(self, title: str, message: str) -> None:
        """Show macOS notification."""
        import subprocess
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "{title}"'
        ], capture_output=True, timeout=2)
    
    def _show_linux_notification(self, title: str, message: str) -> None:
        """Show Linux notification using libnotify."""
        import subprocess
        try:
            subprocess.run([
                "notify-send",
                title,
                message
            ], capture_output=True, timeout=2)
        except FileNotFoundError:
            pass
    
    def play_success_sound(self) -> None:
        """Play success sound effect."""
        if not self._sound_enabled:
            return
        
        try:
            if self._is_windows:
                self._play_windows_sound()
            elif self._is_macos:
                self._play_macos_sound()
            elif self._is_linux:
                self._play_linux_sound()
        except Exception as e:
            self.console.print(f"[dim]Sound failed: {e}[/dim]")
    
    def _play_windows_sound(self) -> None:
        """Play Windows system sound."""
        import winsound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    
    def _play_macos_sound(self) -> None:
        """Play macOS system sound."""
        import subprocess
        subprocess.run([
            "afplay",
            "/System/Library/Sounds/Glass.aiff"
        ], capture_output=True, timeout=1)
    
    def _play_linux_sound(self) -> None:
        """Play Linux system sound."""
        import subprocess
        try:
            subprocess.run([
                "paplay",
                "/usr/share/sounds/freedesktop/stereo/complete.oga"
            ], capture_output=True, timeout=1)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            try:
                subprocess.run([
                    "aplay",
                    "/usr/share/sounds/alsa/Front_Center.wav"
                ], capture_output=True, timeout=1)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
    
    def notify_success(self, message: str = "Task completed successfully!") -> None:
        """Show success notification with sound."""
        self.show_notification("Sun CLI", message)
        self.play_success_sound()
    
    def enable_sound(self, enabled: bool = True) -> None:
        """Enable or disable sound effects."""
        self._sound_enabled = enabled
    
    def enable_notification(self, enabled: bool = True) -> None:
        """Enable or disable desktop notifications."""
        self._notification_enabled = enabled


# Global instance
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager(console: Optional[Console] = None) -> NotificationManager:
    """Get or create global notification manager."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager(console or Console())
    return _notification_manager
