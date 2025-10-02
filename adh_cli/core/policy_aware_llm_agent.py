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
from adh_cli.ui.tool_execution_manager import ToolExecutionManager
from adh_cli.agents.agent_loader import AgentLoader


class PolicyAwareLlmAgent:
    """ADK LlmAgent with integrated policy enforcement.

    This class uses Google ADK's LlmAgent for automatic tool orchestration
    while maintaining full policy enforcement, safety checks, and user
    confirmation workflows.
    """

    def __init__(
        self,
        model_name: str = "gemini-flash-latest",
        api_key: Optional[str] = None,
        policy_dir: Optional[Path] = None,
        confirmation_handler: Optional[Callable] = None,
        notification_handler: Optional[Callable] = None,
        audit_log_path: Optional[Path] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        agent_name: str = "orchestrator",
        # Tool execution manager callbacks
        on_execution_start: Optional[Callable] = None,
        on_execution_update: Optional[Callable] = None,
        on_execution_complete: Optional[Callable] = None,
        on_confirmation_required: Optional[Callable] = None,
    ):
        """Initialize policy-aware LlmAgent.

        Args:
            model_name: Gemini model to use (overridden by agent definition)
            api_key: API key for Gemini
            policy_dir: Directory containing policy files
            confirmation_handler: Handler for user confirmations
            notification_handler: Handler for notifications
            audit_log_path: Path for audit log
            temperature: Model temperature (overridden by agent definition)
            max_tokens: Max output tokens (overridden by agent definition)
            agent_name: Name of the agent to load from agents/ directory
            on_execution_start: Callback when execution starts
            on_execution_update: Callback when execution state updates
            on_execution_complete: Callback when execution completes
            on_confirmation_required: Callback when confirmation needed
        """
        self.agent_name = agent_name
        self.api_key = api_key
        self.confirmation_handler = confirmation_handler
        self.notification_handler = notification_handler

        # Load agent definition
        try:
            loader = AgentLoader()
            self.agent_definition = loader.load(agent_name)

            # Use agent configuration (overriding defaults)
            self.model_name = self.agent_definition.model
            self.temperature = self.agent_definition.temperature
            self.max_tokens = self.agent_definition.max_tokens
        except (FileNotFoundError, ValueError) as e:
            # Fallback to defaults if agent loading fails
            self.agent_definition = None
            self.model_name = model_name
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

        # Create tool execution manager
        self.execution_manager = ToolExecutionManager(
            on_execution_start=on_execution_start,
            on_execution_update=on_execution_update,
            on_execution_complete=on_execution_complete,
            on_confirmation_required=on_confirmation_required,
        )

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
        # If we have a loaded agent definition, use it
        if self.agent_definition:
            # Generate tool descriptions
            tool_descriptions = self._generate_tool_descriptions()

            # Render the system prompt with variables
            return self.agent_definition.render_system_prompt(
                variables={},
                tool_descriptions=tool_descriptions
            )

        # Fallback to default prompt if no agent definition
        return """You are a helpful AI assistant for development tasks.

You have access to tools for file system operations and command execution.
All tool usage is subject to policy enforcement and safety checks.

IMPORTANT TOOL USAGE GUIDELINES:
- IMMEDIATELY use tools to accomplish user requests - don't ask for permission unless required by policy
- When you execute a tool, ALWAYS include the results in your response to the user
- Show the actual data returned by tools (file contents, directory listings, command output, etc.)
- Format tool results in a clear, readable way for the user
- Don't just say "I executed the tool" - show what you found
- When listing directories, show the files and folders
- When reading files, show the content (or a summary if it's long)
- When executing commands, show the output

TOOL EXECUTION BEHAVIOR:
- If the user asks about "this directory" or "current directory", use "." as the path parameter
- Execute tools RIGHT AWAY - don't ask clarifying questions unless absolutely necessary
- Only wait for user confirmation when the policy system requires it (you'll be prompted)
- Don't ask "do you want me to..." - just do it and show results
- Be direct and action-oriented, not cautious or hesitant

Your goal is to be helpful and efficient - use your tools to get answers immediately."""

    def _generate_tool_descriptions(self) -> str:
        """Generate formatted descriptions of available tools.

        Returns:
            Formatted string with tool descriptions
        """
        if not self.tools:
            return "No tools currently available."

        descriptions = []
        for tool in self.tools:
            # Get the tool's name and description
            tool_name = tool.tool_name if hasattr(tool, 'tool_name') else "unknown"

            # Try to get description from the function's docstring
            description = ""
            if hasattr(tool, 'func') and tool.func.__doc__:
                # Get first line of docstring
                description = tool.func.__doc__.strip().split('\n')[0]

            descriptions.append(f"- **{tool_name}**: {description}")

        return "\n".join(descriptions)

    async def _ensure_session_initialized(self):
        """Ensure the session is initialized."""
        if not self.session_service:
            return

        # Check if session already exists to avoid recreating it
        try:
            existing_session = await self.session_service.get_session(
                app_name="adh_cli",
                user_id=self.user_id,
                session_id=self.session_id
            )

            # Only create session if it doesn't exist
            if not existing_session:
                await self.session_service.create_session(
                    app_name="adh_cli",
                    user_id=self.user_id,
                    session_id=self.session_id
                )
        except Exception as e:
            # If get_session fails, try to create
            try:
                await self.session_service.create_session(
                    app_name="adh_cli",
                    user_id=self.user_id,
                    session_id=self.session_id
                )
            except Exception:
                # Session may already exist or other error
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
            execution_manager=self.execution_manager,
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

        # Stream events from runner
        try:
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content
            ):
                # Note: Tool execution is now tracked via ToolExecutionManager
                # and displayed in the UI notification area, so we don't need
                # pop-up notifications here

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