"""Policy-aware ADK agent implementation."""

from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import json

from google import genai
from google.genai.types import Tool, FunctionDeclaration, Schema

from adh_cli.core.tool_executor import ToolExecutor, ExecutionContext, ExecutionResult
from adh_cli.policies.policy_engine import PolicyEngine
from adh_cli.safety.pipeline import SafetyPipeline
from adh_cli.policies.policy_types import SupervisionLevel


class PolicyAwareAgent:
    """ADK agent with integrated policy enforcement."""

    def __init__(
        self,
        model_name: str = "models/gemini-flash-latest",
        api_key: Optional[str] = None,
        policy_dir: Optional[Path] = None,
        confirmation_handler: Optional[Any] = None,
        notification_handler: Optional[Any] = None,
        audit_log_path: Optional[Path] = None,
    ):
        """Initialize the policy-aware agent.

        Args:
            model_name: Gemini model to use
            api_key: API key for Gemini
            policy_dir: Directory containing policy files
            confirmation_handler: Handler for user confirmations
            notification_handler: Handler for notifications
            audit_log_path: Path for audit log file
        """
        self.model_name = model_name
        self.api_key = api_key

        # Initialize policy engine
        self.policy_engine = PolicyEngine(policy_dir=policy_dir)

        # Initialize safety pipeline
        self.safety_pipeline = SafetyPipeline()

        # Initialize tool executor
        self.tool_executor = ToolExecutor(
            policy_engine=self.policy_engine,
            safety_pipeline=self.safety_pipeline,
            confirmation_handler=confirmation_handler,
            audit_logger=self._create_audit_logger(audit_log_path),
        )

        self.confirmation_handler = confirmation_handler
        self.notification_handler = notification_handler

        # Tool definitions for Gemini
        self.tool_definitions: List[Tool] = []
        self.tool_handlers: Dict[str, Any] = {}

        # Initialize Gemini client
        self._init_client()

    def _init_client(self):
        """Initialize the Gemini client."""
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Any,
    ):
        """Register a tool with the agent.

        Args:
            name: Tool name
            description: Tool description
            parameters: Parameter schema
            handler: Async function to handle the tool
        """
        # Register with executor
        self.tool_executor.register_tool(name, handler)

        # Store handler reference
        self.tool_handlers[name] = handler

        # Create Gemini tool definition
        func_decl = FunctionDeclaration(
            name=name,
            description=description,
            parameters=Schema(
                type="object",
                properties=parameters,
            ),
        )

        self.tool_definitions.append(Tool(function_declarations=[func_decl]))

    async def chat(
        self,
        message: str,
        context: Optional[ExecutionContext] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Send a message to the agent and get a response.

        Args:
            message: User message
            context: Execution context
            history: Conversation history

        Returns:
            Agent response
        """
        context = context or ExecutionContext()

        # Build conversation
        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        # Generate response with tools
        response = await self._generate_response(messages, context)

        return response

    async def _generate_response(
        self,
        messages: List[Dict[str, str]],
        context: ExecutionContext,
    ) -> str:
        """Generate a response using Gemini with tool execution.

        Args:
            messages: Conversation messages
            context: Execution context

        Returns:
            Generated response
        """
        # Create Gemini request with tools
        generation_config = {
            "temperature": 0.7,
            "max_output_tokens": 2048,
        }

        # Generate with automatic function calling
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=messages,
            tools=self.tool_definitions,
            generation_config=generation_config,
        )

        # Process response
        if response.candidates:
            candidate = response.candidates[0]

            # Check for function calls
            if hasattr(candidate.content, 'parts'):
                for part in candidate.content.parts:
                    if hasattr(part, 'function_call'):
                        # Execute tool with policy enforcement
                        tool_result = await self._execute_tool_call(
                            part.function_call,
                            context
                        )

                        # Add tool result to conversation and continue
                        messages.append({
                            "role": "assistant",
                            "content": str(candidate.content.parts[0].text) if hasattr(candidate.content.parts[0], 'text') else "",
                        })
                        messages.append({
                            "role": "function",
                            "name": part.function_call.name,
                            "content": json.dumps(tool_result),
                        })

                        # Generate follow-up response
                        return await self._generate_response(messages, context)

            # Return text response
            if candidate.content.parts and hasattr(candidate.content.parts[0], 'text'):
                return candidate.content.parts[0].text

        return "I couldn't generate a response."

    async def _execute_tool_call(
        self,
        function_call: Any,
        context: ExecutionContext,
    ) -> Dict[str, Any]:
        """Execute a tool call with policy enforcement.

        Args:
            function_call: Function call from Gemini
            context: Execution context

        Returns:
            Tool execution result
        """
        tool_name = function_call.name
        parameters = json.loads(function_call.args) if hasattr(function_call, 'args') else {}

        # Execute with policy enforcement
        result = await self.tool_executor.execute(
            tool_name=tool_name,
            parameters=parameters,
            context=context,
        )

        # Handle notifications
        if result.policy_decision:
            await self._handle_supervision(result)

        # Return result for Gemini
        if result.success:
            return {"success": True, "result": result.result}
        else:
            return {"success": False, "error": result.error}

    async def _handle_supervision(self, result: ExecutionResult):
        """Handle supervision requirements from policy decision.

        Args:
            result: Execution result with policy decision
        """
        if not result.policy_decision:
            return

        decision = result.policy_decision

        # Send notifications based on supervision level
        if decision.supervision_level == SupervisionLevel.NOTIFY:
            if self.notification_handler:
                await self.notification_handler(
                    f"Tool executed: {result.policy_decision}",
                    level="info"
                )
        elif decision.supervision_level == SupervisionLevel.MANUAL:
            if self.notification_handler:
                await self.notification_handler(
                    f"Manual review performed for high-risk operation",
                    level="warning"
                )

    def _create_audit_logger(self, log_path: Optional[Path]):
        """Create an audit logger function.

        Args:
            log_path: Path to audit log file

        Returns:
            Async function for logging
        """
        if not log_path:
            return None

        async def log_event(event_data: Dict[str, Any]):
            """Log an event to the audit file."""
            log_path.parent.mkdir(parents=True, exist_ok=True)

            with open(log_path, "a") as f:
                f.write(json.dumps(event_data) + "\n")

        return log_event

    async def execute_with_policies(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        context: Optional[ExecutionContext] = None,
    ) -> ExecutionResult:
        """Execute a tool directly with policy enforcement.

        Args:
            tool_name: Name of tool to execute
            parameters: Tool parameters
            context: Execution context

        Returns:
            Execution result
        """
        return await self.tool_executor.execute(
            tool_name=tool_name,
            parameters=parameters,
            context=context or ExecutionContext(),
        )

    def update_policies(self, policy_dir: Path):
        """Update policies from a new directory.

        Args:
            policy_dir: New policy directory
        """
        self.policy_engine = PolicyEngine(policy_dir=policy_dir)
        self.tool_executor.policy_engine = self.policy_engine

    def set_user_preferences(self, preferences: Dict[str, Any]):
        """Set user preferences for policy engine.

        Args:
            preferences: User preference settings
        """
        self.policy_engine.user_preferences = preferences