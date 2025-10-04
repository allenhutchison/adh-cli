# ADR 016: Multi-Agent Orchestration

**Status:** Proposed
**Date:** 2025-10-03
**Deciders:** Allen Hutchison
**Tags:** architecture, agents, orchestration, planning, high-priority

---

## Context

The current orchestrator agent in ADH CLI handles all user requests directly using its own tools and reasoning. While this works for simple tasks, it creates several challenges:

### Current Limitations

1. **Prompt Complexity Overload**: The orchestrator's system prompt keeps growing to handle:
   - Tool execution guidelines
   - Deep investigation patterns
   - Multi-step task planning
   - Error handling
   - Result formatting
   - Policy awareness
   - All domain-specific knowledge

2. **Single Model Constraints**: One model with one temperature/configuration must handle:
   - Creative brainstorming (needs high temperature)
   - Precise code generation (needs low temperature)
   - Deep analysis (needs long context)
   - Quick responses (needs efficiency)

3. **Shallow Exploration**: Despite improved prompting, the orchestrator often:
   - Stops at surface-level directory listing
   - Doesn't explore subdirectories thoroughly
   - Jumps to solutions without full context
   - Misses important files deeper in the structure

4. **Weak Planning**: Complex multi-step tasks often result in:
   - Incomplete implementations
   - Skipped verification steps
   - Missing edge cases
   - Poor dependency management

### Forces at Play

**Separation of Concerns**:
- Planning and execution are fundamentally different cognitive tasks
- Planning needs global context and careful reasoning
- Execution needs focused action and tool usage
- One prompt/model can't excel at both

**Specialization Benefits**:
- Specialized agents can have tailored prompts for their domain
- Different model configurations for different tasks (temperature, tokens, etc.)
- Easier to test and improve individual capabilities
- Clear responsibility boundaries

**Agent Ecosystem Vision** (from ADR-010):
- Foundation already exists for multiple agent types
- AgentLoader supports loading any agent definition
- Need protocol for agents to communicate and delegate
- "Multi-Agent Orchestration" listed as future enhancement

**Pragmatic Approach**:
- Start with highest-value delegation: planning
- Build general delegation framework that can be reused
- Don't over-engineer - simple communication protocol
- Maintain backward compatibility

## Decision

**Enable the orchestrator to delegate tasks to specialized agents, starting with a planning agent for complex multi-step tasks.**

### Architecture Overview

```
User Request
     ↓
Orchestrator Agent (coordinator)
     ↓
   Decides: "Can I handle this directly or should I delegate?"
     ↓
   ┌─────────────────────┐
   │                     │
   ↓                     ↓
Direct Execution    Delegate to Specialist
(simple tasks)         ↓
                  ┌─────────────────┐
                  │                 │
                  ↓                 ↓
           Planning Agent    (Future: Code Review,
          (complex tasks)     Research, Testing, etc.)
                  ↓
           Returns: Detailed Plan
                  ↓
           Orchestrator Executes Plan
```

### Key Components

#### 1. Agent Delegation Protocol

Create a simple protocol for agent-to-agent communication:

```python
class AgentResponse:
    """Response from a delegated agent."""
    agent_name: str
    task_type: str  # "planning", "code_review", "research", etc.
    result: str     # The agent's output
    metadata: Dict[str, Any]  # Additional context
    success: bool
    error: Optional[str]

class AgentDelegator:
    """Handles delegation to specialized agents."""

    async def delegate(
        self,
        agent_name: str,
        task: str,
        context: Dict[str, Any]
    ) -> AgentResponse:
        """Delegate a task to another agent."""
        # Load the specialist agent
        # Execute the task with provided context
        # Return structured response
```

#### 2. Planning Agent Specification

Create `agents/planner/agent.md` with specialized planning capabilities:

