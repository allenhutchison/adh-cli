"""Policy-aware wrapper for ADK FunctionTool."""

from typing import Any, Callable, Dict, Optional
from google.adk.tools import FunctionTool
from adh_cli.policies.policy_engine import PolicyEngine
from adh_cli.policies.policy_types import ToolCall, PolicyDecision
from adh_cli.safety.pipeline import SafetyPipeline, SafetyStatus
from adh_cli.core.tool_executor import ExecutionContext


class SafetyError(Exception):
    """Exception raised when safety checks fail."""
    pass


class PolicyAwareFunctionTool(FunctionTool):
    """FunctionTool with integrated policy enforcement and safety checks.

    This class wraps ADK's FunctionTool to add:
    - Policy evaluation before execution
    - Safety checks with parameter modifications
    - Audit logging
    - Confirmation requirements based on policy
    """

    def __init__(
        self,
        func: Callable,
        tool_name: str,
        policy_engine: PolicyEngine,
        safety_pipeline: SafetyPipeline,
        confirmation_handler: Optional[Callable] = None,
        audit_logger: Optional[Callable] = None,
    ):
        """Initialize policy-aware function tool.

        Args:
            func: The actual tool function to execute
            tool_name: Name of the tool for policy lookup
            policy_engine: Policy engine for evaluation
            safety_pipeline: Safety pipeline for checks
            confirmation_handler: Handler for user confirmations (not used directly)
            audit_logger: Logger for audit trail
        """
        self.tool_name = tool_name
        self.policy_engine = policy_engine
        self.safety_pipeline = safety_pipeline
        self.confirmation_handler = confirmation_handler
        self.audit_logger = audit_logger
        self.original_func = func

        # Create policy-wrapped function
        async def policy_wrapped_func(**kwargs):
            """Wrapper that enforces policy before execution."""

            # 1. Create tool call for policy evaluation
            tool_call = ToolCall(
                tool_name=tool_name,
                parameters=kwargs,
                context={}
            )

            # 2. Evaluate against policy
            decision = self.policy_engine.evaluate_tool_call(tool_call)

            # 3. Check if tool is blocked
            if not decision.allowed:
                error_msg = f"Tool '{tool_name}' blocked by policy"
                if decision.reason:
                    error_msg += f": {decision.reason}"
                raise PermissionError(error_msg)

            # 4. Run safety checks
            if decision.safety_checks:
                try:
                    pipeline_result = await self.safety_pipeline.run_checks(
                        tool_call,
                        decision.safety_checks
                    )

                    # Check for failures
                    failed_checks = [
                        r for r in pipeline_result.results
                        if r.status == SafetyStatus.FAILED
                    ]

                    if failed_checks:
                        errors = [c.message for c in failed_checks]
                        raise SafetyError(
                            f"Safety check(s) failed: {', '.join(errors)}"
                        )

                    # Apply parameter modifications from safety checks
                    for result in pipeline_result.results:
                        if hasattr(result, 'parameter_modifications') and result.parameter_modifications:
                            kwargs.update(result.parameter_modifications)

                except Exception as e:
                    # If safety checks fail to run, log and continue
                    if self.audit_logger:
                        await self.audit_logger(
                            tool_name=tool_name,
                            parameters=kwargs,
                            error=f"Safety check error: {str(e)}",
                            success=False
                        )
                    # Re-raise if it's a SafetyError
                    if isinstance(e, SafetyError):
                        raise

            # 5. Log audit trail before execution
            if self.audit_logger:
                await self.audit_logger(
                    tool_name=tool_name,
                    parameters=kwargs,
                    decision=decision.dict() if hasattr(decision, 'dict') else str(decision),
                    phase="pre_execution"
                )

            # 6. Execute original function
            try:
                result = await func(**kwargs)

                # Log success
                if self.audit_logger:
                    await self.audit_logger(
                        tool_name=tool_name,
                        parameters=kwargs,
                        result=str(result)[:200],  # Truncate long results
                        success=True,
                        phase="post_execution"
                    )

                return result

            except Exception as e:
                # Log failure
                if self.audit_logger:
                    await self.audit_logger(
                        tool_name=tool_name,
                        parameters=kwargs,
                        error=str(e),
                        success=False,
                        phase="execution_error"
                    )
                raise

        # Create confirmation checker function
        def needs_confirmation(**kwargs) -> bool:
            """Determine if confirmation is needed based on policy.

            This is called by ADK's FunctionTool to determine if the user
            should confirm before executing the tool.

            Args:
                **kwargs: Tool parameters

            Returns:
                True if confirmation is required, False otherwise
            """
            tool_call = ToolCall(
                tool_name=tool_name,
                parameters=kwargs,
                context={}
            )
            decision = self.policy_engine.evaluate_tool_call(tool_call)
            return decision.requires_confirmation

        # Initialize parent FunctionTool with our wrapped function
        super().__init__(
            func=policy_wrapped_func,
            require_confirmation=needs_confirmation
        )