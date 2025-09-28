"""Clipboard service for cross-platform clipboard operations."""

import subprocess
import platform
from typing import Optional, Tuple


class ClipboardService:
    """Service for handling clipboard operations across different platforms."""

    @staticmethod
    def copy_to_clipboard(text: str) -> Tuple[bool, str]:
        """
        Copy text to system clipboard.

        Args:
            text: Text to copy to clipboard

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not text:
            return False, "No text to copy"

        system = platform.system()

        try:
            if system == "Darwin":  # macOS
                process = subprocess.Popen(
                    "pbcopy",
                    stdin=subprocess.PIPE,
                    shell=False
                )
                process.communicate(text.encode('utf-8'))

                if process.returncode == 0:
                    return True, "Successfully copied to clipboard"
                else:
                    return False, "Failed to copy to clipboard"

            elif system == "Linux":
                # Try xclip first, then xsel
                for cmd in [
                    ["xclip", "-selection", "clipboard"],
                    ["xsel", "--clipboard", "--input"]
                ]:
                    try:
                        process = subprocess.Popen(
                            cmd,
                            stdin=subprocess.PIPE,
                            stderr=subprocess.DEVNULL
                        )
                        process.communicate(text.encode('utf-8'))
                        if process.returncode == 0:
                            return True, "Successfully copied to clipboard"
                    except FileNotFoundError:
                        continue

                return False, "Could not copy to clipboard. Install xclip or xsel"

            elif system == "Windows":
                # Windows support using clip.exe (available on Windows 10+)
                try:
                    process = subprocess.Popen(
                        "clip",
                        stdin=subprocess.PIPE,
                        shell=True
                    )
                    process.communicate(text.encode('utf-16le'))
                    if process.returncode == 0:
                        return True, "Successfully copied to clipboard"
                    else:
                        return False, "Failed to copy to clipboard"
                except Exception:
                    return False, "Clipboard copy not available on this Windows version"

            else:
                return False, f"Unsupported platform: {system}"

        except Exception as e:
            return False, f"Error copying to clipboard: {str(e)}"

    @staticmethod
    def paste_from_clipboard() -> Tuple[bool, str]:
        """
        Paste text from system clipboard.

        Returns:
            Tuple of (success: bool, text_or_error_message: str)
        """
        system = platform.system()

        try:
            if system == "Darwin":  # macOS
                result = subprocess.run(
                    "pbpaste",
                    capture_output=True,
                    text=True,
                    shell=False
                )
                if result.returncode == 0:
                    return True, result.stdout
                else:
                    return False, "Failed to paste from clipboard"

            elif system == "Linux":
                # Try xclip first, then xsel
                for cmd in [
                    ["xclip", "-selection", "clipboard", "-out"],
                    ["xsel", "--clipboard", "--output"]
                ]:
                    try:
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            stderr=subprocess.DEVNULL
                        )
                        if result.returncode == 0:
                            return True, result.stdout
                    except FileNotFoundError:
                        continue

                return False, "Could not paste from clipboard. Install xclip or xsel"

            elif system == "Windows":
                # Windows PowerShell method
                try:
                    result = subprocess.run(
                        ["powershell", "-command", "Get-Clipboard"],
                        capture_output=True,
                        text=True,
                        shell=False
                    )
                    if result.returncode == 0:
                        return True, result.stdout
                    else:
                        return False, "Failed to paste from clipboard"
                except Exception:
                    return False, "Clipboard paste not available on this Windows version"

            else:
                return False, f"Unsupported platform: {system}"

        except Exception as e:
            return False, f"Error pasting from clipboard: {str(e)}"