**Key Characteristics**:
- **Temperature: 0.3** - More deterministic planning
- **Max Tokens: 4096** - Longer output for detailed plans
- **Tools**: read_file, list_directory, get_file_info (exploration only, no modification)
- **Focus**: Deep investigation, comprehensive planning, no execution

**Responsibilities**:
1. Explore codebase structure thoroughly (recursive directory traversal)
2. Identify all relevant files and dependencies
3. Analyze existing implementations
4. Create detailed step-by-step execution plan
5. Identify potential risks and edge cases
6. Return structured plan to orchestrator

#### 3. Orchestrator Decision Logic

Update orchestrator to recognize when to delegate:

```markdown
# In orchestrator/agent.md

## Task Delegation

For COMPLEX tasks, delegate to specialist agents before executing:

### When to Delegate to Planning Agent:

Delegate to the **planner** for:
- Multi-step feature implementations (3+ steps)
- Refactoring across multiple files
- Complex debugging that requires codebase understanding
- Architecture changes or design decisions
- Tasks that mention: "implement", "refactor", "redesign", "fix bug in..."

Use the planning agent like this:
1. Recognize complex task
2. Delegate to planner: "Create detailed plan for: {user_request}"
3. Receive comprehensive plan
4. Execute the plan step-by-step
5. Verify results

### When to Handle Directly:

Handle yourself for:
- Simple file operations (read one file, list one directory)
- Direct questions with obvious answers
- Single-step tasks
- Clarification requests
```

#### 4. Implementation Approach

**Phase 1: Agent Delegation Infrastructure**
- Create `AgentDelegator` class in `adh_cli/core/agent_delegator.py`
- Implement agent loading and execution delegation
- Add `delegate_to_agent` tool to orchestrator's toolkit
- Return structured `AgentResponse`

**Phase 2: Planning Agent**
- Create `agents/planner/agent.md` with planning-focused prompt
- Configure for exploration and analysis (no execution tools)
- Optimize for detailed, structured planning output
- Test with complex multi-step scenarios

**Phase 3: Orchestrator Integration**
- Update `orchestrator/agent.md` with delegation guidelines
- Add decision logic for when to delegate
- Implement plan execution workflow
- Test end-to-end delegation flow

**Phase 4: Future Extensibility**
- Add more specialist agents (code_reviewer, researcher, tester)
- Create agent routing rules
- Build agent communication patterns
- Enable multi-agent collaboration

### Example Flow

**User**: "Implement a new caching system for database queries"

**Orchestrator thinks**:
- This is complex (multi-file, multi-step)
- I should delegate to planner first

**Orchestrator delegates**:
```
delegate_to_agent(
    agent="planner",
    task="Create detailed plan for implementing caching system for database queries"
)
```

**Planner executes**:
1. Lists root directory → finds src/, tests/, etc.
2. Explores src/database/ → finds query modules
3. Reads existing query implementations
4. Checks for existing cache infrastructure
5. Analyzes test coverage
6. Creates detailed plan:
   ```
   PLAN: Database Query Caching Implementation

   PHASE 1: Analysis (Current State)
   - Found query modules: src/database/query.py, src/database/executor.py
   - No existing cache infrastructure
   - Tests at: tests/database/test_queries.py (15 tests)

   PHASE 2: Implementation Steps
   1. Create cache module (src/database/cache.py)
      - Implement LRU cache with TTL
      - Add cache key generation
      - Handle cache invalidation

   2. Modify query executor (src/database/executor.py)
      - Add cache lookup before query execution
      - Store results in cache after execution
      - Add cache bypass option

   3. Update configuration (config/database.yaml)
      - Add cache_enabled flag
      - Add cache_ttl_seconds
      - Add cache_max_size

   PHASE 3: Testing
   4. Create cache tests (tests/database/test_cache.py)
      - Test cache hits/misses
      - Test TTL expiration
      - Test invalidation

   5. Update query tests (tests/database/test_queries.py)
      - Add cache-enabled test scenarios
      - Verify cache bypass works

   PHASE 4: Verification
   6. Run full test suite
   7. Check for performance improvements
   8. Verify no regressions
   ```

