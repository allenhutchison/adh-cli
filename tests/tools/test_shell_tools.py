"""Tests for async shell tools."""

import asyncio

import pytest
import tempfile
from pathlib import Path

from adh_cli.tools.shell_tools import (
    read_file,
    write_file,
    list_directory,
    execute_command,
    create_directory,
    delete_file,
    get_file_info,
)


class TestReadFile:
    """Test read_file function."""

    @pytest.mark.asyncio
    async def test_read_file_success(self):
        """Test successful file reading."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content\nLine 2\nLine 3")
            temp_path = f.name

        try:
            content = await read_file(temp_path)
            assert content == "Test content\nLine 2\nLine 3"
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_read_file_with_max_lines(self):
        """Test reading file with line limit."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for i in range(10):
                f.write(f"Line {i}\n")
            temp_path = f.name

        try:
            content = await read_file(temp_path, max_lines=3)
            assert content == "Line 0\nLine 1\nLine 2\n"
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        """Test reading nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            await read_file("/nonexistent/file.txt")

    @pytest.mark.asyncio
    async def test_read_directory_as_file(self):
        """Test reading directory raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="Not a file"):
                await read_file(tmpdir)


class TestWriteFile:
    """Test write_file function."""

    @pytest.mark.asyncio
    async def test_write_file_new(self):
        """Test writing to a new file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"

            result = await write_file(str(file_path), "Test content")

            assert result["success"] is True
            assert result["existed"] is False
            assert result["bytes_written"] > 0

            # Verify content was written
            assert file_path.read_text() == "Test content"

    @pytest.mark.asyncio
    async def test_write_file_overwrite(self):
        """Test overwriting an existing file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Old content")
            temp_path = f.name

        try:
            result = await write_file(temp_path, "New content")

            assert result["success"] is True
            assert result["existed"] is True
            assert result["old_size"] > 0

            # Verify new content
            assert Path(temp_path).read_text() == "New content"
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_write_file_create_dirs(self):
        """Test creating parent directories when writing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "nested" / "dir" / "test.txt"

            result = await write_file(str(file_path), "Content", create_dirs=True)

            assert result["success"] is True
            assert file_path.exists()
            assert file_path.read_text() == "Content"


class TestListDirectory:
    """Test list_directory function."""

    @pytest.mark.asyncio
    async def test_list_directory_success(self):
        """Test listing directory contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files and dirs
            Path(tmpdir, "file1.txt").write_text("content")
            Path(tmpdir, "file2.py").write_text("code")
            Path(tmpdir, "subdir").mkdir()

            result = await list_directory(tmpdir)

            assert result["success"] is True
            assert result["count"] == 3

            # Check items are categorized correctly
            names = [item["name"] for item in result["items"]]
            assert "file1.txt" in names
            assert "file2.py" in names
            assert "subdir" in names

    @pytest.mark.asyncio
    async def test_list_directory_show_hidden(self):
        """Test listing directory with hidden files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create regular and hidden files
            Path(tmpdir, "visible.txt").write_text("content")
            Path(tmpdir, ".hidden").write_text("secret")

            # Without show_hidden
            result = await list_directory(tmpdir, show_hidden=False)
            assert result["count"] == 1

            # With show_hidden
            result = await list_directory(tmpdir, show_hidden=True)
            assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_list_nonexistent_directory(self):
        """Test listing nonexistent directory raises error."""
        with pytest.raises(FileNotFoundError):
            await list_directory("/nonexistent/directory")

    @pytest.mark.asyncio
    async def test_list_file_as_directory(self):
        """Test listing file as directory raises error."""
        with tempfile.NamedTemporaryFile() as f:
            with pytest.raises(NotADirectoryError):
                await list_directory(f.name)


class TestExecuteCommand:
    """Test execute_command function."""

    @pytest.mark.asyncio
    async def test_execute_simple_command(self):
        """Test executing a simple command."""
        result = await execute_command("echo 'Hello World'")

        assert result["success"] is True
        assert result["return_code"] == 0
        assert "Hello World" in result["stdout"]

    @pytest.mark.asyncio
    async def test_execute_with_cwd(self):
        """Test executing command in specific directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await execute_command("pwd", cwd=tmpdir)

            assert result["success"] is True
            assert tmpdir in result["stdout"]

    @pytest.mark.asyncio
    async def test_execute_failing_command(self):
        """Test executing a failing command."""
        result = await execute_command("exit 1")

        assert result["success"] is False
        assert result["return_code"] == 1

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, monkeypatch):
        """Test command timeout without sending OS signals."""
        class DummyProcess:
            def __init__(self):
                self.returncode = None

            async def communicate(self):
                # Simulate a long-running process so wait_for times out
                await asyncio.sleep(5)
                return b"", b""

            def kill(self):
                # No-op kill to avoid OS signal in restricted environments
                self.returncode = -9

            async def wait(self):
                return

        async def fake_create_subprocess_shell(*args, **kwargs):
            return DummyProcess()

        monkeypatch.setattr(
            asyncio, "create_subprocess_shell", fake_create_subprocess_shell
        )

        with pytest.raises(TimeoutError):
            await execute_command("sleep 10", timeout=1)

    @pytest.mark.asyncio
    async def test_execute_nonexistent_cwd(self):
        """Test executing in nonexistent directory."""
        with pytest.raises(FileNotFoundError):
            await execute_command("echo test", cwd="/nonexistent/dir")


