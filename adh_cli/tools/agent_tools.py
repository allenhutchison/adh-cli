"""Agent delegation tools for multi-agent orchestration."""

from typing import Dict, Any, Optional

from ..core.agent_delegator import AgentDelegator


def create_delegate_tool(delegator: AgentDelegator):
    """Create a delegate_to_agent tool bound to a specific AgentDelegator instance.

    Args:
        delegator: The AgentDelegator instance to use

    Returns:
        The delegate_to_agent tool function
    """

    async def delegate_to_agent(
        agent: str,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Delegate a task to a specialist agent.

        Use this tool when you encounter a complex task that would benefit from
        specialized expertise. The specialist agent will perform deep analysis
        and return detailed results.

        When to delegate:
        - Complex multi-step tasks requiring detailed planning
        - Tasks needing deep codebase exploration
        - Code review or analysis tasks
        - Research that requires thorough investigation

        Args:
            agent: Name of specialist agent to use:
                   - "planner": Creates detailed implementation plans for complex tasks
                   - "code_reviewer": Reviews code for quality and issues (future)
                   - "researcher": Investigates topics and gathers information (future)
                   - "tester": Designs and executes tests (future)
            task: Clear description of what you want the agent to do
            context: Optional context dict with:
                     - working_dir: Current working directory
                     - requirements: Specific requirements or constraints
                     - files: List of relevant files (optional)

        Returns:
            The specialist agent's response (plan, analysis, findings, etc.)

        Examples:
            # Delegate complex implementation planning
            plan = await delegate_to_agent(
                agent="planner",
                task="Create detailed plan for implementing database caching system",
                context={"working_dir": ".", "requirements": "Must support TTL and LRU"}
            )

            # Delegate code review (when available)
            review = await delegate_to_agent(
                agent="code_reviewer",
                task="Review the authentication module for security issues",
                context={"files": ["src/auth.py", "src/session.py"]}
            )
        """
        response = await delegator.delegate(
            agent_name=agent,
            task=task,
            context=context or {}
        )

        if response.success:
            return response.result
        else:
            # Return error as part of the result so the orchestrator can handle it
            return f"⚠️ Delegation to {agent} failed: {response.error}\n\nPlease handle this task directly or try a different approach."

    return delegate_to_agent
