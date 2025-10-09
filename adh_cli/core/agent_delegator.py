"""Agent delegation infrastructure for multi-agent orchestration."""

from dataclasses import dataclass
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

    def _register_execute_command_tool(
        self, agent: PolicyAwareLlmAgent, description: str, command_example: str
    ):
        """Helper to register the 'execute_command' tool with a specific description.

        Args:
            agent: The agent to register the tool for
            description: Custom description for the execute_command tool
            command_example: Example command for the description
        """
        from ..tools import shell_tools

        agent.register_tool(
            name="execute_command",
            description=description,
            parameters={
                "command": {
                    "type": "string",
                    "description": f"Command to execute (e.g. `{command_example}`)",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for the command",
                    "nullable": True,
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 300,
                },
                "shell": {
                    "type": "boolean",
                    "description": "Use shell execution",
                    "default": True,
                },
            },
            handler=shell_tools.execute_command,
        )

    def _register_google_search_tools(self, agent: PolicyAwareLlmAgent):
        """Helper to register Google search and URL context tools.

        Args:
            agent: The agent to register the tools for
        """
        from ..tools.specs import register_default_specs

        register_default_specs()
        for tool_name in ("google_search", "google_url_context"):
            spec = registry.get(tool_name)
            if spec is None or spec.adk_tool_factory is None:
                raise ValueError(f"{tool_name} specification not registered")
            agent.register_native_tool(
                name=spec.name,
                description=spec.description,
                parameters=spec.parameters,
                factory=spec.adk_tool_factory,
            )

    def _register_agent_tools(self, agent: PolicyAwareLlmAgent, agent_name: str):
        """Register tools appropriate for this agent.

        Different agents get different tool sets based on their role:
        - Planner: Read-only tools (read_file, list_directory, get_file_info)
        - Code reviewer: Read-only inspection tools for code analysis
        - etc.

        Args:
            agent: The agent to register tools for
            agent_name: Name of the agent
        """
        from ..tools import shell_tools

        # All agents get read-only tools for exploration
        if agent_name == "search":
            self._register_google_search_tools(agent)
            return

        # Default agents get read-only tools for exploration
        agent.register_tool(
            name="read_file",
            description="Read contents of a text file",
            parameters={},
            handler=shell_tools.read_file,
        )

        agent.register_tool(
            name="list_directory",
            description="List contents of a directory",
            parameters={},
            handler=shell_tools.list_directory,
        )

        agent.register_tool(
            name="get_file_info",
            description="Get metadata about a file or directory",
            parameters={},
            handler=shell_tools.get_file_info,
        )

        # Planning and code review agents stay read-only to avoid accidental writes.
        if agent_name == "code_reviewer":
            return

        if agent_name == "tester":
            # Allow build/test agent to execute repository commands.
            self._register_execute_command_tool(
                agent,
                description=(
                    "Run a shell command inside the repository. Prefer `task` shortcuts "
                    "for builds, linting, and tests."
                ),
                command_example="task test",
            )
            return

        if agent_name == "researcher":
            # Researcher needs repo exploration, shell access for search helpers, and web search tools.
            self._register_execute_command_tool(
                agent,
                description=(
                    "Run read-only commands (e.g. `rg`, `task list`) while researching topics."
                ),
                command_example='rg "keyword" docs',
            )
            self._register_google_search_tools(agent)
            return

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
