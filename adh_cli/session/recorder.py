"""Session recorder for capturing chat transcripts."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import uuid

from .models import (
    SessionMetadata,
    TranscriptEntry,
    ChatTurn,
    ToolInvocation,
)


class SessionRecorder:
    """Records session transcripts to JSONL files.

    Features:
    - Async buffering for performance
    - JSONL format for easy parsing
    - Automatic session management
    - Export to markdown
    """

    def __init__(
        self,
        session_dir: Optional[Path] = None,
        session_id: Optional[str] = None,
        agent_name: str = "orchestrator",
        buffer_size: int = 10,
    ):
        """Initialize session recorder.

        Args:
            session_dir: Directory to store session files (default: ~/.adh-cli/sessions)
            session_id: Session identifier (generated if not provided)
            agent_name: Name of the agent
            buffer_size: Number of entries to buffer before flushing
        """
        # Set up session directory
        if session_dir is None:
            session_dir = Path.home() / ".adh-cli" / "sessions"
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Initialize session
        self.session_id = session_id or str(uuid.uuid4())
        self.session_file = self.session_dir / f"{self.session_id}.jsonl"

        # Create metadata
        self.metadata = SessionMetadata(
            session_id=self.session_id,
            start_time=datetime.now(),
            agent_name=agent_name,
        )

        # Write metadata as first line
        self._write_line({"type": "metadata", "data": self.metadata.to_dict()})

        # Buffering state
        self.buffer: List[TranscriptEntry] = []
        self.buffer_size = buffer_size
        self._lock = asyncio.Lock()

    def record_chat_turn(
        self, role: str, content: str, agent_name: Optional[str] = None
    ) -> None:
        """Record a chat message.

        Args:
            role: "user" or "ai"
            content: Message content
            agent_name: Optional agent name for delegation
        """
        entry = ChatTurn(
            timestamp=datetime.now(),
            role=role,
            content=content,
            agent_name=agent_name,
        )
        self._add_entry(entry)

    def record_tool_invocation(
        self,
        tool_name: str,
        parameters: dict,
        success: bool,
        result: Optional[str] = None,
        error: Optional[str] = None,
        agent_name: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
    ) -> None:
        """Record a tool invocation.

        Args:
            tool_name: Name of the tool
            parameters: Tool parameters
            success: Whether execution succeeded
            result: Tool result (truncated if long)
            error: Error message if failed
            agent_name: Optional agent name for delegation
            execution_time_ms: Execution time in milliseconds
        """
        # Truncate result if too long
        if result and len(result) > 1000:
            result = result[:1000] + "... (truncated)"

        entry = ToolInvocation(
            timestamp=datetime.now(),
            tool_name=tool_name,
            parameters=parameters,
            success=success,
            result=result,
            error=error,
            agent_name=agent_name,
            execution_time_ms=execution_time_ms,
        )
        self._add_entry(entry)

    def _add_entry(self, entry: TranscriptEntry) -> None:
        """Add entry to buffer and flush if needed.

        Args:
            entry: Transcript entry to add
        """
        self.buffer.append(entry)

        # Flush if buffer is full
        if len(self.buffer) >= self.buffer_size:
            self.flush()

    def flush(self) -> None:
        """Flush buffered entries to disk."""
        if not self.buffer:
            return

        # Write all buffered entries
        for entry in self.buffer:
            self._write_line({"type": "entry", "data": entry.to_dict()})

        self.buffer.clear()

    def _write_line(self, data: dict) -> None:
        """Write a line to the JSONL file.

        Args:
            data: Data to write
        """
        with open(self.session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")

    def close(self) -> None:
        """Close the session and flush remaining entries."""
        # Flush any remaining buffered entries
        self.flush()

        # Update metadata with end time
        self.metadata.end_time = datetime.now()

        # Write final metadata
        self._write_line({"type": "metadata_final", "data": self.metadata.to_dict()})

    def export_markdown(self, output_path: Optional[Path] = None) -> str:
        """Export session to markdown format.

        Args:
            output_path: Optional path to write markdown file

        Returns:
            Markdown content as string
        """
        # Flush any pending entries
        self.flush()

        # Read and parse JSONL
        entries = []
        with open(self.session_file, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                if data["type"] == "entry":
                    entries.append(data["data"])

        # Build markdown
        lines = []
        lines.append(f"# ADH CLI Session: {self.session_id}\n")
        lines.append(
            f"**Started:** {self.metadata.start_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        if self.metadata.end_time:
            lines.append(
                f"**Ended:** {self.metadata.end_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        lines.append(f"**Agent:** {self.metadata.agent_name}\n")
        lines.append("---\n")

        for entry_data in entries:
            entry_type = entry_data["entry_type"]
            timestamp = datetime.fromisoformat(entry_data["timestamp"])
            time_str = timestamp.strftime("%H:%M:%S")

            if entry_type == "chat_turn":
                role = entry_data["role"]
                content = entry_data["content"]
                agent_suffix = ""
                if entry_data.get("agent_name"):
                    agent_suffix = f" ({entry_data['agent_name']})"

                if role == "user":
                    lines.append(f"## [{time_str}] You\n")
                else:
                    lines.append(f"## [{time_str}] AI{agent_suffix}\n")
                lines.append(f"{content}\n")

            elif entry_type == "tool_invocation":
                tool_name = entry_data["tool_name"]
                success = entry_data["success"]
                agent_suffix = ""
                if entry_data.get("agent_name"):
                    agent_suffix = f" (via {entry_data['agent_name']})"

                status = "✅" if success else "❌"
                lines.append(
                    f"### [{time_str}] 🔧 Tool: {tool_name}{agent_suffix} {status}\n"
                )

                # Parameters
                if entry_data.get("parameters"):
                    lines.append("**Parameters:**")
                    for key, value in entry_data["parameters"].items():
                        lines.append(f"- `{key}`: {value}")
                    lines.append("")

                # Result or error
                if success and entry_data.get("result"):
                    lines.append("**Result:**")
                    lines.append(f"```\n{entry_data['result']}\n```\n")
                elif not success and entry_data.get("error"):
                    lines.append("**Error:**")
                    lines.append(f"```\n{entry_data['error']}\n```\n")

        markdown = "\n".join(lines)

        # Write to file if path provided
        if output_path:
            output_path = Path(output_path)
            output_path.write_text(markdown, encoding="utf-8")

        return markdown

    @classmethod
    def load_session(cls, session_file: Path) -> "SessionRecorder":
        """Load an existing session from a JSONL file.

        Args:
            session_file: Path to session file

        Returns:
            SessionRecorder instance

        Raises:
            FileNotFoundError: If session file doesn't exist
        """
        if not session_file.exists():
            raise FileNotFoundError(f"Session file not found: {session_file}")

        # Read metadata from first line
        with open(session_file, "r", encoding="utf-8") as f:
            first_line = f.readline()
            data = json.loads(first_line)
            if data["type"] != "metadata":
                raise ValueError("Invalid session file: missing metadata")

            metadata = SessionMetadata.from_dict(data["data"])

        # Create recorder instance
        recorder = cls(
            session_dir=session_file.parent,
            session_id=metadata.session_id,
            agent_name=metadata.agent_name,
        )
        recorder.metadata = metadata

        return recorder