class TestCreateDirectory:
    """Test create_directory function."""

    @pytest.mark.asyncio
    async def test_create_directory_simple(self):
        """Test creating a simple directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "newdir"

            result = await create_directory(str(new_dir))

            assert result["success"] is True
            assert result["created"] is True
            assert new_dir.exists()
            assert new_dir.is_dir()

    @pytest.mark.asyncio
    async def test_create_directory_with_parents(self):
        """Test creating directory with parent dirs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "parent" / "child" / "grandchild"

            result = await create_directory(str(new_dir), parents=True)

            assert result["success"] is True
            assert result["created"] is True
            assert new_dir.exists()

    @pytest.mark.asyncio
    async def test_create_existing_directory(self):
        """Test creating already existing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await create_directory(tmpdir)

            assert result["success"] is True
            assert result["created"] is False
            assert "already exists" in result["message"]

    @pytest.mark.asyncio
    async def test_create_directory_file_exists(self):
        """Test creating directory where file exists."""
        with tempfile.NamedTemporaryFile() as f:
            with pytest.raises(FileExistsError):
                await create_directory(f.name)


class TestDeleteFile:
    """Test delete_file function."""

    @pytest.mark.asyncio
    async def test_delete_file_with_confirmation(self):
        """Test deleting file with confirmation."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"content")
            temp_path = f.name

        result = await delete_file(temp_path, confirm=True)

        assert result["success"] is True
        assert result["deleted"] is True
        assert not Path(temp_path).exists()

    @pytest.mark.asyncio
    async def test_delete_file_without_confirmation(self):
        """Test deleting file without confirmation raises error."""
        with tempfile.NamedTemporaryFile() as f:
            with pytest.raises(ValueError, match="Confirmation required"):
                await delete_file(f.name, confirm=False)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file(self):
        """Test deleting nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            await delete_file("/nonexistent/file.txt", confirm=True)

    @pytest.mark.asyncio
    async def test_delete_directory_as_file(self):
        """Test deleting directory as file raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="Not a file"):
                await delete_file(tmpdir, confirm=True)


class TestGetFileInfo:
    """Test get_file_info function."""

    @pytest.mark.asyncio
    async def test_get_file_info(self):
        """Test getting file information."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            f.write(b"test content")
            f.flush()

            info = await get_file_info(f.name)

            assert info["exists"] is True
            assert info["type"] == "file"
            assert info["size"] == 12
            assert info["extension"] == ".txt"
            assert info["is_binary"] is False

    @pytest.mark.asyncio
    async def test_get_directory_info(self):
        """Test getting directory information."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Add some files
            Path(tmpdir, "file1.txt").write_text("content")
            Path(tmpdir, "file2.txt").write_text("content")

            info = await get_file_info(tmpdir)

            assert info["exists"] is True
            assert info["type"] == "directory"
            assert info["item_count"] == 2

    @pytest.mark.asyncio
    async def test_get_binary_file_info(self):
        """Test detecting binary file."""
        with tempfile.NamedTemporaryFile(suffix=".bin") as f:
            # Write binary data with null bytes
            f.write(b"\x00\x01\x02\x03")
            f.flush()

            info = await get_file_info(f.name)

            assert info["is_binary"] is True

    @pytest.mark.asyncio
    async def test_get_nonexistent_file_info(self):
        """Test getting info for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            await get_file_info("/nonexistent/file.txt")