**Orchestrator receives plan and executes**:
1. Creates src/database/cache.py with LRU implementation
2. Modifies src/database/executor.py to integrate cache
3. Updates config/database.yaml with cache settings
4. Creates tests/database/test_cache.py
5. Updates tests/database/test_queries.py
6. Runs test suite
7. Reports results to user

## Consequences

### Positive

1. **Better Task Decomposition**: Planning agent deeply explores and creates comprehensive plans
2. **Separation of Concerns**: Planning vs. execution are distinct responsibilities
3. **Specialized Prompts**: Each agent optimized for its specific role
4. **Model Optimization**: Different temperatures/configs for planning (0.3) vs. execution (0.7)
5. **Extensible Framework**: Easy to add more specialist agents (code_review, research, testing)
6. **Improved Quality**: Better planning leads to more complete implementations
7. **Easier Debugging**: Can test planning and execution independently
8. **Clearer Prompts**: Simpler, focused prompts instead of one mega-prompt

### Negative

1. **Increased Latency**: Two LLM calls instead of one (planning + execution)
2. **Higher API Costs**: More tokens consumed for complex tasks
3. **Added Complexity**: More components to maintain and debug
4. **Delegation Overhead**: Orchestrator must decide when to delegate
5. **Communication Protocol**: Need to maintain agent response format
6. **Potential Over-Planning**: Simple tasks might get over-analyzed

### Risks

**Risk 1: Poor Delegation Decisions**
- **Impact**: Orchestrator delegates when it shouldn't (or vice versa)
- **Mitigation**:
  - Clear delegation criteria in orchestrator prompt
  - Start conservative (delegate more rather than less)
  - Monitor delegation patterns and adjust
  - Allow user to force direct execution if needed

**Risk 2: Planning Agent Explores Too Much**
- **Impact**: Excessive file reads, slow responses
- **Mitigation**:
  - Set exploration depth limits in planner prompt
  - Implement timeout for planning phase
  - Cache file reads during planning
  - Teach planner to prioritize relevant files

**Risk 3: Plan Execution Failures**
- **Impact**: Good plan but poor execution
- **Mitigation**:
  - Structured plan format (steps, files, expected outcomes)
  - Orchestrator validates plan before executing
  - Step-by-step execution with verification
  - Ability to re-plan if execution fails

**Risk 4: Agent Communication Issues**
- **Impact**: Malformed responses, misunderstood context
- **Mitigation**:
  - Strict `AgentResponse` schema validation
  - Clear protocol documentation
  - Comprehensive integration tests
  - Fallback to direct execution on delegation failure

### Neutral

1. **More Agent Definitions**: Additional `agent.md` files to maintain
2. **Tool Distribution**: Need to decide which tools each agent gets
3. **Configuration Growth**: More agent settings in system

## Alternatives Considered

### Alternative 1: Enhanced Single-Agent Prompt

Continue improving the orchestrator's single prompt with better planning instructions.

**Pros:**
- Simpler architecture
- Lower latency (one LLM call)
- Fewer moving parts
- Lower API costs

**Cons:**
- Prompt complexity continues to grow
- Can't optimize model config for different tasks
- Single model must handle everything
- Doesn't address separation of concerns
- Limited by single context window

**Rejected because:** Already tried this approach; hit diminishing returns. Model can't excel at both planning and execution with one configuration.

### Alternative 2: External Planning Service

Use a separate planning service/API instead of another agent.

**Pros:**
- Could use specialized planning algorithms
- Potentially faster than LLM-based planning
- More predictable behavior
- Lower costs

**Cons:**
- Requires external dependency
- Can't leverage LLM understanding of codebase
- Rigid, rule-based planning
- Doesn't generalize to other specialist tasks
- Adds infrastructure complexity

