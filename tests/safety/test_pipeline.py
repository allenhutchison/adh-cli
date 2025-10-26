"""Tests for safety check pipeline."""

import asyncio
import pytest

from adh_cli.safety.pipeline import SafetyPipeline, PipelineResult
from adh_cli.safety.base_checker import SafetyChecker, SafetyResult, SafetyStatus
from adh_cli.policies.policy_types import ToolCall, SafetyCheck, RiskLevel


class MockChecker(SafetyChecker):
    """Mock safety checker for testing."""

    def __init__(self, config=None):
        super().__init__(config=config)
        self.check_result = None

    async def check(self, tool_call: ToolCall) -> SafetyResult:
        """Return configured result."""
        if self.check_result:
            return self.check_result
        return SafetyResult(
            checker_name=self.name,
            status=SafetyStatus.PASSED,
            message="Check passed",
            risk_level=RiskLevel.LOW,
        )


class TestPipelineResult:
    """Test the PipelineResult class."""

    def test_is_safe_when_passed(self):
        """Test is_safe returns True when status is PASSED."""
        result = PipelineResult(
            results=[],
            overall_status=SafetyStatus.PASSED,
            risk_score=0.1,
            blocking_issues=[],
            warnings=[],
        )
        assert result.is_safe is True

    def test_is_safe_when_warning(self):
        """Test is_safe returns True when status is WARNING."""
        result = PipelineResult(
            results=[],
            overall_status=SafetyStatus.WARNING,
            risk_score=0.3,
            blocking_issues=[],
            warnings=["Some warning"],
        )
        assert result.is_safe is True

    def test_is_safe_when_failed(self):
        """Test is_safe returns False when status is FAILED."""
        result = PipelineResult(
            results=[],
            overall_status=SafetyStatus.FAILED,
            risk_score=0.8,
            blocking_issues=["Critical issue"],
            warnings=[],
        )
        assert result.is_safe is False

    def test_is_safe_when_error(self):
        """Test is_safe returns True when status is ERROR (not blocking)."""
        result = PipelineResult(
            results=[],
            overall_status=SafetyStatus.ERROR,
            risk_score=0.5,
            blocking_issues=[],
            warnings=[],
        )
        assert result.is_safe is True

    def test_has_warnings_true(self):
        """Test has_warnings returns True when warnings exist."""
        result = PipelineResult(
            results=[],
            overall_status=SafetyStatus.WARNING,
            risk_score=0.3,
            blocking_issues=[],
            warnings=["Warning 1", "Warning 2"],
        )
        assert result.has_warnings is True

    def test_has_warnings_false(self):
        """Test has_warnings returns False when no warnings."""
        result = PipelineResult(
            results=[],
            overall_status=SafetyStatus.PASSED,
            risk_score=0.1,
            blocking_issues=[],
            warnings=[],
        )
        assert result.has_warnings is False


