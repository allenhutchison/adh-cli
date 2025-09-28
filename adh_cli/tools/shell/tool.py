"""Shell command execution tools for the AI agent."""

import subprocess
import os
from typing import Dict, Any, Optional
from pathlib import Path


def execute_command(command: str, working_directory: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
    """Execute a shell command and return the output.

    Args:
        command: The shell command to execute
        working_directory: Optional directory to run the command in
        timeout: Maximum seconds to wait for command completion

    Returns:
        Dictionary with success, stdout, stderr, return_code, and error fields
    """
    result = {
        "success": False,
        "stdout": "",
        "stderr": "",
        "return_code": -1,
        "error": None
    }

    # Safety check: Block potentially dangerous commands
    dangerous_patterns = [
        "rm -rf /",
        "dd if=/dev/zero",
        "mkfs",
        "format",
        "> /dev/sda",
        ":(){ :|:& };:",  # Fork bomb
    ]

    command_lower = command.lower()
    for pattern in dangerous_patterns:
        if pattern.lower() in command_lower:
            result["error"] = f"Command blocked for safety: Contains dangerous pattern '{pattern}'"
            return result

    try:
        # Set working directory
        cwd = working_directory if working_directory else os.getcwd()

        # Run the command
        process = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd
        )

        result["success"] = process.returncode == 0
        result["stdout"] = process.stdout
        result["stderr"] = process.stderr
        result["return_code"] = process.returncode

        if not result["success"] and not result["stderr"]:
            result["error"] = f"Command failed with return code {process.returncode}"

    except subprocess.TimeoutExpired:
        result["error"] = f"Command timed out after {timeout} seconds"
    except FileNotFoundError:
        result["error"] = "Working directory not found"
    except Exception as e:
        result["error"] = f"Error executing command: {str(e)}"

    return result


def list_directory(path: str = ".", show_hidden: bool = False, detailed: bool = True) -> Dict[str, Any]:
    """List contents of a directory with details.

    Args:
        path: Directory path to list
        show_hidden: Whether to show hidden files
        detailed: Whether to show detailed info

    Returns:
        Dictionary with success, path, files, directories, and error fields
    """
    result = {
        "success": False,
        "path": path,
        "files": [],
        "directories": [],
        "error": None
    }

    try:
        dir_path = Path(path).resolve()

        if not dir_path.exists():
            result["error"] = f"Path does not exist: {path}"
            return result

        if not dir_path.is_dir():
            result["error"] = f"Path is not a directory: {path}"
            return result

        for item in dir_path.iterdir():
            # Skip hidden files if not requested
            if not show_hidden and item.name.startswith('.'):
                continue

            item_info = {
                "name": item.name,
                "path": str(item)
            }

            if detailed:
                stat = item.stat()
                item_info["size"] = stat.st_size
                item_info["modified"] = stat.st_mtime

            if item.is_dir():
                result["directories"].append(item_info)
            else:
                result["files"].append(item_info)

        result["success"] = True

    except PermissionError:
        result["error"] = f"Permission denied accessing: {path}"
    except Exception as e:
        result["error"] = f"Error listing directory: {str(e)}"

    return result


def read_file(file_path: str, max_lines: int = 1000) -> Dict[str, Any]:
    """Read the contents of a text file.

    Args:
        file_path: Path to the file to read
        max_lines: Maximum number of lines to read

    Returns:
        Dictionary with success, content, line_count, truncated, and error fields
    """
    result = {
        "success": False,
        "content": "",
        "line_count": 0,
        "truncated": False,
        "error": None
    }

    try:
        file = Path(file_path).resolve()

        if not file.exists():
            result["error"] = f"File does not exist: {file_path}"
            return result

        if not file.is_file():
            result["error"] = f"Path is not a file: {file_path}"
            return result

        # Check file size (limit to 10MB)
        if file.stat().st_size > 10 * 1024 * 1024:
            result["error"] = "File too large (>10MB)"
            return result

        with open(file, 'r', encoding='utf-8') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    result["truncated"] = True
                    break
                lines.append(line)

            result["content"] = ''.join(lines)
            result["line_count"] = len(lines)
            result["success"] = True

    except UnicodeDecodeError:
        result["error"] = "File is not a text file or has encoding issues"
    except PermissionError:
        result["error"] = f"Permission denied reading: {file_path}"
    except Exception as e:
        result["error"] = f"Error reading file: {str(e)}"

    return result