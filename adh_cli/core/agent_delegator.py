"""Agent delegation infrastructure for multi-agent orchestration."""

from dataclasses import dataclass
import functools
import inspect
from typing import Any, Dict, Optional
from pathlib import Path

from .policy_aware_llm_agent import PolicyAwareLlmAgent
from ..core.tool_executor import ExecutionContext
from ..tools.base import registry


@dataclass
class AgentResponse:
    """Response from a delegated agent.

    Attributes:
        agent_name: Name of the agent that executed the task
        task_type: Type of task (planning, code_review, research, etc.)
        result: The agent's output/response
        metadata: Additional context or information
        success: Whether the delegation succeeded
        error: Error message if delegation failed
    """

    agent_name: str
    task_type: str
    result: str
    metadata: Dict[str, Any]
    success: bool
    error: Optional[str] = None


class AgentDelegator:
    """Handles delegation to specialized agents.

    The AgentDelegator manages loading and executing specialist agents,
    caching them for reuse, and returning structured responses.
    """

    def __init__(
        self,
        api_key: str,
        policy_dir: Optional[Path] = None,
        audit_log_path: Optional[Path] = None,
        parent_agent: Optional[Any] = None,
    ):
        """Initialize the agent delegator.

        Args:
            api_key: API key for Gemini
            policy_dir: Directory containing policy files
            audit_log_path: Path for audit logging
            parent_agent: Parent agent (to get execution_manager callbacks from)
        """
        self.api_key = api_key
        self.policy_dir = policy_dir
        self.audit_log_path = audit_log_path
        self.parent_agent = parent_agent
        self._agent_cache: Dict[str, PolicyAwareLlmAgent] = {}

    async def delegate(
        self, agent_name: str, task: str, context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """Delegate a task to a specialist agent.

        Args:
            agent_name: Name of agent to delegate to (e.g., "planner")
            task: Task description for the agent
            context: Additional context for the agent

        Returns:
            AgentResponse with result or error
        """
        try:
            # Load or get cached agent
            if agent_name not in self._agent_cache:
                # Get callbacks from parent agent's execution manager if available
                on_execution_start = None
                on_execution_update = None
                on_execution_complete = None
                on_confirmation_required = None

                if self.parent_agent and hasattr(
                    self.parent_agent, "execution_manager"
                ):
                    exec_mgr = self.parent_agent.execution_manager
                    on_execution_start = getattr(exec_mgr, "on_execution_start", None)
                    on_execution_update = getattr(exec_mgr, "on_execution_update", None)
                    on_execution_complete = getattr(
                        exec_mgr, "on_execution_complete", None
                    )
                    on_confirmation_required = getattr(
                        exec_mgr, "on_confirmation_required", None
                    )

                agent = PolicyAwareLlmAgent(
                    agent_name=agent_name,
                    api_key=self.api_key,
                    policy_dir=self.policy_dir,
                    audit_log_path=self.audit_log_path,
                    # Pass execution manager callbacks so delegated agent's
                    # tool calls appear in the UI
                    on_execution_start=on_execution_start,
                    on_execution_update=on_execution_update,
                    on_execution_complete=on_execution_complete,
                    on_confirmation_required=on_confirmation_required,
                )
                # Register tools specific to this agent
                self._register_agent_tools(agent, agent_name)
                self._agent_cache[agent_name] = agent

            agent = self._agent_cache[agent_name]

            # Create execution context if provided
            exec_context = None
            if context:
                exec_context = ExecutionContext(
                    user_id=context.get("user_id"),
                    session_id=context.get("session_id"),
                    metadata=context,
                )

            # Execute task
            result = await agent.chat(task, context=exec_context)

            return AgentResponse(
                agent_name=agent_name,
                task_type=self._infer_task_type(agent_name),
                result=result,
                metadata=context or {},
                success=True,
            )

        except Exception as e:
            return AgentResponse(
                agent_name=agent_name,
                task_type=self._infer_task_type(agent_name),
                result="",
                metadata=context or {},
                success=False,
                error=str(e),
            )

    def _infer_task_type(self, agent_name: str) -> str:
        """Infer task type from agent name.

        Args:
            agent_name: Name of the agent

        Returns:
            Task type string
        """
        type_mapping = {
            "planner": "planning",
            "code_reviewer": "code_review",
            "researcher": "research",
            "tester": "testing",
        }
        return type_mapping.get(agent_name, "general")

    def _register_google_tool(
        self, agent: PolicyAwareLlmAgent, tool_name: str, spec: Any
    ):
        """Register a Google search tool with API key binding.

        Google search tools require special handling to bind the API key
        and generation config from the agent into the handler.

        Args:
            agent: The agent to register the tool for
            tool_name: Name of the tool (google_search or google_url_context)
            spec: Tool specification from registry
        """
        if spec.handler is None:
            raise ValueError(f"{tool_name} handler not found in registry")

        raw_generation_params = getattr(agent, "generation_params", None)
        generation_config = (
            dict(raw_generation_params)
            if isinstance(raw_generation_params, dict)
            else None
        )
        agent_model = getattr(agent, "model_name", None)

        # Capture handler in closure correctly
        original_handler = spec.handler

        @functools.wraps(original_handler)
        async def bound_handler(
            *args,
            __handler=original_handler,
            __api_key=self.api_key,
            __model=agent_model,
            __generation_config=generation_config,
            **kwargs,
        ):
            kwargs = dict(kwargs)
            request_api_key = kwargs.pop("api_key", None)
            request_model = kwargs.pop("model", None)
            request_generation_config = kwargs.pop("generation_config", None)

            effective_api_key = __api_key or request_api_key
            effective_model = __model or request_model
            effective_generation_config = (
                __generation_config or request_generation_config
            )

            return await __handler(
                *args,
                api_key=effective_api_key,
                model=effective_model,
                generation_config=effective_generation_config,
                **kwargs,
            )

        original_signature = inspect.signature(original_handler)
        adjusted_parameters = [
            param.replace(default=inspect._empty)
            if param.default is not inspect._empty
            else param
            for param in original_signature.parameters.values()
        ]
        bound_handler.__signature__ = original_signature.replace(
            parameters=adjusted_parameters
        )

        agent.register_tool(
            name=spec.name,
            description=spec.description,
            parameters=spec.parameters,
            handler=bound_handler,
        )

    def _register_agent_tools(self, agent: PolicyAwareLlmAgent, agent_name: str):
        """Register tools for this agent based on YAML definition.

        Reads tool names from the agent's YAML frontmatter (agent_definition.tools)
        and registers them from the tool registry. This makes YAML the single source
        of truth for agent tool configuration (per ADR-021).

        Args:
            agent: The agent to register tools for
            agent_name: Name of the agent (used for error messages)
        """
        from ..tools.specs import register_default_specs

        # Ensure all tool specs are registered
        register_default_specs()

        # Get agent definition from the agent
        agent_def = agent.agent_definition
        if not agent_def or not agent_def.tools:
            # No tools specified in YAML - nothing to register
            return

        # Register each tool from the YAML definition
        for tool_name in agent_def.tools:
            spec = registry.get(tool_name)
            if spec is None:
                available = ", ".join(sorted(registry.list_tools()))
                raise ValueError(
                    f"Tool '{tool_name}' not found in registry for agent '{agent_name}'. "
                    f"Available tools: {available}"
                )

            # Special handling for google search tools that need API key binding
            if tool_name in ("google_search", "google_url_context"):
                self._register_google_tool(agent, tool_name, spec)
            else:
                # Standard tool registration from registry
                agent.register_tool(
                    name=spec.name,
                    description=spec.description,
                    parameters=spec.parameters,
                    handler=spec.handler,
                )

    def clear_cache(self):
        """Clear the agent cache.

        Useful for testing or when you want to reload agent definitions.
        """
        self._agent_cache.clear()

    def get_cached_agents(self) -> list[str]:
        """Get list of currently cached agent names.

        Returns:
            List of agent names in the cache
        """
        return list(self._agent_cache.keys())
