"""Tests for session recorder."""

import json
import pytest

from adh_cli.session import SessionRecorder


class TestSessionRecorder:
    """Test session recorder functionality."""

    def test_session_initialization(self, tmp_path):
        """Test session recorder initialization."""
        recorder = SessionRecorder(session_dir=tmp_path)

        # Check session file was created
        assert recorder.session_file.exists()
        assert recorder.session_file.parent == tmp_path

        # Check metadata
        assert recorder.metadata.session_id == recorder.session_id
        assert recorder.metadata.start_time is not None
        assert recorder.metadata.agent_name == "orchestrator"

        # Check metadata was written
        with open(recorder.session_file, "r") as f:
            first_line = json.loads(f.readline())
            assert first_line["type"] == "metadata"
            assert first_line["data"]["session_id"] == recorder.session_id

    def test_record_chat_turn(self, tmp_path):
        """Test recording chat turns."""
        recorder = SessionRecorder(session_dir=tmp_path)

        # Record user message
        recorder.record_chat_turn("user", "Hello, AI!")

        # Record AI response
        recorder.record_chat_turn("ai", "Hello! How can I help you?")

        # Flush to disk
        recorder.flush()

        # Read and verify
        entries = []
        with open(recorder.session_file, "r") as f:
            for line in f:
                data = json.loads(line)
                if data["type"] == "entry":
                    entries.append(data["data"])

        assert len(entries) == 2

        # Check user message
        assert entries[0]["entry_type"] == "chat_turn"
        assert entries[0]["role"] == "user"
        assert entries[0]["content"] == "Hello, AI!"

        # Check AI response
        assert entries[1]["entry_type"] == "chat_turn"
        assert entries[1]["role"] == "ai"
        assert entries[1]["content"] == "Hello! How can I help you?"

    def test_record_tool_invocation(self, tmp_path):
        """Test recording tool invocations."""
        recorder = SessionRecorder(session_dir=tmp_path)

        # Record successful tool call
        recorder.record_tool_invocation(
            tool_name="read_file",
            parameters={"file_path": "/test/file.txt"},
            success=True,
            result="File contents here",
        )

        # Record failed tool call
        recorder.record_tool_invocation(
            tool_name="write_file",
            parameters={"file_path": "/test/output.txt", "content": "data"},
            success=False,
            error="Permission denied",
        )

        recorder.flush()

        # Read and verify
        entries = []
        with open(recorder.session_file, "r") as f:
            for line in f:
                data = json.loads(line)
                if data["type"] == "entry":
                    entries.append(data["data"])

        assert len(entries) == 2

        # Check successful tool call
        assert entries[0]["entry_type"] == "tool_invocation"
        assert entries[0]["tool_name"] == "read_file"
        assert entries[0]["success"] is True
        assert entries[0]["result"] == "File contents here"
        assert entries[0]["error"] is None

        # Check failed tool call
        assert entries[1]["entry_type"] == "tool_invocation"
        assert entries[1]["tool_name"] == "write_file"
        assert entries[1]["success"] is False
        assert entries[1]["result"] is None
        assert entries[1]["error"] == "Permission denied"

    def test_buffering(self, tmp_path):
        """Test that entries are buffered and flushed."""
        recorder = SessionRecorder(session_dir=tmp_path, buffer_size=5)

        # Add 3 entries (less than buffer size)
        for i in range(3):
            recorder.record_chat_turn("user", f"Message {i}")

        # Read file - should only have metadata (buffer not flushed)
        entries = []
        with open(recorder.session_file, "r") as f:
            for line in f:
                data = json.loads(line)
                if data["type"] == "entry":
                    entries.append(data["data"])

        assert len(entries) == 0

        # Add 2 more entries (reach buffer size)
        for i in range(3, 5):
            recorder.record_chat_turn("user", f"Message {i}")

        # Buffer should be flushed now
        entries = []
        with open(recorder.session_file, "r") as f:
            for line in f:
                data = json.loads(line)
                if data["type"] == "entry":
                    entries.append(data["data"])

        assert len(entries) == 5

    def test_close_flushes_buffer(self, tmp_path):
        """Test that close() flushes remaining entries."""
        recorder = SessionRecorder(session_dir=tmp_path, buffer_size=10)

        # Add entries (less than buffer size)
        recorder.record_chat_turn("user", "Message 1")
        recorder.record_chat_turn("ai", "Response 1")

        # Close should flush
        recorder.close()

        # Verify entries were written
        entries = []
        with open(recorder.session_file, "r") as f:
            for line in f:
                data = json.loads(line)
                if data["type"] == "entry":
                    entries.append(data["data"])

        assert len(entries) == 2

        # Verify final metadata was written
        with open(recorder.session_file, "r") as f:
            lines = f.readlines()
            last_line = json.loads(lines[-1])
            assert last_line["type"] == "metadata_final"
            assert last_line["data"]["end_time"] is not None

    def test_export_markdown(self, tmp_path):
        """Test exporting session to markdown."""
        recorder = SessionRecorder(session_dir=tmp_path)

        # Add some chat turns and tool calls
        recorder.record_chat_turn("user", "Read the config file")
        recorder.record_chat_turn("ai", "I'll read that for you.")
        recorder.record_tool_invocation(
            tool_name="read_file",
            parameters={"file_path": "/config/settings.yaml"},
            success=True,
            result="key: value",
        )
        recorder.record_chat_turn("ai", "The config contains: key=value")

        # Export to markdown
        md_file = tmp_path / "export.md"
        markdown = recorder.export_markdown(md_file)

        # Verify file was created
        assert md_file.exists()

        # Verify markdown content
        assert f"# ADH CLI Session: {recorder.session_id}" in markdown
        assert "**Started:**" in markdown
        assert "## [" in markdown  # Timestamp
        assert "You" in markdown
        assert "AI" in markdown
        assert "🔧 Tool: read_file" in markdown
        assert "**Parameters:**" in markdown
        assert "`file_path`" in markdown
        assert "**Result:**" in markdown
        assert "key: value" in markdown

    def test_truncate_long_results(self, tmp_path):
        """Test that long results are truncated."""
        recorder = SessionRecorder(session_dir=tmp_path)

        # Create a very long result
        long_result = "x" * 2000

        recorder.record_tool_invocation(
            tool_name="test_tool",
            parameters={},
            success=True,
            result=long_result,
        )

        recorder.flush()

        # Read back and verify truncation
        entries = []
        with open(recorder.session_file, "r") as f:
            for line in f:
                data = json.loads(line)
                if data["type"] == "entry":
                    entries.append(data["data"])

        assert len(entries) == 1
        assert len(entries[0]["result"]) <= 1020  # 1000 + "... (truncated)"
        assert "truncated" in entries[0]["result"]

    def test_delegated_agent_name(self, tmp_path):
        """Test recording agent name for delegated executions."""
        recorder = SessionRecorder(session_dir=tmp_path)

        # Record chat turn from delegated agent
        recorder.record_chat_turn("ai", "Analysis complete", agent_name="code_reviewer")

        # Record tool call from delegated agent
        recorder.record_tool_invocation(
            tool_name="execute_command",
            parameters={"command": "pytest tests/"},
            success=True,
            result="All tests passed",
            agent_name="tester",
        )

        recorder.flush()

        # Verify agent names were recorded
        entries = []
        with open(recorder.session_file, "r") as f:
            for line in f:
                data = json.loads(line)
                if data["type"] == "entry":
                    entries.append(data["data"])

        assert entries[0]["agent_name"] == "code_reviewer"
        assert entries[1]["agent_name"] == "tester"

    def test_load_session(self, tmp_path):
        """Test loading an existing session."""
        # Create a session
        recorder1 = SessionRecorder(session_dir=tmp_path, session_id="test-session-123")
        recorder1.record_chat_turn("user", "Hello")
        recorder1.flush()

        session_file = recorder1.session_file

        # Load the session
        recorder2 = SessionRecorder.load_session(session_file)

        # Verify loaded session matches
        assert recorder2.session_id == "test-session-123"
        assert recorder2.metadata.agent_name == "orchestrator"
        assert recorder2.session_file == session_file

    def test_load_nonexistent_session(self, tmp_path):
        """Test loading a nonexistent session raises error."""
        fake_path = tmp_path / "nonexistent.jsonl"

        with pytest.raises(FileNotFoundError):
            SessionRecorder.load_session(fake_path)