class TestSafetyPipeline:
    """Test the SafetyPipeline class."""

    def test_initialization(self):
        """Test pipeline initializes with default checkers."""
        pipeline = SafetyPipeline()

        # Check that default checkers are registered
        assert "BackupChecker" in pipeline.checkers
        assert "DiskSpaceChecker" in pipeline.checkers
        assert "SensitiveDataChecker" in pipeline.checkers
        assert "SizeLimitChecker" in pipeline.checkers
        assert "CommandValidator" in pipeline.checkers
        assert "SandboxChecker" in pipeline.checkers
        assert "PermissionChecker" in pipeline.checkers
        assert len(pipeline.checkers) == 7

    def test_register_checker(self):
        """Test registering a custom checker."""
        pipeline = SafetyPipeline()

        # Clear existing checkers for clean test
        pipeline.checkers = {}

        # Register custom checker
        pipeline.register_checker("CustomChecker", MockChecker)

        assert "CustomChecker" in pipeline.checkers
        assert pipeline.checkers["CustomChecker"] == MockChecker

    @pytest.mark.asyncio
    async def test_run_checks_all_pass(self):
        """Test running checks when all pass."""
        pipeline = SafetyPipeline()
        pipeline.checkers = {"MockChecker": MockChecker}

        tool_call = ToolCall(tool_name="test_tool", parameters={})
        safety_checks = [SafetyCheck(name="test_check", checker_class="MockChecker")]

        result = await pipeline.run_checks(tool_call, safety_checks)

        assert result.overall_status == SafetyStatus.PASSED
        assert result.is_safe is True
        assert len(result.blocking_issues) == 0
        assert len(result.warnings) == 0

    @pytest.mark.asyncio
    async def test_run_checks_with_warnings(self):
        """Test running checks with warnings."""
        pipeline = SafetyPipeline()

        # Create a checker that returns a warning
        class WarningChecker(MockChecker):
            async def check(self, tool_call: ToolCall) -> SafetyResult:
                return SafetyResult(
                    checker_name="WarningChecker",
                    status=SafetyStatus.WARNING,
                    message="This is a warning",
                    risk_level=RiskLevel.MEDIUM,
                )

        pipeline.checkers = {"WarningChecker": WarningChecker}

        tool_call = ToolCall(tool_name="test_tool", parameters={})
        safety_checks = [SafetyCheck(name="test_check", checker_class="WarningChecker")]

        result = await pipeline.run_checks(tool_call, safety_checks)

        assert result.overall_status == SafetyStatus.WARNING
        assert result.is_safe is True
        assert len(result.warnings) == 1
        assert "This is a warning" in result.warnings

    @pytest.mark.asyncio
    async def test_run_checks_with_blocking_failure(self):
        """Test running checks with blocking failure."""
        pipeline = SafetyPipeline()

        # Create a checker that returns a blocking failure
        class FailingChecker(MockChecker):
            async def check(self, tool_call: ToolCall) -> SafetyResult:
                return SafetyResult(
                    checker_name="FailingChecker",
                    status=SafetyStatus.FAILED,
                    message="Critical failure",
                    risk_level=RiskLevel.HIGH,
                    can_override=False,
                )

        pipeline.checkers = {"FailingChecker": FailingChecker}

        tool_call = ToolCall(tool_name="test_tool", parameters={})
        safety_checks = [SafetyCheck(name="test_check", checker_class="FailingChecker")]

        result = await pipeline.run_checks(tool_call, safety_checks)

        assert result.overall_status == SafetyStatus.FAILED
        assert result.is_safe is False
        assert len(result.blocking_issues) == 1
        assert "Critical failure" in result.blocking_issues

    @pytest.mark.asyncio
    async def test_run_checks_with_overridable_failure(self):
        """Test running checks with overridable failure."""
        pipeline = SafetyPipeline()

        # Create a checker that returns an overridable failure
        class OverridableFailingChecker(MockChecker):
            async def check(self, tool_call: ToolCall) -> SafetyResult:
                return SafetyResult(
                    checker_name="OverridableFailingChecker",
                    status=SafetyStatus.FAILED,
                    message="Overridable failure",
                    risk_level=RiskLevel.MEDIUM,
                    can_override=True,
                )

        pipeline.checkers = {"OverridableFailingChecker": OverridableFailingChecker}

        tool_call = ToolCall(tool_name="test_tool", parameters={})
        safety_checks = [
            SafetyCheck(name="test_check", checker_class="OverridableFailingChecker")
        ]

        result = await pipeline.run_checks(tool_call, safety_checks)

        # Overridable failures become warnings
        assert result.overall_status == SafetyStatus.PASSED
        assert result.is_safe is True
        assert len(result.warnings) == 1
        assert "[Overridable] Overridable failure" in result.warnings

    @pytest.mark.asyncio
    async def test_run_checks_unknown_checker(self):
        """Test running checks with unknown checker class."""
        pipeline = SafetyPipeline()
        pipeline.checkers = {}

        tool_call = ToolCall(tool_name="test_tool", parameters={})
        safety_checks = [SafetyCheck(name="test_check", checker_class="UnknownChecker")]

        result = await pipeline.run_checks(tool_call, safety_checks)

        # No tasks created, empty results
        assert result.overall_status == SafetyStatus.PASSED
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_run_checks_multiple_checkers(self):
        """Test running multiple checks."""
        pipeline = SafetyPipeline()

        class PassChecker(MockChecker):
            async def check(self, tool_call: ToolCall) -> SafetyResult:
                return SafetyResult(
                    checker_name="PassChecker",
                    status=SafetyStatus.PASSED,
                    message="Passed",
                    risk_level=RiskLevel.LOW,
                )

        class WarnChecker(MockChecker):
            async def check(self, tool_call: ToolCall) -> SafetyResult:
                return SafetyResult(
                    checker_name="WarnChecker",
                    status=SafetyStatus.WARNING,
                    message="Warning",
                    risk_level=RiskLevel.MEDIUM,
                )

        pipeline.checkers = {"PassChecker": PassChecker, "WarnChecker": WarnChecker}

        tool_call = ToolCall(tool_name="test_tool", parameters={})
        safety_checks = [
            SafetyCheck(name="pass_check", checker_class="PassChecker"),
            SafetyCheck(name="warn_check", checker_class="WarnChecker"),
        ]

        result = await pipeline.run_checks(tool_call, safety_checks)

        assert result.overall_status == SafetyStatus.WARNING
        assert len(result.results) == 2
        assert len(result.warnings) == 1

    @pytest.mark.asyncio
    async def test_run_check_with_timeout_success(self):
        """Test running a check that completes within timeout."""
        pipeline = SafetyPipeline()
        checker = MockChecker()
        tool_call = ToolCall(tool_name="test_tool", parameters={})

        result = await pipeline._run_check_with_timeout(checker, tool_call, timeout=5.0)

        assert result.status == SafetyStatus.PASSED
        assert result.message == "Check passed"

    @pytest.mark.asyncio
    async def test_run_check_with_timeout_expires(self):
        """Test running a check that times out."""
        pipeline = SafetyPipeline()

        # Create a checker that takes too long
        class SlowChecker(MockChecker):
            async def check(self, tool_call: ToolCall) -> SafetyResult:
                await asyncio.sleep(10)  # Longer than timeout
                return SafetyResult(
                    checker_name="SlowChecker",
                    status=SafetyStatus.PASSED,
                    message="Should not get here",
                    risk_level=RiskLevel.LOW,
                )

        checker = SlowChecker()
        tool_call = ToolCall(tool_name="test_tool", parameters={})

        result = await pipeline._run_check_with_timeout(checker, tool_call, timeout=0.1)

        assert result.status == SafetyStatus.ERROR
        assert "timed out" in result.message.lower()
        assert result.risk_level == RiskLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_run_check_with_exception(self):
        """Test running a check that raises an exception."""
        pipeline = SafetyPipeline()

        # Create a checker that raises an exception
        class ErrorChecker(MockChecker):
            async def check(self, tool_call: ToolCall) -> SafetyResult:
                raise ValueError("Something went wrong")

        checker = ErrorChecker()
        tool_call = ToolCall(tool_name="test_tool", parameters={})

        result = await pipeline._run_check_with_timeout(checker, tool_call, timeout=5.0)

        assert result.status == SafetyStatus.ERROR
        assert "Check failed" in result.message
        assert "Something went wrong" in result.message
        assert result.risk_level == RiskLevel.MEDIUM

    def test_aggregate_results_all_passed(self):
        """Test aggregating results when all passed."""
        pipeline = SafetyPipeline()

        results = [
            SafetyResult(
                checker_name="Checker1",
                status=SafetyStatus.PASSED,
                message="Pass 1",
                risk_level=RiskLevel.LOW,
            ),
            SafetyResult(
                checker_name="Checker2",
                status=SafetyStatus.PASSED,
                message="Pass 2",
                risk_level=RiskLevel.LOW,
            ),
        ]

        pipeline_result = pipeline._aggregate_results(results)

        assert pipeline_result.overall_status == SafetyStatus.PASSED
        assert len(pipeline_result.blocking_issues) == 0
        assert len(pipeline_result.warnings) == 0
        assert pipeline_result.risk_score == 0.25  # Average of two LOW risks

    def test_aggregate_results_with_warnings(self):
        """Test aggregating results with warnings."""
        pipeline = SafetyPipeline()

        results = [
            SafetyResult(
                checker_name="Checker1",
                status=SafetyStatus.PASSED,
                message="Pass",
                risk_level=RiskLevel.LOW,
            ),
            SafetyResult(
                checker_name="Checker2",
                status=SafetyStatus.WARNING,
                message="Warning message",
                risk_level=RiskLevel.MEDIUM,
            ),
        ]

        pipeline_result = pipeline._aggregate_results(results)

        assert pipeline_result.overall_status == SafetyStatus.WARNING
        assert len(pipeline_result.warnings) == 1
        assert "Warning message" in pipeline_result.warnings

    def test_aggregate_results_with_blocking_failure(self):
        """Test aggregating results with blocking failure."""
        pipeline = SafetyPipeline()

        results = [
            SafetyResult(
                checker_name="Checker1",
                status=SafetyStatus.FAILED,
                message="Critical issue",
                risk_level=RiskLevel.HIGH,
                can_override=False,
            ),
        ]

        pipeline_result = pipeline._aggregate_results(results)

        assert pipeline_result.overall_status == SafetyStatus.FAILED
        assert len(pipeline_result.blocking_issues) == 1
        assert "Critical issue" in pipeline_result.blocking_issues

    def test_aggregate_results_with_exception(self):
        """Test aggregating results with exception."""
        pipeline = SafetyPipeline()

        results = [
            ValueError("Test error"),
            SafetyResult(
                checker_name="Checker1",
                status=SafetyStatus.PASSED,
                message="Pass",
                risk_level=RiskLevel.LOW,
            ),
        ]

        pipeline_result = pipeline._aggregate_results(results)

        assert pipeline_result.overall_status == SafetyStatus.ERROR
        assert len(pipeline_result.blocking_issues) == 1
        assert "Check error" in pipeline_result.blocking_issues[0]
        assert "Test error" in pipeline_result.blocking_issues[0]

    def test_aggregate_results_risk_score_calculation(self):
        """Test risk score calculation with different risk levels."""
        pipeline = SafetyPipeline()

        results = [
            SafetyResult(
                checker_name="Checker1",
                status=SafetyStatus.PASSED,
                message="Low risk",
                risk_level=RiskLevel.LOW,
            ),
            SafetyResult(
                checker_name="Checker2",
                status=SafetyStatus.PASSED,
                message="Medium risk",
                risk_level=RiskLevel.MEDIUM,
            ),
            SafetyResult(
                checker_name="Checker3",
                status=SafetyStatus.PASSED,
                message="High risk",
                risk_level=RiskLevel.HIGH,
            ),
        ]

        pipeline_result = pipeline._aggregate_results(results)

        # Average of 0.25, 0.5, 0.75
        expected_score = (0.25 + 0.5 + 0.75) / 3
        assert pipeline_result.risk_score == pytest.approx(expected_score)

    def test_aggregate_results_empty_list(self):
        """Test aggregating empty results list."""
        pipeline = SafetyPipeline()

        pipeline_result = pipeline._aggregate_results([])

        assert pipeline_result.overall_status == SafetyStatus.PASSED
        assert pipeline_result.risk_score == 0
        assert len(pipeline_result.blocking_issues) == 0
        assert len(pipeline_result.warnings) == 0

    def test_get_risk_assessment_very_low(self):
        """Test risk assessment for very low risk."""
        pipeline = SafetyPipeline()
        result = PipelineResult(
            results=[],
            overall_status=SafetyStatus.PASSED,
            risk_score=0.1,
            blocking_issues=[],
            warnings=[],
        )

        assessment = pipeline.get_risk_assessment(result)
        assert "Very Low Risk" in assessment

    def test_get_risk_assessment_low(self):
        """Test risk assessment for low risk."""
        pipeline = SafetyPipeline()
        result = PipelineResult(
            results=[],
            overall_status=SafetyStatus.PASSED,
            risk_score=0.3,
            blocking_issues=[],
            warnings=[],
        )

        assessment = pipeline.get_risk_assessment(result)
        assert "Low Risk" in assessment

    def test_get_risk_assessment_medium(self):
        """Test risk assessment for medium risk."""
        pipeline = SafetyPipeline()
        result = PipelineResult(
            results=[],
            overall_status=SafetyStatus.WARNING,
            risk_score=0.5,
            blocking_issues=[],
            warnings=[],
        )

        assessment = pipeline.get_risk_assessment(result)
        assert "Medium Risk" in assessment

    def test_get_risk_assessment_high(self):
        """Test risk assessment for high risk."""
        pipeline = SafetyPipeline()
        result = PipelineResult(
            results=[],
            overall_status=SafetyStatus.WARNING,
            risk_score=0.7,
            blocking_issues=[],
            warnings=[],
        )

        assessment = pipeline.get_risk_assessment(result)
        assert "High Risk" in assessment

    def test_get_risk_assessment_critical(self):
        """Test risk assessment for critical risk."""
        pipeline = SafetyPipeline()
        result = PipelineResult(
            results=[],
            overall_status=SafetyStatus.FAILED,
            risk_score=0.9,
            blocking_issues=["Critical issue"],
            warnings=[],
        )

        assessment = pipeline.get_risk_assessment(result)
        assert "Critical Risk" in assessment
