"""Tests for tool execution data models and utilities."""

import pytest
from datetime import datetime, timedelta
from adh_cli.ui.tool_execution import (
    ToolExecutionState,
    ToolExecutionInfo,
    truncate_value,
    format_parameters_inline,
    format_parameters_expanded,
)
from adh_cli.policies.policy_types import PolicyDecision, SupervisionLevel, RiskLevel


class TestToolExecutionInfo:
    """Test ToolExecutionInfo data model."""

    def test_initialization_defaults(self):
        """Test default initialization."""
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="read_file"
        )

        assert info.id == "test-1"
        assert info.tool_name == "read_file"
        assert info.state == ToolExecutionState.PENDING
        assert info.parameters == {}
        assert info.requires_confirmation is False
        assert info.confirmed is None
        assert info.result is None
        assert info.error is None

    def test_initialization_with_parameters(self):
        """Test initialization with parameters."""
        params = {"file_path": "test.txt", "max_lines": 100}
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="read_file",
            parameters=params,
            state=ToolExecutionState.EXECUTING
        )

        assert info.parameters == params
        assert info.state == ToolExecutionState.EXECUTING

    def test_duration_calculation(self):
        """Test duration property calculation."""
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="read_file",
            started_at=datetime(2024, 1, 1, 12, 0, 0),
            completed_at=datetime(2024, 1, 1, 12, 0, 2, 500000)
        )

        assert info.duration == pytest.approx(2.5, rel=0.01)

    def test_duration_none_when_not_complete(self):
        """Test duration is None when execution not complete."""
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="read_file",
            started_at=datetime.now()
        )

        assert info.duration is None

    def test_is_terminal_states(self):
        """Test is_terminal property for various states."""
        terminal_states = [
            ToolExecutionState.SUCCESS,
            ToolExecutionState.FAILED,
            ToolExecutionState.BLOCKED,
            ToolExecutionState.CANCELLED,
        ]

        for state in terminal_states:
            info = ToolExecutionInfo(id="test-1", tool_name="test", state=state)
            assert info.is_terminal is True

    def test_is_not_terminal_states(self):
        """Test is_terminal property for non-terminal states."""
        non_terminal_states = [
            ToolExecutionState.PENDING,
            ToolExecutionState.CONFIRMING,
            ToolExecutionState.EXECUTING,
        ]

        for state in non_terminal_states:
            info = ToolExecutionInfo(id="test-1", tool_name="test", state=state)
            assert info.is_terminal is False

    def test_status_icons(self):
        """Test status icon for each state."""
        expected_icons = {
            ToolExecutionState.PENDING: "⏳",
            ToolExecutionState.CONFIRMING: "⚠️",
            ToolExecutionState.EXECUTING: "🔧",
            ToolExecutionState.SUCCESS: "✅",
            ToolExecutionState.FAILED: "❌",
            ToolExecutionState.BLOCKED: "🚫",
            ToolExecutionState.CANCELLED: "⊗",
        }

        for state, expected_icon in expected_icons.items():
            info = ToolExecutionInfo(id="test-1", tool_name="test", state=state)
            assert info.status_icon == expected_icon

    def test_status_text(self):
        """Test status text for various states."""
        # Executing
        info = ToolExecutionInfo(id="test-1", tool_name="test", state=ToolExecutionState.EXECUTING)
        assert info.status_text == "Executing..."

        # Success with duration
        info = ToolExecutionInfo(
            id="test-1",
            tool_name="test",
            state=ToolExecutionState.SUCCESS,
            started_at=datetime(2024, 1, 1, 12, 0, 0),
            completed_at=datetime(2024, 1, 1, 12, 0, 1, 500000)
        )
        assert "Completed (1.50s)" in info.status_text

        # Failed
        info = ToolExecutionInfo(id="test-1", tool_name="test", state=ToolExecutionState.FAILED)
        assert info.status_text == "Failed"

        # Blocked
        info = ToolExecutionInfo(id="test-1", tool_name="test", state=ToolExecutionState.BLOCKED)
        assert info.status_text == "Blocked by Policy"


