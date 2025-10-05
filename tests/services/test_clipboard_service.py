"""Unit tests for the clipboard service."""

import subprocess
from unittest.mock import Mock, patch

from adh_cli.services.clipboard_service import ClipboardService


class TestClipboardServiceCopy:
    """Test cases for copy_to_clipboard functionality."""

    def test_copy_empty_text(self):
        """Test copying empty text returns appropriate error."""
        success, message = ClipboardService.copy_to_clipboard("")
        assert not success
        assert message == "No text to copy"

    @patch("platform.system")
    @patch("subprocess.Popen")
    def test_copy_macos_success(self, mock_popen, mock_platform):
        """Test successful copy on macOS."""
        mock_platform.return_value = "Darwin"

        # Mock successful pbcopy process
        mock_process = Mock()
        mock_process.communicate.return_value = (None, None)
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        success, message = ClipboardService.copy_to_clipboard("test text")

        assert success
        assert message == "Successfully copied to clipboard"
        mock_popen.assert_called_once_with("pbcopy", stdin=subprocess.PIPE, shell=False)
        mock_process.communicate.assert_called_once_with(b"test text")

    @patch("platform.system")
    @patch("subprocess.Popen")
    def test_copy_macos_failure(self, mock_popen, mock_platform):
        """Test failed copy on macOS."""
        mock_platform.return_value = "Darwin"

        # Mock failed pbcopy process
        mock_process = Mock()
        mock_process.communicate.return_value = (None, None)
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        success, message = ClipboardService.copy_to_clipboard("test text")

        assert not success
        assert message == "Failed to copy to clipboard"

    @patch("platform.system")
    @patch("subprocess.Popen")
    def test_copy_linux_xclip_success(self, mock_popen, mock_platform):
        """Test successful copy on Linux using xclip."""
        mock_platform.return_value = "Linux"

        # Mock successful xclip process
        mock_process = Mock()
        mock_process.communicate.return_value = (None, None)
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        success, message = ClipboardService.copy_to_clipboard("test text")

        assert success
        assert message == "Successfully copied to clipboard"
        mock_popen.assert_called_once_with(
            ["xclip", "-selection", "clipboard"],
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

    @patch("platform.system")
    @patch("subprocess.Popen")
    def test_copy_linux_xsel_fallback(self, mock_popen, mock_platform):
        """Test fallback to xsel when xclip is not available on Linux."""
        mock_platform.return_value = "Linux"

        # First call raises FileNotFoundError (xclip not found)
        # Second call succeeds (xsel works)
        mock_process = Mock()
        mock_process.communicate.return_value = (None, None)
        mock_process.returncode = 0

        mock_popen.side_effect = [FileNotFoundError("xclip not found"), mock_process]

        success, message = ClipboardService.copy_to_clipboard("test text")

        assert success
        assert message == "Successfully copied to clipboard"
        assert mock_popen.call_count == 2

        # Check that xsel was called after xclip failed
        second_call_args = mock_popen.call_args_list[1]
        assert second_call_args[0][0] == ["xsel", "--clipboard", "--input"]

    @patch("platform.system")
    @patch("subprocess.Popen")
    def test_copy_linux_no_clipboard_tool(self, mock_popen, mock_platform):
        """Test error when no clipboard tool is available on Linux."""
        mock_platform.return_value = "Linux"

        # Both xclip and xsel raise FileNotFoundError
        mock_popen.side_effect = [
            FileNotFoundError("xclip not found"),
            FileNotFoundError("xsel not found"),
        ]

        success, message = ClipboardService.copy_to_clipboard("test text")

        assert not success
        assert message == "Could not copy to clipboard. Install xclip or xsel"

    @patch("platform.system")
    @patch("subprocess.Popen")
    def test_copy_windows_success(self, mock_popen, mock_platform):
        """Test successful copy on Windows."""
        mock_platform.return_value = "Windows"

        # Mock successful clip.exe process
        mock_process = Mock()
        mock_process.communicate.return_value = (None, None)
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        success, message = ClipboardService.copy_to_clipboard("test text")

        assert success
        assert message == "Successfully copied to clipboard"
        mock_popen.assert_called_once_with("clip", stdin=subprocess.PIPE, shell=True)
        # Windows uses UTF-16LE encoding
        mock_process.communicate.assert_called_once_with("test text".encode("utf-16le"))

    @patch("platform.system")
    @patch("subprocess.Popen")
    def test_copy_windows_failure(self, mock_popen, mock_platform):
        """Test failed copy on Windows."""
        mock_platform.return_value = "Windows"

        # Mock exception when calling clip
        mock_popen.side_effect = Exception("clip.exe not found")

        success, message = ClipboardService.copy_to_clipboard("test text")

        assert not success
        assert "Clipboard copy not available on this Windows version" in message

    @patch("platform.system")
    def test_copy_unsupported_platform(self, mock_platform):
        """Test error on unsupported platform."""
        mock_platform.return_value = "FreeBSD"

        success, message = ClipboardService.copy_to_clipboard("test text")

        assert not success
        assert message == "Unsupported platform: FreeBSD"

    @patch("platform.system")
    @patch("subprocess.Popen")
    def test_copy_with_unicode_text(self, mock_popen, mock_platform):
        """Test copying text with Unicode characters."""
        mock_platform.return_value = "Darwin"

        mock_process = Mock()
        mock_process.communicate.return_value = (None, None)
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        unicode_text = "Hello 世界! 🎉 Émoji"
        success, message = ClipboardService.copy_to_clipboard(unicode_text)

        assert success
        mock_process.communicate.assert_called_once_with(unicode_text.encode("utf-8"))


class TestClipboardServicePaste:
    """Test cases for paste_from_clipboard functionality."""

    @patch("platform.system")
    @patch("subprocess.run")
    def test_paste_macos_success(self, mock_run, mock_platform):
        """Test successful paste on macOS."""
        mock_platform.return_value = "Darwin"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "pasted text"
        mock_run.return_value = mock_result

        success, text = ClipboardService.paste_from_clipboard()

        assert success
        assert text == "pasted text"
        mock_run.assert_called_once_with(
            "pbpaste", capture_output=True, text=True, shell=False
        )

    @patch("platform.system")
    @patch("subprocess.run")
    def test_paste_macos_failure(self, mock_run, mock_platform):
        """Test failed paste on macOS."""
        mock_platform.return_value = "Darwin"

        mock_result = Mock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        success, message = ClipboardService.paste_from_clipboard()

        assert not success
        assert message == "Failed to paste from clipboard"

    @patch("platform.system")
    @patch("subprocess.run")
    def test_paste_linux_xclip_success(self, mock_run, mock_platform):
        """Test successful paste on Linux using xclip."""
        mock_platform.return_value = "Linux"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "pasted text"
        mock_run.return_value = mock_result

        success, text = ClipboardService.paste_from_clipboard()

        assert success
        assert text == "pasted text"
        mock_run.assert_called_once_with(
            ["xclip", "-selection", "clipboard", "-out"],
            capture_output=True,
            text=True,
            stderr=subprocess.DEVNULL,
        )

    @patch("platform.system")
    @patch("subprocess.run")
    def test_paste_linux_xsel_fallback(self, mock_run, mock_platform):
        """Test fallback to xsel when xclip is not available on Linux."""
        mock_platform.return_value = "Linux"

        # First call raises FileNotFoundError (xclip not found)
        # Second call succeeds (xsel works)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "pasted text"

        mock_run.side_effect = [FileNotFoundError("xclip not found"), mock_result]

        success, text = ClipboardService.paste_from_clipboard()

        assert success
        assert text == "pasted text"
        assert mock_run.call_count == 2

    @patch("platform.system")
    @patch("subprocess.run")
    def test_paste_windows_success(self, mock_run, mock_platform):
        """Test successful paste on Windows."""
        mock_platform.return_value = "Windows"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "pasted text"
        mock_run.return_value = mock_result

        success, text = ClipboardService.paste_from_clipboard()

        assert success
        assert text == "pasted text"
        mock_run.assert_called_once_with(
            ["powershell", "-command", "Get-Clipboard"],
            capture_output=True,
            text=True,
            shell=False,
        )

    @patch("platform.system")
    def test_paste_unsupported_platform(self, mock_platform):
        """Test error on unsupported platform."""
        mock_platform.return_value = "FreeBSD"

        success, message = ClipboardService.paste_from_clipboard()

        assert not success
        assert message == "Unsupported platform: FreeBSD"

    @patch("platform.system")
    @patch("subprocess.run")
    def test_paste_exception_handling(self, mock_run, mock_platform):
        """Test exception handling during paste operation."""
        mock_platform.return_value = "Darwin"
        mock_run.side_effect = Exception("Unexpected error")

        success, message = ClipboardService.paste_from_clipboard()

        assert not success
        assert "Error pasting from clipboard" in message
