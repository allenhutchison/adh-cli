"""End-to-end integration tests for tool execution UI tracking."""

import pytest

from adh_cli.core.policy_aware_llm_agent import PolicyAwareLlmAgent
from adh_cli.ui.tool_execution import ToolExecutionState


@pytest.mark.asyncio
async def test_tool_execution_tracking_flow(tmp_path):
    """Test complete tool execution tracking from agent to UI callbacks."""
    # Track callback invocations
    start_calls = []
    update_calls = []
    complete_calls = []
    confirmation_calls = []

    def on_start(info):
        start_calls.append(info)

    def on_update(info):
        update_calls.append(info)

    def on_complete(info):
        complete_calls.append(info)

    def on_confirmation(info, decision):
        confirmation_calls.append((info, decision))

    # Create agent with execution tracking
    agent = PolicyAwareLlmAgent(
        api_key="test-key",
        policy_dir=tmp_path / "policies",
        on_execution_start=on_start,
        on_execution_update=on_update,
        on_execution_complete=on_complete,
        on_confirmation_required=on_confirmation,
    )

    # Register a simple test tool
    async def test_tool(value: str) -> str:
        """Test tool that returns a value."""
        return f"Result: {value}"

    agent.register_tool(
        name="test_tool",
        description="Test tool",
        parameters={"value": {"type": "string"}},
        handler=test_tool,
    )

    # Get the registered tool directly
    tool = agent.tools[0]

    # Execute the tool through the policy wrapper
    result = await tool.func(value="test_input")

    # Verify result
    assert result == "Result: test_input"

    # Verify callback sequence
    assert len(start_calls) == 1, "Should have one start callback"
    assert len(update_calls) == 2, "Should have two update callbacks (start + complete)"
    assert len(complete_calls) == 1, "Should have one complete callback"

    # Verify execution info (note: object is mutated, so we check it ended in SUCCESS)
    start_info = start_calls[0]
    assert start_info.tool_name == "test_tool"
    assert start_info.parameters == {"value": "test_input"}
    # The info object is mutated, so it will have the final state
    assert start_info.state == ToolExecutionState.SUCCESS

    # Verify final state
    complete_info = complete_calls[0]
    assert complete_info.state == ToolExecutionState.SUCCESS
    assert complete_info.result == "Result: test_input"
    assert complete_info.is_terminal is True
    # Verify it's the same object (passed by reference)
    assert start_info is complete_info


@pytest.mark.asyncio
async def test_tool_execution_tracking_with_error(tmp_path):
    """Test tool execution tracking when tool raises an error."""
    # Track callback invocations
    start_calls = []
    complete_calls = []

    def on_start(info):
        start_calls.append(info)

    def on_complete(info):
        complete_calls.append(info)

    # Create agent with execution tracking
    agent = PolicyAwareLlmAgent(
        api_key="test-key",
        policy_dir=tmp_path / "policies",
        on_execution_start=on_start,
        on_execution_complete=on_complete,
    )

    # Register a tool that raises an error
    async def failing_tool(value: str) -> str:
        """Test tool that fails."""
        raise ValueError("Test error")

    agent.register_tool(
        name="failing_tool",
        description="Failing tool",
        parameters={"value": {"type": "string"}},
        handler=failing_tool,
    )

    # Get the registered tool directly
    tool = agent.tools[0]

    # Execute the tool - should raise error
    with pytest.raises(ValueError, match="Test error"):
        await tool.func(value="test_input")

    # Verify callbacks were invoked
    assert len(start_calls) == 1, "Should have one start callback"
    assert len(complete_calls) == 1, "Should have one complete callback even on error"

    # Verify error tracking
    complete_info = complete_calls[0]
    assert complete_info.state == ToolExecutionState.FAILED
    assert "Test error" in complete_info.error
    assert complete_info.error_type == "ValueError"
    assert complete_info.is_terminal is True


@pytest.mark.asyncio
async def test_tool_execution_tracking_with_policy_block(tmp_path):
    """Test tool execution tracking when policy blocks execution."""
    # Track callback invocations
    start_calls = []
    complete_calls = []

    def on_start(info):
        start_calls.append(info)

    def on_complete(info):
        complete_calls.append(info)

    # Create policies that block the tool
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir(parents=True)

    policy_file = policy_dir / "test_policies.yaml"
    policy_file.write_text("""
test_tools:
  test_tool:
    pattern: "test_tool"
    supervision: "deny"
    risk: "critical"
    reason: "Test tool is blocked"
""")

    # Create agent with execution tracking
    agent = PolicyAwareLlmAgent(
        api_key="test-key",
        policy_dir=policy_dir,
        on_execution_start=on_start,
        on_execution_complete=on_complete,
    )

    # Register a tool
    async def test_tool(value: str) -> str:
        """Test tool."""
        return f"Result: {value}"

    agent.register_tool(
        name="test_tool",
        description="Test tool",
        parameters={"value": {"type": "string"}},
        handler=test_tool,
    )

    # Get the registered tool
    tool = agent.tools[0]

    # Execute the tool - should be blocked
    with pytest.raises(PermissionError, match="blocked by policy"):
        await tool.func(value="test_input")

    # Verify callbacks - should have start but execution blocked
    assert len(start_calls) == 1, "Should have one start callback"
    # Note: complete_calls might be 0 or 1 depending on when blocking happens
    # The important thing is that it was blocked

    # Verify execution was blocked
    start_info = start_calls[0]
    assert start_info.tool_name == "test_tool"


@pytest.mark.asyncio
async def test_multiple_tool_executions_tracked_separately(tmp_path):
    """Test that multiple tool executions are tracked with separate IDs."""
    # Track callback invocations
    start_calls = []
    complete_calls = []

    def on_start(info):
        start_calls.append(info)

    def on_complete(info):
        complete_calls.append(info)

    # Create agent with execution tracking
    agent = PolicyAwareLlmAgent(
        api_key="test-key",
        policy_dir=tmp_path / "policies",
        on_execution_start=on_start,
        on_execution_complete=on_complete,
    )

    # Register a simple test tool
    async def test_tool(value: str) -> str:
        """Test tool."""
        return f"Result: {value}"

    agent.register_tool(
        name="test_tool",
        description="Test tool",
        parameters={"value": {"type": "string"}},
        handler=test_tool,
    )

    # Get the registered tool
    tool = agent.tools[0]

    # Execute the tool multiple times
    result1 = await tool.func(value="first")
    result2 = await tool.func(value="second")
    result3 = await tool.func(value="third")

    # Verify results
    assert result1 == "Result: first"
    assert result2 == "Result: second"
    assert result3 == "Result: third"

    # Verify separate tracking
    assert len(start_calls) == 3, "Should have three start callbacks"
    assert len(complete_calls) == 3, "Should have three complete callbacks"

    # Verify unique IDs
    execution_ids = [info.id for info in start_calls]
    assert len(execution_ids) == len(
        set(execution_ids)
    ), "Execution IDs should be unique"

    # Verify parameters tracked correctly
    assert start_calls[0].parameters == {"value": "first"}
    assert start_calls[1].parameters == {"value": "second"}
    assert start_calls[2].parameters == {"value": "third"}
