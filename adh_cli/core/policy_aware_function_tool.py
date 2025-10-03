"""Policy-aware wrapper for ADK FunctionTool."""

import functools
import inspect
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING
from google.adk.tools import FunctionTool
from adh_cli.policies.policy_engine import PolicyEngine
from adh_cli.policies.policy_types import ToolCall, PolicyDecision
from adh_cli.safety.pipeline import SafetyPipeline, SafetyStatus
from adh_cli.core.tool_executor import ExecutionContext

if TYPE_CHECKING:
    from adh_cli.ui.tool_execution_manager import ToolExecutionManager


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
        execution_manager: Optional["ToolExecutionManager"] = None,
    ):
        """Initialize policy-aware function tool.

        Args:
            func: The actual tool function to execute
            tool_name: Name of the tool for policy lookup
            policy_engine: Policy engine for evaluation
            safety_pipeline: Safety pipeline for checks
            confirmation_handler: Handler for user confirmations (not used directly)
            audit_logger: Logger for audit trail
            execution_manager: Optional execution manager for UI tracking
        """
        self.tool_name = tool_name
        self.policy_engine = policy_engine
        self.safety_pipeline = safety_pipeline
        self.confirmation_handler = confirmation_handler
        self.audit_logger = audit_logger
        self.execution_manager = execution_manager
        self.original_func = func

        # Create policy-wrapped function with proper metadata preservation
        @functools.wraps(func)
        async def policy_wrapped_func(*args, **kwargs):
            """Wrapper that enforces policy before execution."""
            execution_id = None

            # Convert positional args to keyword args based on function signature
            if args:
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                for i, arg in enumerate(args):
                    if i < len(param_names):
                        kwargs[param_names[i]] = arg

            # 1. Create tool call for policy evaluation
            tool_call = ToolCall(
                tool_name=tool_name,
                parameters=kwargs,
                context={}
            )

            # 2. Evaluate against policy
            decision = self.policy_engine.evaluate_tool_call(tool_call)

            # 3. Track execution start (if manager available)
            if self.execution_manager:
                execution_info = self.execution_manager.create_execution(
                    tool_name=tool_name,
                    parameters=kwargs,
                    policy_decision=decision,
                )
                execution_id = execution_info.id

            # 4. Check if tool is blocked
            if not decision.allowed:
                error_msg = f"Tool '{tool_name}' blocked by policy"
                if decision.reason:
                    error_msg += f": {decision.reason}"

                # Track blocked execution
                if self.execution_manager and execution_id:
                    self.execution_manager.block_execution(execution_id, reason=error_msg)

                raise PermissionError(error_msg)

            # 5. Handle confirmation requirement (HUMAN-IN-THE-LOOP)
            if decision.requires_confirmation:
                user_confirmed = False

                # Use execution manager if available (preferred - shows in UI)
                if self.execution_manager and execution_id:
                    # Show UI confirmation widget and wait for user response
                    self.execution_manager.require_confirmation(execution_id, decision)

                    # BLOCK here until user confirms or cancels
                    user_confirmed = await self.execution_manager.wait_for_confirmation(execution_id)

                # Fall back to confirmation handler if no execution manager
                elif self.confirmation_handler:
                    user_confirmed = await self.confirmation_handler(
                        tool_call=tool_call,
                        decision=decision,
                        message=decision.confirmation_message
                    )

                # If neither is available, deny by default (fail-safe)
                else:
                    user_confirmed = False

                if not user_confirmed:
                    # User cancelled - abort execution
                    error_msg = f"Tool '{tool_name}' execution cancelled by user"
                    raise PermissionError(error_msg)

            # 6. Run safety checks
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

            # 7. Log audit trail before execution
            if self.audit_logger:
                await self.audit_logger(
                    tool_name=tool_name,
                    parameters=kwargs,
                    decision=decision.dict() if hasattr(decision, 'dict') else str(decision),
                    phase="pre_execution"
                )

            # 8. Mark execution as started
            if self.execution_manager and execution_id:
                self.execution_manager.start_execution(execution_id)

            # 9. Execute original function
            try:
                result = await func(**kwargs)

                # Track successful completion
                if self.execution_manager and execution_id:
                    self.execution_manager.complete_execution(
                        execution_id,
                        success=True,
                        result=result
                    )

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
                # Track failed execution
                if self.execution_manager and execution_id:
                    self.execution_manager.complete_execution(
                        execution_id,
                        success=False,
                        error=str(e),
                        error_type=type(e).__name__
                    )

                # Log failure
                if self.audit_logger:
                    await self.audit_logger(
                        tool_name=tool_name,
                        parameters=kwargs,
                        error=str(e),
                        success=False,
                        phase="execution_error"
                    )

                # Re-raise with enhanced error message including calling signature
                error_type = type(e).__name__
                param_str = ", ".join(f"{k}={repr(v)}" for k, v in kwargs.items())
                enhanced_msg = f"{error_type} in {tool_name}({param_str}): {str(e)}"

                # Create new exception with enhanced message but preserve original type
                if isinstance(e, (FileNotFoundError, PermissionError, ValueError, TypeError)):
                    raise type(e)(enhanced_msg) from e
                else:
                    # For unknown exception types, wrap in RuntimeError
                    raise RuntimeError(enhanced_msg) from e

        # Override function name for tool identification
        # Note: functools.wraps() already copied __annotations__, __module__, __doc__, etc.
        policy_wrapped_func.__name__ = tool_name

        # Ensure __signature__ is properly set for ADK introspection
        # (functools.wraps doesn't copy __signature__, so we do it manually)
        policy_wrapped_func.__signature__ = inspect.signature(func)

        # Initialize parent FunctionTool with our wrapped function
        # Note: We don't use ADK's require_confirmation parameter because we handle
        # confirmation ourselves via the UI (ToolExecutionManager + ToolExecutionWidget).
        # This prevents brittle prompt-based confirmation that can be defeated by
        # prompt injection. Our approach blocks execution until the user clicks
        # Confirm/Cancel in the UI.
        super().__init__(
            func=policy_wrapped_func,
            require_confirmation=None  # We handle confirmation via UI, not ADK
        )