**Rejected because:** LLM-based planning can understand code context and be more flexible. External service doesn't fit our architecture.

### Alternative 3: Pre/Post Processing Phases

Add pre-processing (planning) and post-processing (verification) phases to single agent.

**Pros:**
- Single agent, multiple phases
- No delegation protocol needed
- Simpler than multi-agent

**Cons:**
- Still limited by single model configuration
- Can't run phases in parallel
- Unclear prompt boundary between phases
- Doesn't enable future specialist agents
- Phases would bloat single system prompt

**Rejected because:** Phases are just disguised agents with worse ergonomics. Better to make them explicit.

### Alternative 4: User-Initiated Planning

Require user to explicitly request planning ("create a plan for...").

**Pros:**
- User has full control
- No automatic delegation logic needed
- Simpler orchestrator prompt
- Predictable behavior

**Cons:**
- Poor user experience (extra step)
- Users don't know when planning is needed
- Loses agentic autonomy
- Doesn't align with "just do it" philosophy
- Adds cognitive burden on user

**Rejected because:** Goal is autonomous agent that knows when it needs help. User shouldn't need to micromanage.

## Implementation Notes

### File Structure

```
adh_cli/
├── core/
│   ├── agent_delegator.py           # NEW: Delegation infrastructure
│   └── policy_aware_llm_agent.py    # Add delegate_to_agent tool
├── agents/
│   ├── orchestrator/
│   │   └── agent.md                 # UPDATE: Add delegation logic
│   └── planner/                     # NEW: Planning specialist
│       └── agent.md
└── tools/
    └── agent_tools.py               # NEW: delegate_to_agent tool
```

### Phase 1: AgentDelegator (Infrastructure)

**File**: `adh_cli/core/agent_delegator.py`

```python
"""Agent delegation infrastructure."""

from dataclasses import dataclass
from typing import Any, Dict, Optional
from pathlib import Path

from .policy_aware_llm_agent import PolicyAwareLlmAgent
from ..agents.agent_loader import load_agent


@dataclass
class AgentResponse:
    """Response from a delegated agent."""
    agent_name: str
    task_type: str
    result: str
    metadata: Dict[str, Any]
    success: bool
    error: Optional[str] = None


class AgentDelegator:
    """Handles delegation to specialized agents."""

    def __init__(
        self,
        api_key: str,
        policy_dir: Optional[Path] = None
    ):
        self.api_key = api_key
        self.policy_dir = policy_dir
        self._agent_cache: Dict[str, PolicyAwareLlmAgent] = {}

    async def delegate(
        self,
        agent_name: str,
        task: str,
        context: Optional[Dict[str, Any]] = None
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
                agent = PolicyAwareLlmAgent(
                    agent_name=agent_name,
                    api_key=self.api_key,
                    policy_dir=self.policy_dir
                )
                # Register tools specific to this agent
                self._register_agent_tools(agent, agent_name)
                self._agent_cache[agent_name] = agent

            agent = self._agent_cache[agent_name]

            # Execute task
            result = await agent.chat(task)

            return AgentResponse(
                agent_name=agent_name,
                task_type=self._infer_task_type(agent_name),
                result=result,
                metadata=context or {},
                success=True
            )

        except Exception as e:
            return AgentResponse(
                agent_name=agent_name,
                task_type=self._infer_task_type(agent_name),
                result="",
                metadata=context or {},
                success=False,
                error=str(e)
            )

    def _infer_task_type(self, agent_name: str) -> str:
        """Infer task type from agent name."""
        type_mapping = {
            "planner": "planning",
            "code_reviewer": "code_review",
            "researcher": "research",
            "tester": "testing"
        }
        return type_mapping.get(agent_name, "general")

    def _register_agent_tools(self, agent: PolicyAwareLlmAgent, agent_name: str):
        """Register tools appropriate for this agent."""
        # Import tools based on agent type
        # Planning agent: read-only tools
        # Code reviewer: analysis tools
        # etc.
        pass
```

