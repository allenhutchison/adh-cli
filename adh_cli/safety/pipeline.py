"""Safety check pipeline for running multiple safety checks."""

import asyncio
from typing import Dict, List, Type
from dataclasses import dataclass

from .base_checker import SafetyChecker, SafetyResult, SafetyStatus
from ..policies.policy_types import ToolCall, RiskLevel, SafetyCheck


@dataclass
class PipelineResult:
    """Aggregated result from the safety pipeline."""

    results: List[SafetyResult]
    overall_status: SafetyStatus
    risk_score: float
    blocking_issues: List[str]
    warnings: List[str]

    @property
    def is_safe(self) -> bool:
        """Check if execution can proceed."""
        return (
            self.overall_status != SafetyStatus.FAILED
            and len(self.blocking_issues) == 0
        )

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0


class SafetyPipeline:
    """Pipeline for running safety checks on tool calls."""

    def __init__(self):
        """Initialize the safety pipeline."""
        self.checkers: Dict[str, Type[SafetyChecker]] = {}
        self._register_default_checkers()

    def _register_default_checkers(self):
        """Register default safety checkers."""
        # Import and register built-in checkers
        from .checkers import (
            BackupChecker,
            DiskSpaceChecker,
            SensitiveDataChecker,
            SizeLimitChecker,
            CommandValidator,
            SandboxChecker,
            PermissionChecker,
        )

        self.register_checker("BackupChecker", BackupChecker)
        self.register_checker("DiskSpaceChecker", DiskSpaceChecker)
        self.register_checker("SensitiveDataChecker", SensitiveDataChecker)
        self.register_checker("SizeLimitChecker", SizeLimitChecker)
        self.register_checker("CommandValidator", CommandValidator)
        self.register_checker("SandboxChecker", SandboxChecker)
        self.register_checker("PermissionChecker", PermissionChecker)

    def register_checker(self, name: str, checker_class: Type[SafetyChecker]):
        """Register a safety checker class.

        Args:
            name: Name to register the checker under
            checker_class: The checker class
        """
        self.checkers[name] = checker_class

    async def run_checks(
        self, tool_call: ToolCall, safety_checks: List[SafetyCheck]
    ) -> PipelineResult:
        """Run all specified safety checks.

        Args:
            tool_call: The tool invocation to check
            safety_checks: List of safety checks to run

        Returns:
            Aggregated pipeline result
        """
        results = []
        tasks = []

        # Create checker instances and tasks
        for check in safety_checks:
            checker_class = self.checkers.get(check.checker_class)
            if checker_class:
                checker = checker_class(check.config)
                # Run check with timeout
                task = asyncio.create_task(
                    self._run_check_with_timeout(checker, tool_call, check.timeout)
                )
                tasks.append(task)

        # Wait for all checks to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        return self._aggregate_results(results)

    async def _run_check_with_timeout(
        self, checker: SafetyChecker, tool_call: ToolCall, timeout: float
    ) -> SafetyResult:
        """Run a safety check with timeout.

        Args:
            checker: The checker to run
            tool_call: The tool call to check
            timeout: Timeout in seconds

        Returns:
            SafetyResult or error result if timeout/exception
        """
        try:
            return await asyncio.wait_for(checker.check(tool_call), timeout=timeout)
        except asyncio.TimeoutError:
            return SafetyResult(
                checker_name=checker.name,
                status=SafetyStatus.ERROR,
                message=f"Check timed out after {timeout} seconds",
                risk_level=RiskLevel.MEDIUM,
            )
        except Exception as e:
            return SafetyResult(
                checker_name=checker.name,
                status=SafetyStatus.ERROR,
                message=f"Check failed: {str(e)}",
                risk_level=RiskLevel.MEDIUM,
            )

    def _aggregate_results(self, results: List[SafetyResult]) -> PipelineResult:
        """Aggregate individual check results.

        Args:
            results: List of safety check results

        Returns:
            Aggregated pipeline result
        """
        overall_status = SafetyStatus.PASSED
        blocking_issues = []
        warnings = []
        risk_scores = []

        for result in results:
            if isinstance(result, Exception):
                # Handle exceptions from gather
                blocking_issues.append(f"Check error: {str(result)}")
                overall_status = SafetyStatus.ERROR
                # Exceptions are treated as MEDIUM risk
                risk_scores.append(0.5)
                continue

            # Track warnings
            if result.status == SafetyStatus.WARNING:
                warnings.append(result.message)
                if overall_status == SafetyStatus.PASSED:
                    overall_status = SafetyStatus.WARNING

            # Track failures
            if result.status == SafetyStatus.FAILED:
                if result.is_blocking:
                    blocking_issues.append(result.message)
                    overall_status = SafetyStatus.FAILED
                else:
                    warnings.append(f"[Overridable] {result.message}")
                    if overall_status == SafetyStatus.PASSED:
                        overall_status = SafetyStatus.WARNING

            # Calculate risk score
            risk_value = {
                RiskLevel.NONE: 0,
                RiskLevel.LOW: 0.25,
                RiskLevel.MEDIUM: 0.5,
                RiskLevel.HIGH: 0.75,
                RiskLevel.CRITICAL: 1.0,
            }
            risk_scores.append(risk_value.get(result.risk_level, 0.5))

        # Calculate average risk score
        risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else 0

        return PipelineResult(
            results=results,
            overall_status=overall_status,
            risk_score=risk_score,
            blocking_issues=blocking_issues,
            warnings=warnings,
        )

    def get_risk_assessment(self, pipeline_result: PipelineResult) -> str:
        """Generate a human-readable risk assessment.

        Args:
            pipeline_result: Result from pipeline run

        Returns:
            Risk assessment message
        """
        if pipeline_result.risk_score < 0.2:
            return "Very Low Risk - Safe to proceed"
        elif pipeline_result.risk_score < 0.4:
            return "Low Risk - Minimal concerns"
        elif pipeline_result.risk_score < 0.6:
            return "Medium Risk - Proceed with caution"
        elif pipeline_result.risk_score < 0.8:
            return "High Risk - Careful review recommended"
        else:
            return "Critical Risk - Manual review required"
