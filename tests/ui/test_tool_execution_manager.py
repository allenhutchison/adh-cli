"""Tests for ToolExecutionManager."""

import pytest
import asyncio
from unittest.mock import Mock
from datetime import datetime

from adh_cli.ui.tool_execution_manager import ToolExecutionManager
from adh_cli.ui.tool_execution import ToolExecutionState
from adh_cli.policies.policy_types import PolicyDecision, SupervisionLevel, RiskLevel


class TestToolExecutionManager:
    """Test ToolExecutionManager coordination layer."""

    @pytest.fixture
    def manager(self):
        """Create manager with mock callbacks."""
        return ToolExecutionManager(
            on_execution_start=Mock(),
            on_execution_update=Mock(),
            on_execution_complete=Mock(),
            on_confirmation_required=Mock(),
        )

    def test_initialization(self):
        """Test manager initializes with empty state."""
        manager = ToolExecutionManager()

        assert manager.active_count == 0
        assert manager.history_count == 0
        assert manager.get_active_executions() == []
        assert manager.get_history() == []

    def test_create_execution(self, manager):
        """Test creating a new execution."""
        info = manager.create_execution(
            tool_name="read_file",
            parameters={"file_path": "test.txt"},
        )

        assert info.id is not None
        assert info.tool_name == "read_file"
        assert info.parameters == {"file_path": "test.txt"}
        assert info.state == ToolExecutionState.PENDING
        assert manager.active_count == 1

        # Should emit start event
        manager.on_execution_start.assert_called_once_with(info)

    def test_create_execution_with_policy_decision(self, manager):
        """Test creating execution with policy decision."""
        decision = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.CONFIRM,
            risk_level=RiskLevel.MEDIUM,
        )

        info = manager.create_execution(
            tool_name="write_file",
            parameters={"file_path": "test.txt"},
            policy_decision=decision,
        )

        assert info.policy_decision == decision

    def test_start_execution(self, manager):
        """Test starting an execution."""
        info = manager.create_execution(
            tool_name="read_file",
            parameters={},
        )
        manager.on_execution_update.reset_mock()

        updated = manager.start_execution(info.id)

        assert updated.state == ToolExecutionState.EXECUTING
        assert updated.started_at is not None
        manager.on_execution_update.assert_called_once()

    def test_complete_execution_success(self, manager):
        """Test completing execution successfully."""
        info = manager.create_execution(
            tool_name="read_file",
            parameters={},
        )
        manager.start_execution(info.id)
        manager.on_execution_complete.reset_mock()

        result = manager.complete_execution(
            info.id, success=True, result="file contents"
        )

        assert result.state == ToolExecutionState.SUCCESS
        assert result.result == "file contents"
        assert result.completed_at is not None
        assert result.is_terminal is True

        # Should move to history
        assert manager.active_count == 0
        assert manager.history_count == 1
        manager.on_execution_complete.assert_called_once()

    def test_complete_execution_failure(self, manager):
        """Test completing execution with failure."""
        info = manager.create_execution(
            tool_name="read_file",
            parameters={},
        )
        manager.start_execution(info.id)

        result = manager.complete_execution(
            info.id,
            success=False,
            error="File not found",
            error_type="FileNotFoundError",
        )

        assert result.state == ToolExecutionState.FAILED
        assert result.error == "File not found"
        assert result.error_type == "FileNotFoundError"
        assert result.is_terminal is True

        # Should move to history
        assert manager.active_count == 0
        assert manager.history_count == 1

    def test_cancel_execution(self, manager):
        """Test cancelling an execution."""
        info = manager.create_execution(
            tool_name="read_file",
            parameters={},
        )

        result = manager.cancel_execution(info.id)

        assert result.state == ToolExecutionState.CANCELLED
        assert result.completed_at is not None
        assert manager.active_count == 0
        assert manager.history_count == 1

    def test_block_execution(self, manager):
        """Test blocking an execution."""
        info = manager.create_execution(
            tool_name="dangerous_tool",
            parameters={},
        )

        result = manager.block_execution(info.id, reason="Tool blocked by policy")

        assert result.state == ToolExecutionState.BLOCKED
        assert result.error == "Tool blocked by policy"
        assert manager.active_count == 0
        assert manager.history_count == 1

    def test_require_confirmation(self, manager):
        """Test marking execution as requiring confirmation."""
        decision = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.CONFIRM,
            risk_level=RiskLevel.MEDIUM,
        )

        info = manager.create_execution(
            tool_name="write_file",
            parameters={},
        )
        manager.on_confirmation_required.reset_mock()

        result = manager.require_confirmation(info.id, decision)

        assert result.state == ToolExecutionState.CONFIRMING
        assert result.requires_confirmation is True
        assert result.policy_decision == decision

        # Should emit confirmation required event
        manager.on_confirmation_required.assert_called_once_with(result, decision)

    def test_confirm_execution(self, manager):
        """Test confirming an execution."""
        decision = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.CONFIRM,
            risk_level=RiskLevel.MEDIUM,
        )

        info = manager.create_execution(
            tool_name="write_file",
            parameters={},
        )
        manager.require_confirmation(info.id, decision)

        result = manager.confirm_execution(info.id)

        assert result.confirmed is True

    def test_update_execution(self, manager):
        """Test updating execution properties."""
        info = manager.create_execution(
            tool_name="test_tool",
            parameters={},
        )
        manager.on_execution_update.reset_mock()

        result = manager.update_execution(
            info.id,
            state=ToolExecutionState.EXECUTING,
            started_at=datetime.now(),
            custom_field="value",  # Should be ignored if not an attribute
        )

        assert result.state == ToolExecutionState.EXECUTING
        assert result.started_at is not None
        manager.on_execution_update.assert_called_once()

    def test_get_execution_active(self, manager):
        """Test getting active execution by ID."""
        info = manager.create_execution(
            tool_name="test_tool",
            parameters={},
        )

        retrieved = manager.get_execution(info.id)

        assert retrieved is info

    def test_get_execution_historical(self, manager):
        """Test getting historical execution by ID."""
        info = manager.create_execution(
            tool_name="test_tool",
            parameters={},
        )
        manager.complete_execution(info.id, success=True)

        retrieved = manager.get_execution(info.id)

        assert retrieved.id == info.id
        assert retrieved.state == ToolExecutionState.SUCCESS

    def test_get_execution_not_found(self, manager):
        """Test getting non-existent execution."""
        result = manager.get_execution("nonexistent-id")

        assert result is None

    def test_get_active_executions(self, manager):
        """Test getting all active executions."""
        info1 = manager.create_execution("tool1", {})
        info2 = manager.create_execution("tool2", {})
        manager.complete_execution(
            info1.id, success=True
        )  # Completes, moves to history

        active = manager.get_active_executions()

        assert len(active) == 1
        assert active[0].id == info2.id

    def test_get_history(self, manager):
        """Test getting execution history."""
        info1 = manager.create_execution("tool1", {})
        info2 = manager.create_execution("tool2", {})
        manager.complete_execution(info1.id, success=True)
        manager.complete_execution(info2.id, success=True)

        history = manager.get_history()

        assert len(history) == 2
        # Most recent first
        assert history[0].id == info2.id
        assert history[1].id == info1.id

    def test_get_history_with_limit(self, manager):
        """Test getting history with limit."""
        for i in range(5):
            info = manager.create_execution(f"tool{i}", {})
            manager.complete_execution(info.id, success=True)

        history = manager.get_history(limit=2)

        assert len(history) == 2

    def test_clear_history(self, manager):
        """Test clearing execution history."""
        info = manager.create_execution("tool1", {})
        manager.complete_execution(info.id, success=True)

        assert manager.history_count == 1

        manager.clear_history()

        assert manager.history_count == 0

    def test_history_max_limit(self):
        """Test history respects max_history limit."""
        manager = ToolExecutionManager(max_history=3)

        # Create and complete 5 executions
        for i in range(5):
            info = manager.create_execution(f"tool{i}", {})
            manager.complete_execution(info.id, success=True)

        # Should only keep last 3
        assert manager.history_count == 3
        history = manager.get_history()
        assert history[0].tool_name == "tool4"
        assert history[1].tool_name == "tool3"
        assert history[2].tool_name == "tool2"

    def test_multiple_active_executions(self, manager):
        """Test tracking multiple active executions."""
        info1 = manager.create_execution("tool1", {})
        info2 = manager.create_execution("tool2", {})
        manager.create_execution("tool3", {})

        assert manager.active_count == 3

        manager.start_execution(info1.id)
        manager.start_execution(info2.id)

        assert manager.active_count == 3

        manager.complete_execution(info1.id, success=True)

        assert manager.active_count == 2
        assert manager.history_count == 1

    def test_execution_lifecycle_full(self, manager):
        """Test full execution lifecycle."""
        # 1. Create
        info = manager.create_execution(
            tool_name="write_file",
            parameters={"file_path": "test.txt", "content": "hello"},
        )
        assert info.state == ToolExecutionState.PENDING
        assert manager.active_count == 1

        # 2. Require confirmation
        decision = PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.CONFIRM,
            risk_level=RiskLevel.MEDIUM,
        )
        manager.require_confirmation(info.id, decision)
        assert manager.get_execution(info.id).state == ToolExecutionState.CONFIRMING

        # 3. Confirm
        manager.confirm_execution(info.id)
        assert manager.get_execution(info.id).confirmed is True

        # 4. Start execution
        manager.start_execution(info.id)
        assert manager.get_execution(info.id).state == ToolExecutionState.EXECUTING

        # 5. Complete successfully
        manager.complete_execution(info.id, success=True, result="Written")

        # Should be in history now
        assert manager.active_count == 0
        assert manager.history_count == 1
        historical = manager.get_history()[0]
        assert historical.state == ToolExecutionState.SUCCESS
        assert historical.result == "Written"

    def test_no_callbacks(self):
        """Test manager works without callbacks."""
        manager = ToolExecutionManager()  # No callbacks

        info = manager.create_execution("tool", {})
        manager.start_execution(info.id)
        manager.complete_execution(info.id, success=True)

        # Should work fine
        assert manager.history_count == 1