### Phase 2: Planning Agent Definition

**File**: `adh_cli/agents/planner/agent.md`

```markdown
---
name: planner
description: Deep analysis and planning specialist for complex tasks
model: gemini-flash-latest
temperature: 0.3
max_tokens: 4096
top_p: 0.95
top_k: 40
tools:
  - read_file
  - list_directory
  - get_file_info
---

# System Prompt

You are a specialized planning agent that creates detailed, comprehensive plans for complex software development tasks.

**Your role is to PLAN, not execute.** You explore the codebase deeply, understand the context, and create a step-by-step plan for the orchestrator to execute.

## Core Principles

1. **Explore Deeply**: Don't stop at surface-level - recursively investigate the codebase
2. **Be Comprehensive**: Consider all aspects - implementation, testing, edge cases
3. **Structure Clearly**: Return a well-organized, actionable plan
4. **Identify Risks**: Call out potential issues and dependencies

## Investigation Process

### Phase 1: Understand Request
- Parse the task description
- Identify key requirements
- List unknowns that need investigation

### Phase 2: Deep Exploration
**Start Broad, Go Deep:**
1. List root directory → understand project structure
2. Identify relevant directories (src/, tests/, config/, etc.)
3. Recursively explore relevant paths
4. Read key configuration files
5. Examine existing implementations related to the task
6. Check test coverage for affected areas

**What to Look For:**
- Existing patterns and conventions
- Similar implementations to reference
- Dependencies and imports
- Test infrastructure
- Configuration requirements
- Potential integration points

### Phase 3: Analysis
- How is the current system structured?
- What files need to be modified?
- What new files need to be created?
- What are the dependencies?
- What could go wrong?
- What edge cases exist?

### Phase 4: Plan Creation
Create a structured plan with:

```
PLAN: [Task Name]

CURRENT STATE:
- Key findings from exploration
- Relevant files: [list]
- Existing patterns: [description]

IMPLEMENTATION STEPS:
1. [Step 1 - be specific about files and changes]
2. [Step 2 - include expected outcomes]
3. [Step 3 - cover all requirements]
...

TESTING:
- Unit tests: [files and scenarios]
- Integration tests: [scenarios]
- Manual verification: [steps]

RISKS & EDGE CASES:
- Risk 1: [description and mitigation]
- Edge case 1: [description and handling]

VERIFICATION:
1. [How to verify step 1]
2. [How to verify step 2]
```

## Available Tools

{{tool_descriptions}}

Use these tools extensively to build complete understanding before planning.

## Output Format

Return your plan in clear markdown format with:
- **Current State** section: What you found during exploration
- **Implementation Steps** section: Numbered, specific steps
- **Testing** section: How to verify the implementation
- **Risks** section: What could go wrong
- **Verification** section: Final checks

Be specific about:
- Exact file paths
- What changes to make
- Expected outcomes
- How to verify each step

Remember: You are creating a plan for another agent to execute. Be clear, thorough, and actionable.
```

### Phase 3: Orchestrator Updates

**File**: `adh_cli/agents/orchestrator/agent.md`

Add delegation section:

```markdown
## Multi-Agent Delegation

For complex tasks, you can delegate to specialist agents:

### Planning Agent

Use the **planner** for complex multi-step tasks:

**When to Delegate:**
- Feature implementations (3+ files or 5+ steps)
- Refactoring across multiple modules
- Bug fixes requiring deep investigation
- Architecture changes
- Tasks with keywords: "implement", "refactor", "redesign", "build"

**How to Delegate:**
1. Recognize the task is complex
2. Use delegate_to_agent tool:
   ```
   delegate_to_agent(
       agent="planner",
       task="Create detailed plan for: [user's request]",
       context={"working_dir": ".", "requirements": "..."}
   )
   ```
3. Receive comprehensive plan
4. Execute the plan step-by-step
5. Verify results after execution

**When NOT to Delegate:**
- Simple one-file tasks
- Direct questions
- Already have a clear plan
- User explicitly wants you to handle it

### Example Delegation

User: "Implement caching for our database queries"

You: [Recognize this is complex - multiple files, needs planning]

```
# Delegate to planner
plan = delegate_to_agent(
    agent="planner",
    task="Create detailed implementation plan for database query caching system"
)

