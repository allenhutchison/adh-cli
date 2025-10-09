"""ADK-based agent with policy enforcement."""

import asyncio
import json
import re
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path
from datetime import datetime

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.base_tool import BaseTool
from google import genai
from google.genai import types
from pydantic import ValidationError

from adh_cli.core.policy_aware_function_tool import PolicyAwareFunctionTool
from adh_cli.core.tool_executor import ExecutionContext, ExecutionResult
from adh_cli.policies.policy_engine import PolicyEngine
from adh_cli.policies.policy_types import ToolCall
from adh_cli.safety.pipeline import SafetyPipeline
from adh_cli.ui.tool_execution_manager import ToolExecutionManager
from adh_cli.agents.agent_loader import AgentLoader
from adh_cli.tools import web_tools
from adh_cli.config.models import ModelConfig, ModelRegistry, get_default_model


class PolicyAwareNativeTool(BaseTool):
    """Wraps a native ADK tool with policy, confirmation, and audit hooks."""

    def __init__(
        self,
        *,
        tool_name: str,
        inner_tool: BaseTool,
        policy_engine: PolicyEngine,
        confirmation_handler: Optional[Callable],
        audit_logger: Optional[Callable],
        execution_manager: Optional[ToolExecutionManager],
        agent_name: Optional[str],
    ) -> None:
        super().__init__(
            name=getattr(inner_tool, "name", tool_name),
            description=getattr(inner_tool, "description", tool_name),
            is_long_running=getattr(inner_tool, "is_long_running", False),
            custom_metadata=getattr(inner_tool, "custom_metadata", None),
        )
        self.tool_name = tool_name
        self.inner_tool = inner_tool
        self.policy_engine = policy_engine
        self.confirmation_handler = confirmation_handler
        self.audit_logger = audit_logger
        self.execution_manager = execution_manager
        self.agent_name = agent_name

    async def process_llm_request(self, *, tool_context, llm_request) -> None:  # type: ignore[override]
        tool_call = ToolCall(tool_name=self.tool_name, parameters={}, context={})
        decision = self.policy_engine.evaluate_tool_call(tool_call)

        execution_id = None
        if self.execution_manager:
            execution_info = self.execution_manager.create_execution(
                tool_name=self.tool_name,
                parameters={},
                policy_decision=decision,
                agent_name=self.agent_name,
            )
            execution_id = execution_info.id

        if not decision.allowed:
            error_msg = f"Tool '{self.tool_name}' blocked by policy"
            if decision.reason:
                error_msg += f": {decision.reason}"
            if self.execution_manager and execution_id:
                self.execution_manager.block_execution(execution_id, reason=error_msg)
            raise PermissionError(error_msg)

        if decision.requires_confirmation:
            confirmed = False
            if self.execution_manager and execution_id:
                self.execution_manager.require_confirmation(execution_id, decision)
                confirmed = await self.execution_manager.wait_for_confirmation(
                    execution_id
                )
            elif self.confirmation_handler:
                confirmed = await self.confirmation_handler(
                    tool_call=tool_call,
                    decision=decision,
                    message=decision.confirmation_message,
                )

            if not confirmed:
                if self.execution_manager and execution_id:
                    self.execution_manager.complete_execution(
                        execution_id,
                        success=False,
                        error="Tool execution cancelled by user",
                    )
                raise PermissionError(
                    f"Tool '{self.tool_name}' execution cancelled by user"
                )

        if self.execution_manager and execution_id:
            self.execution_manager.start_execution(execution_id)

        if self.audit_logger:
            await self.audit_logger(
                tool_name=self.tool_name,
                parameters={},
                decision=decision.dict()
                if hasattr(decision, "dict")
                else str(decision),
                phase="pre_execution",
            )

        try:
            await self.inner_tool.process_llm_request(
                tool_context=tool_context, llm_request=llm_request
            )

            if self.execution_manager and execution_id:
                self.execution_manager.complete_execution(
                    execution_id,
                    success=True,
                    result="Delegated to Gemini built-in tool",
                )

            if self.audit_logger:
                await self.audit_logger(
                    tool_name=self.tool_name,
                    parameters={},
                    success=True,
                    phase="post_execution",
                    result="Delegated to Gemini built-in tool",
                )

        except Exception as exc:  # noqa: BLE001
            if self.execution_manager and execution_id:
                self.execution_manager.complete_execution(
                    execution_id,
                    success=False,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
            if self.audit_logger:
                await self.audit_logger(
                    tool_name=self.tool_name,
                    parameters={},
                    success=False,
                    phase="execution_error",
                    error=str(exc),
                )
            raise

    def _get_declaration(self):  # pragma: no cover - delegate to inner tool
        return getattr(self.inner_tool, "_get_declaration", lambda: None)()


class PolicyAwareLlmAgent:
    """ADK LlmAgent with integrated policy enforcement.

    This class uses Google ADK's LlmAgent for automatic tool orchestration
    while maintaining full policy enforcement, safety checks, and user
    confirmation workflows.
    """

    _URL_PATTERN = re.compile(r"https?://\S+")
    _URL_CONTEXT_SUCCESS = types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_SUCCESS
    _FALLBACK_MAX_CONTENT_CHARS = 100_000

    def __init__(
        self,
        model_name: Optional[str] = None,
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

        self.temperature = temperature
        self.max_tokens = max_tokens

        agent_model_config: Optional[ModelConfig] = None
        self.agent_definition = None
        try:
            loader = AgentLoader()
            agent_definition = loader.load(agent_name)
            self.agent_definition = agent_definition
            agent_model_config = agent_definition.model_config
            self.temperature = agent_definition.temperature
            self.max_tokens = agent_definition.max_tokens
        except (FileNotFoundError, ValueError) as exc:
            if self.notification_handler:
                self.notification_handler(
                    (
                        f"Could not load agent '{agent_name}', falling back to defaults. "
                        f"Reason: {exc}"
                    ),
                    level="warning",
                )

        # Track agent-level prompt variables (language, focus, etc.)
        self.agent_variables: Dict[str, Any] = {}

        if model_name:
            override_model = ModelRegistry.get_by_id(model_name)
            if not override_model:
                raise ValueError(f"Unknown model: {model_name}")
            self.model_config = override_model
        elif agent_model_config:
            self.model_config = agent_model_config
        else:
            self.model_config = get_default_model()

        self.model_id = self.model_config.id
        self.model_name = self.model_config.api_id

        # Initialize policy engine
        self.policy_engine = PolicyEngine(policy_dir=policy_dir)

        # Initialize safety pipeline
        self.safety_pipeline = SafetyPipeline()

        # Track registered tools
        self.tools: List[BaseTool] = []
        self.tool_handlers: Dict[str, Callable] = {}
        self.native_tools: Dict[str, Dict[str, Any]] = {}
        self.tool_metadata: Dict[str, Dict[str, Any]] = {}

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
            session_service=self.session_service,
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
                variables=self.agent_variables,
                tool_descriptions=tool_descriptions,
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
            tool_name = getattr(tool, "tool_name", getattr(tool, "name", "unknown"))
            metadata = self.tool_metadata.get(tool_name, {})
            description = metadata.get("description") or ""

            if (
                not description
                and hasattr(tool, "func")
                and getattr(tool.func, "__doc__", None)
            ):
                description = tool.func.__doc__.strip().split("\n")[0]

            if not description and getattr(tool, "description", None):
                description = str(tool.description)

            descriptions.append(f"- **{tool_name}**: {description}")

        return "\n".join(descriptions)

    async def _ensure_session_initialized(self):
        """Ensure the session is initialized."""
        if not self.session_service:
            return

        # Check if session already exists to avoid recreating it
        try:
            existing_session = await self.session_service.get_session(
                app_name="adh_cli", user_id=self.user_id, session_id=self.session_id
            )

            # Only create session if it doesn't exist
            if not existing_session:
                await self.session_service.create_session(
                    app_name="adh_cli", user_id=self.user_id, session_id=self.session_id
                )
        except Exception:
            # If get_session fails, try to create
            try:
                await self.session_service.create_session(
                    app_name="adh_cli", user_id=self.user_id, session_id=self.session_id
                )
            except Exception:
                # Session may already exist or other error
                pass

    def _create_audit_logger(
        self, audit_log_path: Optional[Path]
    ) -> Optional[Callable]:
        """Create audit logger if path provided."""
        if not audit_log_path:
            return None

        async def log_audit(**kwargs):
            """Log tool execution to audit file."""
            entry = {"timestamp": datetime.now().isoformat(), **kwargs}

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
            agent_name=self.agent_name,  # Pass agent name for tracking
        )

        # Add to our tracking
        self.tools.append(policy_tool)
        self.tool_handlers[name] = handler
        self.tool_metadata[name] = {
            "description": description,
            "parameters": parameters,
        }

        # Update LlmAgent with new tools (if initialized)
        if self.llm_agent:
            self._update_agent_tools()

    def register_native_tool(
        self,
        *,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        factory: Callable[[], BaseTool],
    ) -> None:
        """Register a native ADK tool (e.g., Gemini built-ins).

        Args:
            name: Tool name as exposed to the policy system/UI.
            description: Human-readable description for prompts/metadata.
            parameters: Declarative parameter description (for docs/policy).
            factory: Callable that returns a new BaseTool instance.
        """

        if name in self.native_tools:
            return

        wrapped_tool = PolicyAwareNativeTool(
            tool_name=name,
            inner_tool=factory(),
            policy_engine=self.policy_engine,
            confirmation_handler=self.confirmation_handler,
            audit_logger=self.audit_logger,
            execution_manager=self.execution_manager,
            agent_name=self.agent_name,
        )
        self.native_tools[name] = {"factory": factory}
        self.tool_metadata[name] = {
            "description": description,
            "parameters": parameters,
        }
        self.tools.append(wrapped_tool)

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
            session_service=self.session_service,
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

        # Update agent prompt variables from context metadata before chatting
        self._update_agent_variables_from_context(context)

        # Ensure session is initialized
        await self._ensure_session_initialized()

        # Update session/user IDs from context
        user_id = context.user_id or self.user_id
        session_id = context.session_id or self.session_id

        # Create user message
        user_content = types.Content(role="user", parts=[types.Part(text=message)])

        response_text = ""
        final_event = None

        # Stream events from runner
        try:
            async for event in self.runner.run_async(
                user_id=user_id, session_id=session_id, new_message=user_content
            ):
                # Note: Tool execution is now tracked via ToolExecutionManager
                # and displayed in the UI notification area, so we don't need
                # pop-up notifications here

                # Collect final response
                if event.is_final_response():
                    final_event = event
                    if event.content:
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                response_text += part.text

            if final_event:
                fallback_response = await self._maybe_run_url_context_fallback(
                    original_message=message,
                    final_event=final_event,
                    initial_response=response_text,
                )
                if fallback_response is not None:
                    return fallback_response

            return response_text or "Task completed."

        except PermissionError as e:
            # Policy blocked the tool
            return f"⛔ Action blocked by policy: {str(e)}"

        except Exception as e:
            # Other errors
            return f"❌ Error: {str(e)}"

    def _update_agent_variables_from_context(self, context: ExecutionContext) -> None:
        """Update agent prompt variables based on execution context metadata."""

        if not self.agent_definition or not self.agent_definition.variables:
            return

        metadata = context.metadata or {}

        candidate_sources: Dict[str, Any] = {}
        if isinstance(metadata, dict):
            candidate_sources.update(metadata)
            nested = metadata.get("agent_variables")
            if isinstance(nested, dict):
                candidate_sources.update(nested)

        new_variables: Dict[str, Any] = {}
        for var_name in self.agent_definition.variables:
            value = candidate_sources.get(var_name)
            if value is None:
                value = ""
            new_variables[var_name] = value

        if new_variables != self.agent_variables:
            self.agent_variables = new_variables

            # Rebuild agent instruction with updated variables when API is active
            if self.api_key:
                self._update_agent_tools()

    async def _maybe_run_url_context_fallback(
        self,
        *,
        original_message: str,
        final_event,
        initial_response: str,
    ) -> Optional[str]:
        """Run a local fetch fallback when Gemini cannot retrieve URL context."""

        urls = self._extract_urls(original_message)
        if not urls or not self.api_key:
            return None

        if not self._url_context_failed(final_event, initial_response):
            return None

        return await self._run_url_context_fallback(
            original_message=original_message,
            urls=urls,
        )

    def _url_context_failed(self, final_event, initial_response: str) -> bool:
        """Heuristic check to determine if URL context retrieval failed."""

        response_text = (initial_response or "").strip()

        url_context_meta = None
        metadata = getattr(final_event, "custom_metadata", None)
        if isinstance(metadata, dict):
            url_context_meta = metadata.get("urlContextMetadata") or metadata.get(
                "url_context_metadata"
            )

        statuses: List[types.UrlRetrievalStatus] = []
        if url_context_meta:
            try:
                parsed = types.UrlContextMetadata.model_validate(url_context_meta)
                statuses = [
                    entry.url_retrieval_status for entry in parsed.url_metadata or []
                ]
            except ValidationError:
                statuses = []

        if statuses:
            return not any(status == self._URL_CONTEXT_SUCCESS for status in statuses)

        grounding_metadata = getattr(final_event, "grounding_metadata", None)
        if grounding_metadata is not None:
            try:
                chunks = getattr(grounding_metadata, "grounding_chunks", None) or []
                if chunks:
                    return False
            except Exception:
                pass

        return not response_text

    @classmethod
    def _extract_urls(cls, text: str) -> List[str]:
        """Extract HTTP(S) URLs from text while trimming trailing punctuation."""

        if not text:
            return []

        urls: List[str] = []
        for match in cls._URL_PATTERN.findall(text):
            cleaned = match.rstrip("),.]")
            if cleaned and cleaned not in urls:
                urls.append(cleaned)
        return urls

    @staticmethod
    def _normalize_url_for_fallback(url: str) -> str:
        """Adjust URLs that require special handling before fetching."""

        if "github.com" in url and "/blob/" in url:
            return url.replace("github.com", "raw.githubusercontent.com").replace(
                "/blob/", "/"
            )
        return url

    async def _run_url_context_fallback(
        self, *, original_message: str, urls: List[str]
    ) -> str:
        """Fetch URL content locally and re-query Gemini with the retrieved text."""

        url_pairs = [(url, self._normalize_url_for_fallback(url)) for url in urls]

        async def fetch_single(
            original: str, normalized: str
        ) -> tuple[str, str, Dict[str, Any]]:
            try:
                result = await web_tools.fetch_url(normalized)
            except ValueError as exc:
                return original, normalized, {"success": False, "error": str(exc)}
            return original, normalized, result

        fetch_results = await asyncio.gather(
            *(fetch_single(original, normalized) for original, normalized in url_pairs)
        )

        successes: List[Dict[str, str]] = []
        errors: List[tuple[str, str]] = []

        for original, normalized, result in fetch_results:
            if not result.get("success", False):
                errors.append((original, result.get("error") or "Unknown error"))
                continue

            content = (result.get("content") or "").strip()
            if not content:
                errors.append((original, "No readable content returned."))
                continue

            truncated = content[: self._FALLBACK_MAX_CONTENT_CHARS]
            if len(content) > self._FALLBACK_MAX_CONTENT_CHARS:
                truncated = f"{truncated}\n... [content truncated]"

            successes.append(
                {
                    "original": original,
                    "normalized": normalized,
                    "content": truncated,
                }
            )

        if not successes:
            if errors:
                error_summary = "; ".join(
                    f"{original} ({message})" for original, message in errors
                )
                return f"❌ Error fetching URLs: {error_summary}"
            return "❌ No readable content returned from provided URLs."

        sections = []
        for item in successes:
            sections.append(
                "\n".join(
                    [
                        f"Source URL: {item['original']}",
                        f"Fetched URL: {item['normalized']}",
                        "---",
                        item["content"],
                        "---",
                    ]
                )
            )

        fetched_block = "\n\n".join(sections)

        error_block = ""
        if errors:
            error_block = "\nSome URLs could not be fetched:\n" + "\n".join(
                f"- {original}: {message}" for original, message in errors
            )

        fallback_prompt = (
            "The user provided URL(s) that Gemini could not retrieve automatically.\n"
            f"Original request:\n{original_message}\n\n"
            "I fetched the page content for you instead. Use only the content below to"
            " answer the request and do not attempt to fetch the URLs again.\n\n"
            f"{fetched_block}"
            f"{error_block}\n"
        )

        success, generated = await self._generate_fallback_response(fallback_prompt)

        fetched_urls = ", ".join(item["original"] for item in successes)
        failure_suffix = ""
        if errors:
            failure_suffix = " Some URLs failed: " + "; ".join(
                f"{original} ({message})" for original, message in errors
            )

        if success and generated:
            return (
                f"{generated}\n\n(Responded using fallback fetch for {fetched_urls}. "
                f"Content may be truncated.{failure_suffix})"
            )

        if success:
            return (
                "Fallback fetch succeeded, but Gemini returned no content."
                f"{failure_suffix}"
            )

        return generated

    async def _generate_fallback_response(self, prompt: str) -> tuple[bool, str]:
        """Run a synchronous Gemini generate-content call in a thread."""

        def _call() -> tuple[bool, str]:
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=prompt)],
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                ),
            )

            if response.candidates and response.candidates[0].content:
                text_parts: List[str] = []
                for part in response.candidates[0].content.parts:
                    if getattr(part, "text", None):
                        text_parts.append(part.text)
                combined = "".join(text_parts).strip()
                return True, combined

            return True, ""

        try:
            return await asyncio.to_thread(_call)
        except Exception as exc:  # noqa: BLE001
            return False, f"❌ Error generating fallback response: {exc}"

    def update_policies(self, policy_dir: Path):
        """Update policies from a directory.

        Note: Requires recreating all tools with new policy engine.
        """
        # Create new policy engine
        self.policy_engine = PolicyEngine(policy_dir=policy_dir)

        # Store current tool metadata for re-registration
        function_tools = []
        for name, handler in self.tool_handlers.items():
            meta = self.tool_metadata.get(name, {})
            function_tools.append(
                {
                    "name": name,
                    "handler": handler,
                    "description": meta.get("description", ""),
                    "parameters": meta.get("parameters", {}),
                }
            )

        native_tools = []
        for name, data in self.native_tools.items():
            meta = self.tool_metadata.get(name, {})
            native_tools.append(
                {
                    "name": name,
                    "factory": data["factory"],
                    "description": meta.get("description", ""),
                    "parameters": meta.get("parameters", {}),
                }
            )

        # Clear current registrations
        self.tools.clear()
        self.tool_handlers.clear()
        self.native_tools.clear()
        self.tool_metadata.clear()

        # Re-register function tools with new policy engine
        for tool_meta in function_tools:
            self.register_tool(
                name=tool_meta["name"],
                description=tool_meta["description"],
                parameters=tool_meta["parameters"],
                handler=tool_meta["handler"],
            )

        # Re-register native tools (policy enforcement handled via metadata/policies)
        for tool_meta in native_tools:
            self.register_native_tool(
                name=tool_meta["name"],
                description=tool_meta["description"],
                parameters=tool_meta["parameters"],
                factory=tool_meta["factory"],
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

            async def execute(
                self,
                tool_name: str,
                parameters: Dict[str, Any],
                context: Optional[ExecutionContext] = None,
            ):
                """Execute a tool directly (for testing/compatibility)."""
                if tool_name not in self.agent.tool_handlers:
                    return ExecutionResult(
                        success=False, error=f"Tool '{tool_name}' not found"
                    )

                try:
                    handler = self.agent.tool_handlers[tool_name]
                    result = await handler(**parameters)
                    return ExecutionResult(success=True, result=result)
                except Exception as e:
                    return ExecutionResult(success=False, error=str(e))

        return ToolExecutorWrapper(self)
