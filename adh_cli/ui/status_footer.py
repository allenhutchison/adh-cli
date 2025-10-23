"""Custom status footer showing environment information and key shortcuts."""

import os
import subprocess
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label


class StatusFooter(Widget):
    """Custom footer displaying CWD, git branch, and key shortcuts."""

    DEFAULT_CSS = """
    StatusFooter {
        dock: bottom;
        height: 1;
        background: $footer-background;
        color: $footer-foreground;
        layout: horizontal;
    }

    StatusFooter > #env-info {
        width: 1fr;
        height: 1;
        padding: 0 1;
        color: $footer-description-foreground;
        background: $footer-description-background;
    }

    StatusFooter > #shortcuts {
        width: auto;
        height: 1;
        layout: horizontal;
    }

    StatusFooter .shortcut-key {
        color: $footer-key-foreground;
        background: $footer-key-background;
        text-style: bold;
        padding: 0 1;
    }

    StatusFooter .shortcut-desc {
        color: $footer-description-foreground;
        background: $footer-description-background;
        padding: 0 1 0 0;
    }

    StatusFooter .shortcut-separator {
        color: $footer-foreground;
        background: $footer-background;
        padding: 0 1;
    }
    """

    current_dir = reactive(os.getcwd())
    """Current working directory."""

    git_branch = reactive("")
    """Current git branch (if in a git repo)."""

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """Initialize the status footer.

        Args:
            name: The name of the widget.
            id: The ID of the widget in the DOM.
            classes: The CSS classes for the widget.
            disabled: Whether the widget is disabled or not.
        """
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._update_git_branch()

    def _update_git_branch(self) -> None:
        """Update the git branch information."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.current_dir,
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode == 0:
                self.git_branch = result.stdout.strip()
            else:
                self.git_branch = ""
        except (
            subprocess.TimeoutExpired,
            FileNotFoundError,
            subprocess.SubprocessError,
        ):
            self.git_branch = ""

    def _format_path(self, path: str) -> str:
        """Format a path for display, replacing home directory with ~.

        Args:
            path: The path to format.

        Returns:
            Formatted path string.
        """
        home = str(Path.home())
        if path.startswith(home):
            return "~" + path[len(home) :]
        return path

    def compose(self) -> ComposeResult:
        """Create child widgets for the status footer."""
        # Left side: Environment info (CWD + git branch)
        yield Label("", id="env-info")

        # Right side: Shortcuts (static, using CSS classes)
        with Horizontal(id="shortcuts"):
            yield Label("^P", classes="shortcut-key")
            yield Label("Command Palette", classes="shortcut-desc")
            yield Label("│", classes="shortcut-separator")
            yield Label("F1", classes="shortcut-key")
            yield Label("Show Keys", classes="shortcut-desc")

    def on_mount(self) -> None:
        """Update the footer when mounted."""
        self._update_env_info()
        # Check git branch every 2 seconds to detect external changes
        self.set_interval(2.0, self._update_git_branch)

    def _update_env_info(self) -> None:
        """Update the environment information display."""
        env_info = self.query_one("#env-info", Label)

        # Format the directory path
        formatted_dir = self._format_path(self.current_dir)

        # Create the display text
        text = Text()
        text.append("📁 ", style="dim")
        text.append(formatted_dir, style="bold")

        # Add git branch if available
        if self.git_branch:
            text.append("  ", style="dim")
            text.append("🌿 ", style="dim")
            text.append(self.git_branch, style="bold cyan")

        env_info.update(text)

    def _watch_current_dir(self, new_dir: str) -> None:
        """React to directory changes.

        Args:
            new_dir: The new current directory.
        """
        self._update_git_branch()
        if self.is_mounted:
            self._update_env_info()

    def _watch_git_branch(self, new_branch: str) -> None:
        """React to git branch changes.

        Args:
            new_branch: The new git branch.
        """
        if self.is_mounted:
            self._update_env_info()
