"""Data models for session transcripts."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import uuid


class EntryType(Enum):
    """Types of transcript entries."""

    CHAT_TURN = "chat_turn"  # User or AI message
    TOOL_INVOCATION = "tool_invocation"  # Tool execution
    AGENT_DELEGATION = "agent_delegation"  # Future: delegated agent work


@dataclass
class SessionMetadata:
    """Metadata for a session."""

    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    agent_name: str = "orchestrator"
    user_id: Optional[str] = None
    repository: Optional[str] = None  # Git repo path if available
    environment: Optional[Dict[str, Any]] = None  # Environment info

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        # Convert datetime to ISO format
        data["start_time"] = self.start_time.isoformat()
        if self.end_time:
            data["end_time"] = self.end_time.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMetadata":
        """Create from dictionary."""
        # Parse ISO datetime strings
        data["start_time"] = datetime.fromisoformat(data["start_time"])
        if data.get("end_time"):
            data["end_time"] = datetime.fromisoformat(data["end_time"])
        return cls(**data)


@dataclass
class TranscriptEntry:
    """Base class for transcript entries."""

    entry_type: EntryType
    timestamp: datetime
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_type": self.entry_type.value,
            "timestamp": self.timestamp.isoformat(),
            "entry_id": self.entry_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranscriptEntry":
        """Create from dictionary (base method)."""
        data["entry_type"] = EntryType(data["entry_type"])
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class ChatTurn:
    """A chat message turn (user or AI)."""

    timestamp: datetime
    role: str  # "user" or "ai"
    content: str
    agent_name: Optional[str] = None  # For delegated agents
    entry_type: EntryType = field(default=EntryType.CHAT_TURN, init=False)
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_type": self.entry_type.value,
            "timestamp": self.timestamp.isoformat(),
            "entry_id": self.entry_id,
            "role": self.role,
            "content": self.content,
            "agent_name": self.agent_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatTurn":
        """Create from dictionary."""
        timestamp = datetime.fromisoformat(data["timestamp"])
        return cls(
            timestamp=timestamp,
            role=data["role"],
            content=data["content"],
            agent_name=data.get("agent_name"),
        )


@dataclass
class ToolInvocation:
    """A tool invocation record."""

    timestamp: datetime
    tool_name: str
    parameters: Dict[str, Any]
    success: bool
    result: Optional[str] = None  # Truncated result
    error: Optional[str] = None
    agent_name: Optional[str] = None  # For delegated agents
    execution_time_ms: Optional[float] = None
    entry_type: EntryType = field(default=EntryType.TOOL_INVOCATION, init=False)
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_type": self.entry_type.value,
            "timestamp": self.timestamp.isoformat(),
            "entry_id": self.entry_id,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "agent_name": self.agent_name,
            "execution_time_ms": self.execution_time_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolInvocation":
        """Create from dictionary."""
        timestamp = datetime.fromisoformat(data["timestamp"])
        return cls(
            timestamp=timestamp,
            tool_name=data["tool_name"],
            parameters=data["parameters"],
            success=data["success"],
            result=data.get("result"),
            error=data.get("error"),
            agent_name=data.get("agent_name"),
            execution_time_ms=data.get("execution_time_ms"),
        )
