"""ADK-based agent with policy enforcement."""

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path
from datetime import datetime

from google.adk.agents import LlmAgent
from google.adk.runners import Runner, Event
from google.adk.sessions import InMemorySessionService
from google.genai import types

from adh_cli.core.policy_aware_function_tool import PolicyAwareFunctionTool
from adh_cli.core.tool_executor import ExecutionContext, ExecutionResult
from adh_cli.policies.policy_engine import PolicyEngine
from adh_cli.policies.policy_types import SupervisionLevel
from adh_cli.safety.pipeline import SafetyPipeline


class PolicyAwareLlmAgent:
    """ADK LlmAgent with integrated policy enforcement.

    This class uses Google ADK's LlmAgent for automatic tool orchestration
    while maintaining full policy enforcement, safety checks, and user
    confirmation workflows.
    """

    def __init__(
        self,
        model_name: str = "gemini-2.0-flash-exp",
        api_key: Optional[str] = None,
        policy_dir: Optional[Path] = None,
        confirmation_handler: Optional[Callable] = None,
        notification_handler: Optional[Callable] = None,
        audit_log_path: Optional[Path] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        """Initialize policy-aware LlmAgent.

        Args:
            model_name: Gemini model to use
            api_key: API key for Gemini
            policy_dir: Directory containing policy files
            confirmation_handler: Handler for user confirmations
            notification_handler: Handler for notifications
            audit_log_path: Path for audit log
            temperature: Model temperature
            max_tokens: Max output tokens
        """
        self.model_name = model_name
        self.api_key = api_key
        self.confirmation_handler = confirmation_handler
        self.notification_handler = notification_handler
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Initialize policy engine
        self.policy_engine = PolicyEngine(policy_dir=policy_dir)

        # Initialize safety pipeline
        self.safety_pipeline = SafetyPipeline()

        # Track registered tools
        self.tools: List[PolicyAwareFunctionTool] = []
        self.tool_handlers: Dict[str, Callable] = {}

        # Create audit logger
        self.audit_logger = self._create_audit_logger(audit_log_path)

        # Initialize LlmAgent and Runner (will be None if no API key)
        self.llm_agent = None
        self.runner = None
        self.session_service = None
        self.session_id = "default_session"
        self.user_id = "default_user"

        # Only initialize if we have an API key
        if api_key:
            self._init_adk_components()

    def _init_adk_components(self):
        """Initialize ADK components (LlmAgent, Runner, SessionService)."""
        # Initialize LlmAgent (without tools initially)
        self.llm_agent = LlmAgent(
            model=self.model_name,
            name="policy_aware_assistant",
            description="AI assistant with policy enforcement",
            instruction=self._get_system_instruction(),
            # tools will be set when tools are registered via _update_agent_tools
            generate_content_config=types.GenerateContentConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            ),
        )

        # Initialize session management
        self.session_service = InMemorySessionService()

        # Create runner
        self.runner = Runner(
            agent=self.llm_agent,
            app_name="adh_cli",
            session_service=self.session_service
        )

        # Initialize session asynchronously
        # Note: This will be handled in the first chat call

    def _get_system_instruction(self) -> str:
        """Get system instruction for the agent."""
        return """You are a helpful AI assistant for development tasks.

You have access to tools for file system operations and command execution.
All tool usage is subject to policy enforcement and safety checks.

IMPORTANT TOOL USAGE GUIDELINES:
- When you execute a tool, ALWAYS include the results in your response to the user
- Show the actual data returned by tools (file contents, directory listings, command output, etc.)
- Format tool results in a clear, readable way for the user
- Don't just say "I executed the tool" - show what you found
- When listing directories, show the files and folders
- When reading files, show the content (or a summary if it's long)
- When executing commands, show the output

When a tool requires confirmation, wait for user approval before proceeding.
Be proactive and helpful - use your tools to accomplish user goals without excessive back-and-forth."""

    async def _ensure_session_initialized(self):
        """Ensure the session is initialized."""
        if not self.session_service:
            return

        try:
            await self.session_service.create_session(
                app_name="adh_cli",
                user_id=self.user_id,
                session_id=self.session_id
            )
        except Exception:
            # Session may already exist, that's okay
            pass

    def _create_audit_logger(self, audit_log_path: Optional[Path]) -> Optional[Callable]:
        """Create audit logger if path provided."""
        if not audit_log_path:
            return None

        async def log_audit(**kwargs):
            """Log tool execution to audit file."""
            entry = {
                "timestamp": datetime.now().isoformat(),
                **kwargs
            }

            try:
                with open(audit_log_path, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception:
                # Don't fail if audit logging fails
                pass

        return log_audit

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable,
    ):
        """Register a tool with policy enforcement.

        Args:
            name: Tool name
            description: Tool description
            parameters: Parameter schema (not used by ADK, but kept for compatibility)
            handler: Async function to handle the tool
        """
        # Create policy-aware wrapper
        policy_tool = PolicyAwareFunctionTool(
            func=handler,
            tool_name=name,
            policy_engine=self.policy_engine,
            safety_pipeline=self.safety_pipeline,
            confirmation_handler=self.confirmation_handler,
            audit_logger=self.audit_logger,
        )

        # Add to our tracking
        self.tools.append(policy_tool)
        self.tool_handlers[name] = handler

        # Update LlmAgent with new tools (if initialized)
        if self.llm_agent:
            self._update_agent_tools()

    def _update_agent_tools(self):
        """Update the LlmAgent with current tools."""
        if not self.api_key:
            return

        # Recreate LlmAgent with updated tools
        # Only pass tools if we have some (don't pass empty list or None)
        llm_agent_kwargs = {
            "model": self.model_name,
            "name": "policy_aware_assistant",
            "description": "AI assistant with policy enforcement",
            "instruction": self._get_system_instruction(),
            "generate_content_config": types.GenerateContentConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            ),
        }

        if self.tools:
            llm_agent_kwargs["tools"] = self.tools

        self.llm_agent = LlmAgent(**llm_agent_kwargs)

        # Recreate runner with updated agent
        self.runner = Runner(
            agent=self.llm_agent,
            app_name="adh_cli",
            session_service=self.session_service
        )

    async def chat(
        self,
        message: str,
        context: Optional[ExecutionContext] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Send a message and get a response.

        Args:
            message: User message
            context: Execution context
            history: Conversation history (not used with ADK sessions)

        Returns:
            Agent response
        """
        # Check if ADK is initialized
        if not self.runner:
            return "⚠️ Agent not initialized. API key may be missing."

        context = context or ExecutionContext()

        # Ensure session is initialized
        await self._ensure_session_initialized()

        # Update session/user IDs from context
        user_id = context.user_id or self.user_id
        session_id = context.session_id or self.session_id

        # Create user message
        user_content = types.Content(
            role='user',
            parts=[types.Part(text=message)]
        )

        response_text = ""
        tool_execution_count = 0

        # Stream events from runner
        try:
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content
            ):
                # Handle function calls (for monitoring/notification)
                function_calls = event.get_function_calls()
                if function_calls:
                    tool_execution_count += len(function_calls)

                    if self.notification_handler:
                        for fc in function_calls:
                            await self.notification_handler(
                                f"🔧 Executing tool: {fc.name}"
                            )

                # Handle function responses (for monitoring)
                function_responses = event.get_function_responses()
                if function_responses and self.notification_handler:
                    await self.notification_handler(
                        f"✓ Tool execution complete"
                    )

                # Collect final response
                if event.is_final_response() and event.content:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_text += part.text

            return response_text or "Task completed."

        except PermissionError as e:
            # Policy blocked the tool
            return f"⛔ Action blocked by policy: {str(e)}"

        except Exception as e:
            # Other errors
            return f"❌ Error: {str(e)}"

    def update_policies(self, policy_dir: Path):
        """Update policies from a directory.

        Note: Requires recreating all tools with new policy engine.
        """
        # Create new policy engine
        self.policy_engine = PolicyEngine(policy_dir=policy_dir)

        # Store current tool metadata
        tool_metadata = [
            {
                "name": name,
                "handler": handler,
                "description": "",  # We don't store this
                "parameters": {},   # We don't store this
            }
            for name, handler in self.tool_handlers.items()
        ]

        # Clear current tools
        self.tools.clear()
        self.tool_handlers.clear()

        # Re-register all tools with new policy engine
        for tool_meta in tool_metadata:
            self.register_tool(
                name=tool_meta["name"],
                description=tool_meta["description"],
                parameters=tool_meta["parameters"],
                handler=tool_meta["handler"],
            )

    def set_user_preferences(self, preferences: Dict[str, Any]):
        """Set user preferences for policy evaluation."""
        self.policy_engine.user_preferences.update(preferences)

    @property
    def tool_executor(self):
        """Property for compatibility with PolicyAwareAgent interface.

        Returns a mock object that provides execute method.
        """
        # Create a simple wrapper for compatibility
        class ToolExecutorWrapper:
            def __init__(self, agent):
                self.agent = agent

            async def execute(self, tool_name: str, parameters: Dict[str, Any],
                            context: Optional[ExecutionContext] = None):
                """Execute a tool directly (for testing/compatibility)."""
                if tool_name not in self.agent.tool_handlers:
                    return ExecutionResult(
                        success=False,
                        error=f"Tool '{tool_name}' not found"
                    )

                try:
                    handler = self.agent.tool_handlers[tool_name]
                    result = await handler(**parameters)
                    return ExecutionResult(success=True, result=result)
                except Exception as e:
                    return ExecutionResult(success=False, error=str(e))

        return ToolExecutorWrapper(self)