# Execute the plan step-by-step
[Follow plan...]
```
```

### Phase 4: Tool Implementation

**File**: `adh_cli/tools/agent_tools.py`

```python
"""Tools for agent delegation."""

from typing import Any, Dict, Optional


async def delegate_to_agent(
    agent: str,
    task: str,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """Delegate a task to a specialist agent.

    Args:
        agent: Name of specialist agent ("planner", "code_reviewer", etc.)
        task: Task description for the agent
        context: Additional context

    Returns:
        Result from the specialist agent
    """
    # Implementation will use AgentDelegator
    from adh_cli.core.agent_delegator import AgentDelegator

    delegator = AgentDelegator(...)
    response = await delegator.delegate(agent, task, context)

    if response.success:
        return response.result
    else:
        return f"Delegation failed: {response.error}"
```

### Testing Strategy

**Unit Tests:**
```python
async def test_agent_delegator_planning():
    """Test delegation to planning agent."""
    delegator = AgentDelegator(api_key="test")
    response = await delegator.delegate(
        agent="planner",
        task="Plan implementation of feature X"
    )
    assert response.success
    assert "PLAN:" in response.result

async def test_delegate_to_agent_tool():
    """Test delegate_to_agent tool."""
    result = await delegate_to_agent(
        agent="planner",
        task="Create plan for database caching"
    )
    assert isinstance(result, str)
    assert len(result) > 0
```

**Integration Tests:**
```python
async def test_orchestrator_delegates_complex_task():
    """Test orchestrator recognizes and delegates complex tasks."""
    orchestrator = PolicyAwareLlmAgent(agent_name="orchestrator")

    # Register delegation tool
    orchestrator.register_tool(...)

    response = await orchestrator.chat(
        "Implement a caching system for database queries"
    )

    # Should have delegated to planner
    assert "planner" in response.lower() or "plan:" in response.lower()
```

### Configuration

No new configuration needed. The orchestrator automatically:
1. Loads planning agent when needed
2. Delegates based on task complexity
3. Caches loaded agents for reuse

### Migration Path

1. **Phase 1**: Deploy infrastructure (AgentDelegator, delegate_to_agent tool)
2. **Phase 2**: Add planning agent definition
3. **Phase 3**: Update orchestrator with delegation logic
4. **Phase 4**: Monitor and tune delegation criteria
5. **Phase 5**: Add more specialist agents as needed

### Performance Considerations

**Latency Impact:**
- Planning delegation adds ~2-5 seconds (one extra LLM call)
- Offset by better execution (fewer retries, better results)
- Cache loaded agents to avoid re-initialization

**Cost Impact:**
- Complex tasks: 2x API calls (planning + execution)
- Simple tasks: 1x API call (no delegation)
- Overall: ~30% cost increase for complex tasks
- Benefit: Higher quality, fewer failed attempts

**Optimization:**
- Parallel execution where possible
- Cache exploration results during planning
- Reuse plans for similar tasks
- Allow user to skip planning if desired

## References

- **Related ADRs**:
  - ADR-010: Markdown-Driven Agent Definition (foundation)
  - ADR-003: Google ADK Integration (agent infrastructure)
- **Agent Loader**: `adh_cli/agents/agent_loader.py`
- **Current Orchestrator**: `adh_cli/agents/orchestrator/agent.md`
- **PolicyAwareLlmAgent**: `adh_cli/core/policy_aware_llm_agent.py`

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-10-03 | Initial proposal | Allen Hutchison |
