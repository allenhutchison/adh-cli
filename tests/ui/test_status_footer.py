"""Tests for the StatusFooter widget."""

import os
import subprocess
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from textual.app import App, ComposeResult
from textual.widgets import Label

from adh_cli.ui.status_footer import StatusFooter


class StatusFooterTestApp(App):
    """Test app for StatusFooter."""

    def compose(self) -> ComposeResult:
        yield StatusFooter()


class TestStatusFooter:
    """Test the StatusFooter widget."""

    @pytest.fixture
    async def app(self):
        """Create a test app with StatusFooter."""
        app = StatusFooterTestApp()
        async with app.run_test() as pilot:
            yield pilot

    @pytest.fixture
    def footer(self):
        """Create a StatusFooter instance with git update mocked."""
        with patch("adh_cli.ui.status_footer.StatusFooter._update_git_branch"):
            yield StatusFooter()

    def test_initialization(self, footer):
        """Test StatusFooter initializes with default values."""
        assert footer.current_dir == os.getcwd()
        assert footer.git_branch == "" or isinstance(footer.git_branch, str)

    def test_update_git_branch_success(self):
        """Test git branch detection in a git repository."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "main\n"

        with patch("subprocess.run", return_value=mock_result):
            # Create footer with subprocess already mocked so init doesn't make real calls
            footer = StatusFooter()
            footer._update_git_branch()
            assert footer.git_branch == "main"

    def test_update_git_branch_not_a_repo(self):
        """Test git branch detection when not in a git repository."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            footer = StatusFooter()
            footer._update_git_branch()
            assert footer.git_branch == ""

    def test_update_git_branch_timeout(self):
        """Test git branch detection handles timeout."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 1)):
            footer = StatusFooter()
            footer._update_git_branch()
            assert footer.git_branch == ""

    def test_update_git_branch_file_not_found(self):
        """Test git branch detection when git is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            footer = StatusFooter()
            footer._update_git_branch()
            assert footer.git_branch == ""

    def test_format_path_with_home(self, footer):
        """Test path formatting replaces home directory with ~."""
        home = str(Path.home())
        test_path = f"{home}/projects/test"

        formatted = footer._format_path(test_path)
        assert formatted == "~/projects/test"

    def test_format_path_without_home(self, footer):
        """Test path formatting leaves non-home paths unchanged."""
        test_path = "/tmp/test"

        formatted = footer._format_path(test_path)
        assert formatted == "/tmp/test"

    def test_format_path_exact_home(self, footer):
        """Test path formatting handles exact home directory."""
        home = str(Path.home())

        formatted = footer._format_path(home)
        assert formatted == "~"

    @pytest.mark.asyncio
    async def test_compose_creates_widgets(self, app):
        """Test compose creates the expected child widgets."""
        footer = app.app.query_one(StatusFooter)

        # Check env-info label exists
        env_info = footer.query_one("#env-info", Label)
        assert env_info is not None

        # Check shortcuts container exists
        shortcuts = footer.query_one("#shortcuts")
        assert shortcuts is not None

        # Check shortcut labels exist
        shortcut_keys = footer.query(".shortcut-key")
        assert len(shortcut_keys) == 2  # ^P and F1

        shortcut_descs = footer.query(".shortcut-desc")
        assert len(shortcut_descs) == 2  # Command Palette and Show Keys

    @pytest.mark.asyncio
    async def test_env_info_updates_on_mount(self, app):
        """Test environment info is updated when footer mounts."""
        footer = app.app.query_one(StatusFooter)
        env_info = footer.query_one("#env-info", Label)

        # Should display the formatted current directory
        formatted_path = footer._format_path(os.getcwd())
        content = env_info.render()
        assert formatted_path in str(content)

    @pytest.mark.asyncio
    async def test_watch_current_dir(self, app):
        """Test that changing current_dir triggers update."""
        footer = app.app.query_one(StatusFooter)
        env_info = footer.query_one("#env-info", Label)

        # Change directory
        footer.current_dir = "/tmp"

        # Give it a moment to update
        await app.pause()

        # Directory change should be reflected in displayed content
        content = env_info.render()
        assert "/tmp" in str(content)

    @pytest.mark.asyncio
    async def test_watch_git_branch(self, app):
        """Test that changing git_branch triggers update."""
        footer = app.app.query_one(StatusFooter)
        env_info = footer.query_one("#env-info", Label)

        # Change branch
        footer.git_branch = "feature/test"

        # Give it a moment to update
        await app.pause()

        # Branch change should be reflected in displayed content
        content = env_info.render()
        assert "feature/test" in str(content)

    @pytest.mark.asyncio
    async def test_interval_updates_git_branch(self):
        """Test that git branch update interval is set on mount."""
        app = StatusFooterTestApp()
        with patch.object(StatusFooter, "set_interval") as mock_set_interval:
            async with app.run_test():
                footer = app.query_one(StatusFooter)
                # Verify set_interval was called with 2 second interval
                mock_set_interval.assert_called_once_with(
                    2.0, footer._update_git_branch
                )

    def test_css_classes_defined(self, footer):
        """Test that CSS classes are properly defined."""
        css = footer.DEFAULT_CSS

        # Check key classes are defined
        assert "StatusFooter" in css
        assert "#env-info" in css
        assert "#shortcuts" in css
        assert ".shortcut-key" in css
        assert ".shortcut-desc" in css
        assert ".shortcut-separator" in css

    @pytest.mark.asyncio
    async def test_shortcut_labels_content(self, app):
        """Test that shortcut labels have correct content."""
        footer = app.app.query_one(StatusFooter)

        # Check shortcut keys have correct text
        shortcut_keys = footer.query(".shortcut-key")
        key_texts = [str(label.render()) for label in shortcut_keys]
        assert "^P" in key_texts[0]
        assert "F1" in key_texts[1]

        # Check shortcut descriptions have correct text
        shortcut_descs = footer.query(".shortcut-desc")
        desc_texts = [str(label.render()) for label in shortcut_descs]
        assert "Command Palette" in desc_texts[0]
        assert "Show Keys" in desc_texts[1]
