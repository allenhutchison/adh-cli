"""Tool execution with policy enforcement and safety checks."""

import asyncio
from typing import Any, Dict, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
import json

from adh_cli.policies.policy_engine import PolicyEngine
from adh_cli.policies.policy_types import (
    ToolCall,
    PolicyDecision,
    SupervisionLevel,
    RiskLevel,
)
from adh_cli.safety.pipeline import SafetyPipeline
from adh_cli.safety.base_checker import SafetyStatus


@dataclass
class ExecutionContext:
    """Context for tool execution."""

    user_id: Optional[str] = None
    session_id: Optional[str] = None
    agent_name: Optional[str] = None
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result of tool execution."""

    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    policy_decision: Optional[PolicyDecision] = None
    safety_results: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolExecutor:
    """Executes tools with policy enforcement and safety checks."""

    def __init__(
        self,
        policy_engine: Optional[PolicyEngine] = None,
        safety_pipeline: Optional[SafetyPipeline] = None,
        confirmation_handler: Optional[Callable] = None,
        audit_logger: Optional[Callable] = None,
    ):
        """Initialize the tool executor.

        Args:
            policy_engine: Policy engine for evaluating tool calls
            safety_pipeline: Pipeline for running safety checks
            confirmation_handler: Async function to get user confirmation
            audit_logger: Function to log execution events
        """
        self.policy_engine = policy_engine or PolicyEngine()
        self.safety_pipeline = safety_pipeline or SafetyPipeline()
        self.confirmation_handler = confirmation_handler
        self.audit_logger = audit_logger
        self.tool_registry: Dict[str, Callable] = {}

    def register_tool(self, name: str, handler: Callable):
        """Register a tool handler.

        Args:
            name: Tool name
            handler: Async function that executes the tool
        """
        self.tool_registry[name] = handler

    async def execute(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        context: Optional[ExecutionContext] = None,
    ) -> ExecutionResult:
        """Execute a tool with policy enforcement.

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            context: Execution context

        Returns:
            ExecutionResult with outcome and details
        """
        context = context or ExecutionContext()
        start_time = datetime.now()

        # Create tool call object
        tool_call = ToolCall(
            tool_name=tool_name,
            parameters=parameters,
            context={
                "user_id": context.user_id,
                "session_id": context.session_id,
            },
            agent_name=context.agent_name,
            request_id=context.request_id,
        )

        # Evaluate policy
        decision = self.policy_engine.evaluate_tool_call(tool_call)

        # Log policy evaluation
        await self._log_event("policy_evaluated", tool_call, decision)

        # Check if denied
        if not decision.allowed:
            return ExecutionResult(
                success=False,
                error=decision.reason or "Tool execution denied by policy",
                policy_decision=decision,
            )

        # Handle supervision levels
        if decision.supervision_level == SupervisionLevel.DENY:
            return ExecutionResult(
                success=False,
                error="Tool execution denied",
                policy_decision=decision,
            )

        # Get user confirmation if needed
        if decision.requires_confirmation:
            confirmed = await self._get_confirmation(tool_call, decision)
            if not confirmed:
                return ExecutionResult(
                    success=False,
                    error="User declined execution",
                    policy_decision=decision,
                )

        # Run safety checks
        safety_results = await self._run_safety_checks(tool_call, decision)

        # Check if any safety check failed
        failed_checks = [
            r for r in safety_results
            if r.status == SafetyStatus.FAILED
        ]

        if failed_checks:
            return ExecutionResult(
                success=False,
                error=f"Safety checks failed: {', '.join(c.message for c in failed_checks)}",
                policy_decision=decision,
                safety_results=safety_results,
            )

        # Check for warnings that need override
        warning_checks = [
            r for r in safety_results
            if r.status == SafetyStatus.WARNING and not r.can_override
        ]

        if warning_checks and not await self._get_override_confirmation(warning_checks):
            return ExecutionResult(
                success=False,
                error="User declined to override safety warnings",
                policy_decision=decision,
                safety_results=safety_results,
            )

        # Execute the tool
        try:
            handler = self.tool_registry.get(tool_name)
            if not handler:
                return ExecutionResult(
                    success=False,
                    error=f"Tool '{tool_name}' not found in registry",
                    policy_decision=decision,
                )

            # Apply any parameter modifications from safety checks
            modified_params = self._apply_parameter_modifications(
                parameters, safety_results
            )

            # Execute with timeout if specified
            timeout = decision.metadata.get("timeout", 30.0)
            result = await asyncio.wait_for(
                handler(**modified_params),
                timeout=timeout
            )

            execution_time = (datetime.now() - start_time).total_seconds()

            # Log successful execution
            await self._log_event(
                "tool_executed",
                tool_call,
                decision,
                result=result,
                execution_time=execution_time,
            )

            return ExecutionResult(
                success=True,
                result=result,
                execution_time=execution_time,
                policy_decision=decision,
                safety_results=safety_results,
            )

        except asyncio.TimeoutError:
            return ExecutionResult(
                success=False,
                error=f"Tool execution timed out after {timeout} seconds",
                policy_decision=decision,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
                policy_decision=decision,
            )

    async def _get_confirmation(
        self, tool_call: ToolCall, decision: PolicyDecision
    ) -> bool:
        """Get user confirmation for tool execution.

        Args:
            tool_call: The tool call requiring confirmation
            decision: Policy decision with confirmation details

        Returns:
            True if user confirms, False otherwise
        """
        if not self.confirmation_handler:
            # No handler, assume confirmed for testing
            return True

        return await self.confirmation_handler(
            tool_call=tool_call,
            decision=decision,
            message=decision.confirmation_message,
        )

    async def _get_override_confirmation(self, warnings: List[Any]) -> bool:
        """Get user confirmation to override warnings.

        Args:
            warnings: List of safety warnings

        Returns:
            True if user confirms override, False otherwise
        """
        if not self.confirmation_handler:
            return False

        message = "Safety warnings detected:\n"
        for warning in warnings:
            message += f"  - {warning.message}\n"
        message += "\nDo you want to proceed anyway?"

        return await self.confirmation_handler(
            message=message,
            warnings=warnings,
        )

    async def _run_safety_checks(
        self, tool_call: ToolCall, decision: PolicyDecision
    ) -> List[Any]:
        """Run safety checks from policy decision.

        Args:
            tool_call: Tool call to check
            decision: Policy decision with safety checks

        Returns:
            List of safety check results
        """
        if not decision.safety_checks:
            return []

        # Configure pipeline with checks from decision
        for check in decision.safety_checks:
            self.safety_pipeline.add_checker(
                check.checker_class,
                check.config,
                required=check.required,
            )

        # Run pipeline
        results = await self.safety_pipeline.run(tool_call)
        return results.check_results

    def _apply_parameter_modifications(
        self, parameters: Dict[str, Any], safety_results: List[Any]
    ) -> Dict[str, Any]:
        """Apply any parameter modifications from safety checks.

        Args:
            parameters: Original parameters
            safety_results: Results from safety checks

        Returns:
            Modified parameters
        """
        modified = parameters.copy()

        for result in safety_results:
            if hasattr(result, 'parameter_modifications'):
                modified.update(result.parameter_modifications)

        return modified

    async def _log_event(
        self,
        event_type: str,
        tool_call: ToolCall,
        decision: Optional[PolicyDecision] = None,
        **kwargs
    ):
        """Log an execution event.

        Args:
            event_type: Type of event
            tool_call: Tool call being executed
            decision: Policy decision if available
            **kwargs: Additional event data
        """
        if not self.audit_logger:
            return

        event_data = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "tool_name": tool_call.tool_name,
            "agent_name": tool_call.agent_name,
            "request_id": tool_call.request_id,
        }

        if decision:
            event_data.update({
                "allowed": decision.allowed,
                "supervision_level": decision.supervision_level.value,
                "risk_level": decision.risk_level.value,
            })

        event_data.update(kwargs)

        await self.audit_logger(event_data)


class PolicyAwareToolRegistry:
    """Registry for tools with built-in policy enforcement."""

    def __init__(self, executor: ToolExecutor):
        """Initialize the registry.

        Args:
            executor: Tool executor with policy enforcement
        """
        self.executor = executor

    def register(self, name: str):
        """Decorator to register a tool.

        Args:
            name: Tool name

        Returns:
            Decorator function
        """
        def decorator(func: Callable):
            self.executor.register_tool(name, func)
            return func
        return decorator

    async def execute(
        self,
        tool_name: str,
        **parameters
    ) -> ExecutionResult:
        """Execute a tool with policy enforcement.

        Args:
            tool_name: Name of tool to execute
            **parameters: Tool parameters

        Returns:
            Execution result
        """
        return await self.executor.execute(tool_name, parameters)