class TestTruncateValue:
    """Test value truncation utility."""

    def test_truncate_short_string(self):
        """Test truncation of short string (no truncation needed)."""
        display, length = truncate_value("hello", max_length=50)
        assert display == '"hello"'
        assert length == 5

    def test_truncate_long_string(self):
        """Test truncation of long string."""
        long_string = "a" * 100
        display, length = truncate_value(long_string, max_length=50)
        assert display == f'"{"a" * 46}..."'
        assert length == 100
        assert len(display) <= 50 + 2  # +2 for quotes

    def test_truncate_none(self):
        """Test truncation of None."""
        display, length = truncate_value(None)
        assert display == "null"
        assert length == 4

    def test_truncate_boolean(self):
        """Test truncation of boolean values."""
        display, length = truncate_value(True)
        assert display == "true"

        display, length = truncate_value(False)
        assert display == "false"

    def test_truncate_number(self):
        """Test truncation of numbers."""
        display, length = truncate_value(42)
        assert display == "42"
        assert length == 2

        display, length = truncate_value(3.14159)
        assert display == "3.14159"

    def test_truncate_bytes(self):
        """Test truncation of binary data."""
        # Small bytes
        data = b"hello"
        display, length = truncate_value(data)
        assert display == "<binary, 5B>"
        assert length == 5

        # KB
        data = b"x" * 2048
        display, length = truncate_value(data)
        assert "<binary, 2.0KB>" in display

        # MB
        data = b"x" * (2 * 1024 * 1024)
        display, length = truncate_value(data)
        assert "<binary, 2.0MB>" in display

    def test_truncate_empty_list(self):
        """Test truncation of empty list."""
        display, length = truncate_value([])
        assert display == "[]"
        assert length == 0

    def test_truncate_short_list(self):
        """Test truncation of short list."""
        display, length = truncate_value([1, 2, 3])
        assert display == "[1, 2, 3]"
        assert length == 3

    def test_truncate_long_list(self):
        """Test truncation of long list."""
        long_list = list(range(100))
        display, length = truncate_value(long_list)
        assert "0, ... 99 more" in display
        assert length == 100

    def test_truncate_empty_dict(self):
        """Test truncation of empty dict."""
        display, length = truncate_value({})
        assert display == "{}"
        assert length == 0

    def test_truncate_short_dict(self):
        """Test truncation of short dict."""
        display, length = truncate_value({"a": 1, "b": 2})
        assert "a: 1" in display
        assert length == 2

    def test_truncate_long_dict(self):
        """Test truncation of long dict."""
        long_dict = {f"key{i}": i for i in range(100)}
        display, length = truncate_value(long_dict)
        assert "... 99 more" in display
        assert length == 100


class TestFormatParametersInline:
    """Test inline parameter formatting."""

    def test_empty_parameters(self):
        """Test formatting with no parameters."""
        result = format_parameters_inline({})
        assert result == ""

    def test_single_parameter(self):
        """Test formatting with single parameter."""
        result = format_parameters_inline({"file_path": "test.txt"})
        assert result == 'file_path: "test.txt"'

    def test_multiple_parameters(self):
        """Test formatting with multiple parameters."""
        params = {
            "file_path": "test.txt",
            "max_lines": 100,
            "encoding": "utf-8"
        }
        result = format_parameters_inline(params, max_params=3)

        assert "file_path" in result
        assert "max_lines" in result
        assert "encoding" in result
        assert " | " in result

    def test_truncates_long_string_value(self):
        """Test that long string values are truncated with length indicator."""
        long_string = "a" * 100
        result = format_parameters_inline(
            {"content": long_string},
            max_value_length=50
        )

        assert "content:" in result
        assert "..." in result
        assert "(100ch)" in result  # Shows original length

    def test_max_params_limit(self):
        """Test that max_params limits display."""
        params = {
            "param1": "value1",
            "param2": "value2",
            "param3": "value3",
            "param4": "value4",
            "param5": "value5",
        }
        result = format_parameters_inline(params, max_params=2)

        assert "param1" in result
        assert "param2" in result
        assert "... 3 more" in result
        assert "param4" not in result

    def test_boolean_and_number_formatting(self):
        """Test formatting of boolean and number values."""
        params = {
            "confirm": True,
            "count": 42,
            "ratio": 3.14
        }
        result = format_parameters_inline(params)

        assert "confirm: true" in result
        assert "count: 42" in result
        assert "ratio: 3.14" in result


class TestFormatParametersExpanded:
    """Test expanded parameter formatting."""

    def test_empty_parameters(self):
        """Test formatting with no parameters."""
        result = format_parameters_expanded({})
        assert result == []

    def test_multiple_parameters(self):
        """Test formatting with multiple parameters."""
        params = {
            "file_path": "test.txt",
            "max_lines": 100,
            "content": "Hello world"
        }
        result = format_parameters_expanded(params)

        assert len(result) == 3
        keys = [item[0] for item in result]
        assert "file_path" in keys
        assert "max_lines" in keys
        assert "content" in keys

    def test_returns_original_length(self):
        """Test that original length is returned for each value."""
        long_string = "a" * 300
        params = {"content": long_string}
        result = format_parameters_expanded(params, max_value_length=200)

        assert len(result) == 1
        key, display, original_len = result[0]
        assert key == "content"
        assert "..." in display  # Truncated
        assert original_len == 300  # Original length preserved

    def test_expanded_max_length_larger(self):
        """Test that expanded view uses larger max length."""
        medium_string = "b" * 100
        params = {"data": medium_string}

        # Should not truncate with default 200 max
        result = format_parameters_expanded(params, max_value_length=200)
        key, display, original_len = result[0]
        assert "..." not in display  # Not truncated
        assert original_len == 100