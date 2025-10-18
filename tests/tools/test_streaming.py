"""Tests for streaming output functionality."""

import pytest
from adh_cli.tools.shell_tools import execute_command


class TestStreamingOutput:
    """Test streaming output callback for execute_command."""

    @pytest.mark.asyncio
    async def test_execute_command_calls_streaming_callback(self):
        """Test that execute_command calls the on_output callback."""
        # Track callback invocations
        callback_calls = []

        async def on_output(stream_name: str, data: str):
            callback_calls.append((stream_name, data))

        # Execute a simple command that produces output
        result = await execute_command(
            "echo 'Line 1'; echo 'Line 2'", on_output=on_output
        )

        # Verify command succeeded
        assert result["success"] is True
        assert result["return_code"] == 0

        # Verify callback was called
        assert len(callback_calls) > 0

        # Verify we got stdout callbacks
        stdout_calls = [call for call in callback_calls if call[0] == "stdout"]
        assert len(stdout_calls) > 0

        # Verify output was captured correctly
        all_output = "".join(data for _, data in stdout_calls)
        assert "Line 1" in all_output
        assert "Line 2" in all_output

    @pytest.mark.asyncio
    async def test_execute_command_without_callback(self):
        """Test that execute_command works without callback (backward compatible)."""
        result = await execute_command("echo 'Hello'")

        assert result["success"] is True
        assert result["return_code"] == 0
        assert "Hello" in result["stdout"]

    @pytest.mark.asyncio
    async def test_execute_command_streams_stderr(self):
        """Test that stderr is also streamed."""
        callback_calls = []

        async def on_output(stream_name: str, data: str):
            callback_calls.append((stream_name, data))

        # Execute command that writes to stderr
        await execute_command("echo 'error message' >&2", on_output=on_output)

        # Verify callback received stderr
        stderr_calls = [call for call in callback_calls if call[0] == "stderr"]
        assert len(stderr_calls) > 0

        # Verify stderr content
        stderr_output = "".join(data for _, data in stderr_calls)
        assert "error message" in stderr_output

    @pytest.mark.asyncio
    async def test_execute_command_final_result_includes_all_output(self):
        """Test that final result includes all streamed output."""
        callback_lines = []

        async def on_output(stream_name: str, data: str):
            callback_lines.append(data)

        result = await execute_command(
            "echo 'Line 1'; echo 'Line 2'; echo 'Line 3'", on_output=on_output
        )

        # Verify final result has all output
        assert "Line 1" in result["stdout"]
        assert "Line 2" in result["stdout"]
        assert "Line 3" in result["stdout"]

        # Verify streaming gave us the same output
        streamed_output = "".join(callback_lines)
        assert result["stdout"] == streamed_output