class TestConfirmationWaiting:
    """Test confirmation waiting functionality (human-in-the-loop)."""

    @pytest.fixture
    def manager(self):
        """Create manager for confirmation tests."""
        return ToolExecutionManager(
            on_execution_start=Mock(),
            on_execution_update=Mock(),
            on_execution_complete=Mock(),
            on_confirmation_required=Mock(),
        )

    @pytest.fixture
    def policy_decision(self):
        """Create a policy decision requiring confirmation."""
        return PolicyDecision(
            allowed=True,
            supervision_level=SupervisionLevel.CONFIRM,
            risk_level=RiskLevel.MEDIUM,
            requires_confirmation=True,
            confirmation_message="Confirm this operation?",
        )

    @pytest.mark.asyncio
    async def test_wait_for_confirmation_user_confirms(self, manager, policy_decision):
        """Test waiting for confirmation when user confirms."""
        # Create execution and require confirmation
        info = manager.create_execution("write_file", {"file": "test.txt"})
        manager.require_confirmation(info.id, policy_decision)

        # Simulate user confirming in background
        async def simulate_user_confirm():
            await asyncio.sleep(0.1)  # Small delay to simulate user thinking
            manager.confirm_execution(info.id)

        # Start background task to confirm
        confirm_task = asyncio.create_task(simulate_user_confirm())

        # Wait for confirmation (should return True)
        result = await manager.wait_for_confirmation(info.id)

        assert result is True
        assert manager.get_execution(info.id).confirmed is True

        await confirm_task  # Clean up

    @pytest.mark.asyncio
    async def test_wait_for_confirmation_user_cancels(self, manager, policy_decision):
        """Test waiting for confirmation when user cancels."""
        # Create execution and require confirmation
        info = manager.create_execution("delete_file", {"file": "important.txt"})
        manager.require_confirmation(info.id, policy_decision)

        # Simulate user cancelling in background
        async def simulate_user_cancel():
            await asyncio.sleep(0.1)
            manager.cancel_execution(info.id)

        # Start background task to cancel
        cancel_task = asyncio.create_task(simulate_user_cancel())

        # Wait for confirmation (should return False)
        result = await manager.wait_for_confirmation(info.id)

        assert result is False
        assert manager.get_execution(info.id).state == ToolExecutionState.CANCELLED
        assert manager.get_execution(info.id).confirmed is False

        await cancel_task  # Clean up

    @pytest.mark.asyncio
    async def test_wait_for_confirmation_timeout(self, manager, policy_decision):
        """Test confirmation times out if user doesn't respond."""
        # Create execution and require confirmation
        info = manager.create_execution("execute_command", {"command": "rm -rf /"})
        manager.require_confirmation(info.id, policy_decision)

        # Wait with very short timeout (no user response)
        result = await manager.wait_for_confirmation(info.id, timeout=0.1)

        # Should return False (treated as cancellation)
        assert result is False
        assert manager.get_execution(info.id).state == ToolExecutionState.CANCELLED

    @pytest.mark.asyncio
    async def test_wait_for_confirmation_no_timeout(self, manager, policy_decision):
        """Test confirmation with no timeout (infinite wait)."""
        # Create execution and require confirmation
        info = manager.create_execution("test_tool", {})
        manager.require_confirmation(info.id, policy_decision)

        # Simulate quick user confirmation
        async def simulate_quick_confirm():
            await asyncio.sleep(0.05)
            manager.confirm_execution(info.id)

        confirm_task = asyncio.create_task(simulate_quick_confirm())

        # Wait with no timeout
        result = await manager.wait_for_confirmation(info.id, timeout=None)

        assert result is True

        await confirm_task

    @pytest.mark.asyncio
    async def test_wait_for_confirmation_raises_if_not_required(self, manager):
        """Test that waiting fails if confirmation wasn't required."""
        # Create execution WITHOUT requiring confirmation
        info = manager.create_execution("read_file", {})

        # Trying to wait should raise ValueError
        with pytest.raises(ValueError, match="No pending confirmation"):
            await manager.wait_for_confirmation(info.id)

    @pytest.mark.asyncio
    async def test_multiple_confirmations_different_executions(
        self, manager, policy_decision
    ):
        """Test multiple pending confirmations for different executions."""
        # Create two executions both requiring confirmation
        info1 = manager.create_execution("tool1", {})
        info2 = manager.create_execution("tool2", {})

        manager.require_confirmation(info1.id, policy_decision)
        manager.require_confirmation(info2.id, policy_decision)

        # Simulate user confirming first, cancelling second
        async def simulate_user_actions():
            await asyncio.sleep(0.05)
            manager.confirm_execution(info1.id)
            await asyncio.sleep(0.05)
            manager.cancel_execution(info2.id)

        actions_task = asyncio.create_task(simulate_user_actions())

        # Wait for both confirmations
        result1 = await manager.wait_for_confirmation(info1.id)
        result2 = await manager.wait_for_confirmation(info2.id)

        assert result1 is True
        assert result2 is False

        await actions_task

    @pytest.mark.asyncio
    async def test_confirmation_cleanup_after_wait(self, manager, policy_decision):
        """Test that pending confirmations are cleaned up after waiting."""
        info = manager.create_execution("test_tool", {})
        manager.require_confirmation(info.id, policy_decision)

        # Confirm quickly
        async def quick_confirm():
            await asyncio.sleep(0.05)
            manager.confirm_execution(info.id)

        confirm_task = asyncio.create_task(quick_confirm())

        # Wait for confirmation
        await manager.wait_for_confirmation(info.id)

        # Trying to wait again should fail (already cleaned up)
        with pytest.raises(ValueError, match="No pending confirmation"):
            await manager.wait_for_confirmation(info.id)

        await confirm_task

    @pytest.mark.asyncio
    async def test_confirm_execution_idempotent(self, manager, policy_decision):
        """Test that confirming multiple times doesn't cause issues."""
        info = manager.create_execution("test_tool", {})
        manager.require_confirmation(info.id, policy_decision)

        # Confirm in background
        async def confirm_twice():
            await asyncio.sleep(0.05)
            manager.confirm_execution(info.id)
            manager.confirm_execution(info.id)  # Second call should be safe

        confirm_task = asyncio.create_task(confirm_twice())

        result = await manager.wait_for_confirmation(info.id)

        assert result is True

        await confirm_task

    @pytest.mark.asyncio
    async def test_cancel_execution_idempotent(self, manager, policy_decision):
        """Test that cancelling multiple times doesn't cause issues."""
        info = manager.create_execution("test_tool", {})
        manager.require_confirmation(info.id, policy_decision)

        # Cancel in background
        async def cancel_twice():
            await asyncio.sleep(0.05)
            manager.cancel_execution(info.id)
            manager.cancel_execution(info.id)  # Second call should be safe

        cancel_task = asyncio.create_task(cancel_twice())

        result = await manager.wait_for_confirmation(info.id)

        assert result is False

        await cancel_task
