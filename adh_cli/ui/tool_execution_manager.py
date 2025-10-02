"""Manager for tool execution tracking and UI widget lifecycle.

This module provides the ToolExecutionManager class which serves as the coordinator
between tool execution (PolicyAwareFunctionTool), state tracking (ToolExecutionInfo),
and UI display (ToolExecutionWidget).

Separation of concerns:
- ToolExecutionInfo: Pure data model (no UI knowledge)
- ToolExecutionWidget: Pure UI component (no execution knowledge)
- ToolExecutionManager: Coordination layer (connects execution to UI)
"""

from typing import Dict, Optional, Callable, Any
from datetime import datetime
import uuid
import asyncio

from adh_cli.ui.tool_execution import (
    ToolExecutionInfo,
    ToolExecutionState,
)
from adh_cli.policies.policy_types import PolicyDecision


class ToolExecutionManager:
    """Manages tool execution tracking and lifecycle.

    This class coordinates between tool execution and UI:
    - Creates and tracks ToolExecutionInfo instances
    - Emits events for UI updates (via callbacks)
    - Manages execution lifecycle
    - Maintains execution history

    The manager is UI-agnostic - it only emits events that UI can subscribe to.
    """

    def __init__(
        self,
        on_execution_start: Optional[Callable[[ToolExecutionInfo], Any]] = None,
        on_execution_update: Optional[Callable[[ToolExecutionInfo], Any]] = None,
        on_execution_complete: Optional[Callable[[ToolExecutionInfo], Any]] = None,
        on_confirmation_required: Optional[Callable[[ToolExecutionInfo, PolicyDecision], Any]] = None,
        max_history: int = 100,
    ):
        """Initialize tool execution manager.

        Args:
            on_execution_start: Callback when execution starts (receives ToolExecutionInfo)
            on_execution_update: Callback when execution state updates (receives ToolExecutionInfo)
            on_execution_complete: Callback when execution completes (receives ToolExecutionInfo)
            on_confirmation_required: Callback when confirmation needed (receives info, decision)
            max_history: Maximum number of executions to keep in history
        """
        self.on_execution_start = on_execution_start
        self.on_execution_update = on_execution_update
        self.on_execution_complete = on_execution_complete
        self.on_confirmation_required = on_confirmation_required
        self.max_history = max_history

        # Track active and completed executions
        self._active_executions: Dict[str, ToolExecutionInfo] = {}
        self._execution_history: list[ToolExecutionInfo] = []

        # Track pending confirmations (execution_id -> Future[bool])
        self._pending_confirmations: Dict[str, asyncio.Future] = {}

    def create_execution(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        policy_decision: Optional[PolicyDecision] = None,
    ) -> ToolExecutionInfo:
        """Create a new tool execution tracking instance.

        Args:
            tool_name: Name of the tool being executed
            parameters: Tool parameters
            policy_decision: Policy decision for this execution

        Returns:
            New ToolExecutionInfo instance
        """
        execution_id = str(uuid.uuid4())
        info = ToolExecutionInfo(
            id=execution_id,
            tool_name=tool_name,
            parameters=parameters,
            policy_decision=policy_decision,
            state=ToolExecutionState.PENDING,
            timestamp=datetime.now(),
        )

        # Track as active
        self._active_executions[execution_id] = info

        # Emit start event
        if self.on_execution_start:
            self.on_execution_start(info)

        return info

    def update_execution(
        self,
        execution_id: str,
        state: Optional[ToolExecutionState] = None,
        **kwargs
    ) -> Optional[ToolExecutionInfo]:
        """Update an execution's state and properties.

        Args:
            execution_id: ID of execution to update
            state: New state (if changing)
            **kwargs: Additional properties to update (result, error, etc.)

        Returns:
            Updated ToolExecutionInfo, or None if not found
        """
        info = self._active_executions.get(execution_id)
        if not info:
            return None

        # Update state if provided
        if state is not None:
            info.state = state

        # Update other properties
        for key, value in kwargs.items():
            if hasattr(info, key):
                setattr(info, key, value)

        # Emit update event
        if self.on_execution_update:
            self.on_execution_update(info)

        # If terminal state, move to history
        if info.is_terminal:
            self._complete_execution(execution_id)

        return info

    def start_execution(self, execution_id: str) -> Optional[ToolExecutionInfo]:
        """Mark execution as started (executing state).

        Args:
            execution_id: ID of execution

        Returns:
            Updated ToolExecutionInfo, or None if not found
        """
        return self.update_execution(
            execution_id,
            state=ToolExecutionState.EXECUTING,
            started_at=datetime.now()
        )

    def complete_execution(
        self,
        execution_id: str,
        success: bool,
        result: Optional[Any] = None,
        error: Optional[str] = None,
        error_type: Optional[str] = None,
    ) -> Optional[ToolExecutionInfo]:
        """Mark execution as complete (success or failed).

        Args:
            execution_id: ID of execution
            success: Whether execution succeeded
            result: Result value (if successful)
            error: Error message (if failed)
            error_type: Error type name (if failed)

        Returns:
            Updated ToolExecutionInfo, or None if not found
        """
        state = ToolExecutionState.SUCCESS if success else ToolExecutionState.FAILED
        return self.update_execution(
            execution_id,
            state=state,
            completed_at=datetime.now(),
            result=result,
            error=error,
            error_type=error_type,
        )

    def cancel_execution(self, execution_id: str) -> Optional[ToolExecutionInfo]:
        """Mark execution as cancelled.

        This resolves the pending confirmation Future with False,
        causing the awaiting execution to abort.

        Args:
            execution_id: ID of execution

        Returns:
            Updated ToolExecutionInfo, or None if not found
        """
        # Resolve the confirmation future if it exists
        confirmation_future = self._pending_confirmations.get(execution_id)
        if confirmation_future and not confirmation_future.done():
            confirmation_future.set_result(False)

        return self.update_execution(
            execution_id,
            state=ToolExecutionState.CANCELLED,
            completed_at=datetime.now(),
            confirmed=False,
        )

    def block_execution(
        self,
        execution_id: str,
        reason: Optional[str] = None
    ) -> Optional[ToolExecutionInfo]:
        """Mark execution as blocked by policy.

        Args:
            execution_id: ID of execution
            reason: Reason for blocking

        Returns:
            Updated ToolExecutionInfo, or None if not found
        """
        return self.update_execution(
            execution_id,
            state=ToolExecutionState.BLOCKED,
            completed_at=datetime.now(),
            error=reason,
        )

    def require_confirmation(
        self,
        execution_id: str,
        policy_decision: PolicyDecision,
    ) -> Optional[ToolExecutionInfo]:
        """Mark execution as requiring confirmation.

        Args:
            execution_id: ID of execution
            policy_decision: Policy decision requiring confirmation

        Returns:
            Updated ToolExecutionInfo, or None if not found
        """
        info = self.update_execution(
            execution_id,
            state=ToolExecutionState.CONFIRMING,
            requires_confirmation=True,
            policy_decision=policy_decision,
        )

        # Create a Future for this confirmation that execution will await
        self._pending_confirmations[execution_id] = asyncio.Future()

        # Emit confirmation required event
        if info and self.on_confirmation_required:
            self.on_confirmation_required(info, policy_decision)

        return info

    async def wait_for_confirmation(
        self,
        execution_id: str,
        timeout: Optional[float] = 300.0  # 5 minute default timeout
    ) -> bool:
        """Wait for user to confirm or cancel execution.

        This method blocks until the user clicks Confirm or Cancel in the UI,
        or until the timeout is reached.

        Args:
            execution_id: ID of execution awaiting confirmation
            timeout: Maximum time to wait in seconds (None for no timeout)

        Returns:
            True if user confirmed, False if cancelled or timed out

        Raises:
            ValueError: If no pending confirmation exists for this execution_id
        """
        confirmation_future = self._pending_confirmations.get(execution_id)

        if confirmation_future is None:
            raise ValueError(
                f"No pending confirmation for execution {execution_id}. "
                "Call require_confirmation() first."
            )

        try:
            # Wait for the future to be resolved (by confirm_execution or cancel_execution)
            if timeout:
                result = await asyncio.wait_for(confirmation_future, timeout=timeout)
            else:
                result = await confirmation_future

            return result

        except asyncio.TimeoutError:
            # Timeout reached - treat as cancellation
            self.cancel_execution(execution_id)
            return False

        finally:
            # Clean up the pending confirmation
            self._pending_confirmations.pop(execution_id, None)

    def confirm_execution(self, execution_id: str) -> Optional[ToolExecutionInfo]:
        """Mark execution as confirmed by user.

        This resolves the pending confirmation Future with True,
        allowing the awaiting execution to proceed.

        Args:
            execution_id: ID of execution

        Returns:
            Updated ToolExecutionInfo, or None if not found
        """
        # Resolve the confirmation future if it exists
        confirmation_future = self._pending_confirmations.get(execution_id)
        if confirmation_future and not confirmation_future.done():
            confirmation_future.set_result(True)

        return self.update_execution(
            execution_id,
            confirmed=True,
        )

    def _complete_execution(self, execution_id: str) -> None:
        """Move execution from active to history.

        Args:
            execution_id: ID of execution to complete
        """
        info = self._active_executions.pop(execution_id, None)
        if not info:
            return

        # Add to history
        self._execution_history.append(info)

        # Trim history if needed
        if len(self._execution_history) > self.max_history:
            self._execution_history = self._execution_history[-self.max_history:]

        # Emit complete event
        if self.on_execution_complete:
            self.on_execution_complete(info)

    def get_execution(self, execution_id: str) -> Optional[ToolExecutionInfo]:
        """Get an execution by ID (active or historical).

        Args:
            execution_id: ID of execution

        Returns:
            ToolExecutionInfo if found, None otherwise
        """
        # Check active first
        info = self._active_executions.get(execution_id)
        if info:
            return info

        # Check history
        for info in self._execution_history:
            if info.id == execution_id:
                return info

        return None

    def get_active_executions(self) -> list[ToolExecutionInfo]:
        """Get all currently active executions.

        Returns:
            List of active ToolExecutionInfo instances
        """
        return list(self._active_executions.values())

    def get_history(self, limit: Optional[int] = None) -> list[ToolExecutionInfo]:
        """Get execution history.

        Args:
            limit: Maximum number of entries to return (most recent first)

        Returns:
            List of historical ToolExecutionInfo instances
        """
        history = list(reversed(self._execution_history))
        if limit:
            history = history[:limit]
        return history

    def clear_history(self) -> None:
        """Clear execution history (keeps active executions)."""
        self._execution_history.clear()

    @property
    def active_count(self) -> int:
        """Get count of active executions."""
        return len(self._active_executions)

    @property
    def history_count(self) -> int:
        """Get count of historical executions."""
        return len(self._execution_history)