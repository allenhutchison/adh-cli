"""Shell tools for file and command operations."""

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional


async def read_file(file_path: str, max_lines: Optional[int] = None) -> str:
    """Read contents of a text file.

    Args:
        file_path: Path to the file to read
        max_lines: Maximum number of lines to read (optional)

    Returns:
        File contents as string

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file cannot be read
        UnicodeDecodeError: If file is not text
    """
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not path.is_file():
        raise ValueError(f"Not a file: {file_path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            if max_lines:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line)
                return "".join(lines)
            else:
                return f.read()
    except UnicodeDecodeError:
        raise UnicodeDecodeError(
            "utf-8", b"", 0, 1, f"Cannot read binary file as text: {file_path}"
        )


async def write_file(
    file_path: str, content: str, create_dirs: bool = True
) -> Dict[str, Any]:
    """Write content to a file.

    Args:
        file_path: Path to the file to write
        content: Content to write
        create_dirs: Whether to create parent directories if they don't exist

    Returns:
        Dictionary with operation details

    Raises:
        PermissionError: If file cannot be written
    """
    path = Path(file_path).expanduser().resolve()

    # Create parent directories if requested
    if create_dirs and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    # Check if file exists (for backup purposes)
    existed = path.exists()
    old_size = path.stat().st_size if existed else 0

    # Write the file
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    new_size = path.stat().st_size

    return {
        "success": True,
        "file_path": str(path),
        "existed": existed,
        "old_size": old_size,
        "new_size": new_size,
        "bytes_written": new_size,
    }


async def list_directory(
    directory: str = ".", show_hidden: bool = False
) -> Dict[str, Any]:
    """List contents of a directory.

    Args:
        directory: Directory path to list (defaults to current directory)
        show_hidden: Whether to show hidden files (starting with .)

    Returns:
        Dictionary with directory listing

    Raises:
        FileNotFoundError: If directory doesn't exist
        NotADirectoryError: If path is not a directory
    """
    path = Path(directory).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    items = []
    for item in sorted(path.iterdir()):
        # Skip hidden files if not requested
        if not show_hidden and item.name.startswith("."):
            continue

        item_info = {
            "name": item.name,
            "type": "directory" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else None,
        }

        # Add file extension for files
        if item.is_file():
            item_info["extension"] = item.suffix

        items.append(item_info)

    return {
        "success": True,
        "directory": str(path),
        "count": len(items),
        "items": items,
    }


async def execute_command(
    command: str,
    cwd: Optional[str] = None,
    timeout: Optional[int] = 300,
    shell: bool = True,
) -> Dict[str, Any]:
    """Execute a shell command.

    Args:
        command: Command to execute
        cwd: Working directory for command execution
        timeout: Timeout in seconds (default 300 / 5 minutes)
        shell: Whether to use shell execution (default True)

    Returns:
        Dictionary with command output and status

    Raises:
        TimeoutError: If command exceeds timeout
        subprocess.CalledProcessError: If command fails
    """
    # Prepare execution environment
    env = os.environ.copy()

    # Set working directory
    if cwd:
        cwd = Path(cwd).expanduser().resolve()
        if not cwd.exists():
            raise FileNotFoundError(f"Working directory not found: {cwd}")

    try:
        # Run command asynchronously
        if shell:
            # Shell execution (supports pipes, redirects, etc.)
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
        else:
            # Direct execution (safer but less flexible)
            import shlex

            cmd_parts = shlex.split(command)
            process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

        # Wait for completion with timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise TimeoutError(f"Command timed out after {timeout} seconds")

        # Decode output
        stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""

        return {
            "success": process.returncode == 0,
            "command": command,
            "return_code": process.returncode,
            "stdout": stdout_text,
            "stderr": stderr_text,
            "cwd": str(cwd) if cwd else os.getcwd(),
        }

    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "command": command,
            "return_code": e.returncode,
            "stdout": e.stdout.decode("utf-8", errors="replace") if e.stdout else "",
            "stderr": e.stderr.decode("utf-8", errors="replace") if e.stderr else "",
            "error": str(e),
        }


async def create_directory(directory: str, parents: bool = True) -> Dict[str, Any]:
    """Create a directory.

    Args:
        directory: Directory path to create
        parents: Whether to create parent directories if they don't exist

    Returns:
        Dictionary with operation details

    Raises:
        FileExistsError: If directory already exists
        PermissionError: If directory cannot be created
    """
    path = Path(directory).expanduser().resolve()

    if path.exists():
        if path.is_dir():
            return {
                "success": True,
                "directory": str(path),
                "created": False,
                "message": "Directory already exists",
            }
        else:
            raise FileExistsError(f"Path exists but is not a directory: {directory}")

    # Create the directory
    path.mkdir(parents=parents, exist_ok=False)

    return {
        "success": True,
        "directory": str(path),
        "created": True,
        "message": "Directory created successfully",
    }


async def delete_file(file_path: str, confirm: bool = False) -> Dict[str, Any]:
    """Delete a file.

    Args:
        file_path: Path to the file to delete
        confirm: Safety confirmation flag (must be True to delete)

    Returns:
        Dictionary with operation details

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file cannot be deleted
        ValueError: If confirmation not provided
    """
    if not confirm:
        raise ValueError("Confirmation required for file deletion (set confirm=True)")

    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not path.is_file():
        raise ValueError(f"Not a file: {file_path}")

    # Get file info before deletion
    file_size = path.stat().st_size

    # Delete the file
    path.unlink()

    return {
        "success": True,
        "file_path": str(path),
        "deleted": True,
        "file_size": file_size,
        "message": f"File deleted: {file_path}",
    }


async def get_file_info(file_path: str) -> Dict[str, Any]:
    """Get information about a file or directory.

    Args:
        file_path: Path to the file or directory

    Returns:
        Dictionary with file/directory information

    Raises:
        FileNotFoundError: If path doesn't exist
    """
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"Path not found: {file_path}")

    stat = path.stat()

    info = {
        "path": str(path),
        "name": path.name,
        "exists": True,
        "type": "directory" if path.is_dir() else "file",
        "size": stat.st_size,
        "modified": stat.st_mtime,
        "created": stat.st_ctime,
        "permissions": oct(stat.st_mode)[-3:],
    }

    if path.is_file():
        info["extension"] = path.suffix
        info["is_binary"] = _is_binary(path)

    if path.is_dir():
        info["item_count"] = len(list(path.iterdir()))

    return info


def _is_binary(file_path: Path) -> bool:
    """Check if a file is binary.

    Args:
        file_path: Path to check

    Returns:
        True if file appears to be binary
    """
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            # Check for null bytes
            return b"\x00" in chunk
    except Exception:
        return False
