"""Tests for PolicyAwareLlmAgent."""

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from google.genai import types as genai_types

from adh_cli.core.policy_aware_llm_agent import PolicyAwareLlmAgent
from adh_cli.core.tool_executor import ExecutionContext
from adh_cli.tools.google_tools import create_google_search_tool


class TestPolicyAwareLlmAgent:
    """Test PolicyAwareLlmAgent class."""

    @pytest.fixture
    def agent_without_api_key(self):
        """Create agent without API key (for testing structure)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PolicyAwareLlmAgent(
                api_key=None,
                policy_dir=Path(tmpdir),
            )
            yield agent

    @pytest.fixture
    def agent_with_mock_adk(self):
        """Create agent with mocked ADK components."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("adh_cli.core.policy_aware_llm_agent.LlmAgent") as mock_llm_agent,
                patch("adh_cli.core.policy_aware_llm_agent.Runner") as mock_runner,
                patch(
                    "adh_cli.core.policy_aware_llm_agent.InMemorySessionService"
                ) as mock_session,
            ):
                # Configure mocks
                mock_agent_instance = Mock()
                mock_llm_agent.return_value = mock_agent_instance

                mock_runner_instance = Mock()
                mock_runner_instance.run_async = AsyncMock()
                mock_runner.return_value = mock_runner_instance

                mock_session_instance = Mock()
                mock_session_instance.create_session = AsyncMock()
                mock_session.return_value = mock_session_instance

                agent = PolicyAwareLlmAgent(
                    api_key="test_key",
                    policy_dir=Path(tmpdir),
                )

                agent.runner = mock_runner_instance
                agent.session_service = mock_session_instance

                yield agent

    def test_agent_initialization_without_api_key(self, agent_without_api_key):
        """Test agent initializes without API key."""
        assert agent_without_api_key.api_key is None
        assert agent_without_api_key.llm_agent is None
        assert agent_without_api_key.runner is None
        assert agent_without_api_key.policy_engine is not None
        assert agent_without_api_key.safety_pipeline is not None

    def test_agent_initialization_with_api_key(self):
        """Test agent initializes with API key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("adh_cli.core.policy_aware_llm_agent.LlmAgent"),
                patch("adh_cli.core.policy_aware_llm_agent.Runner"),
                patch("adh_cli.core.policy_aware_llm_agent.InMemorySessionService"),
            ):
                agent = PolicyAwareLlmAgent(
                    api_key="test_key",
                    policy_dir=Path(tmpdir),
                )

                assert agent.api_key == "test_key"
                assert agent.llm_agent is not None
                assert agent.runner is not None

    def test_register_tool_without_api_key(self, agent_without_api_key):
        """Test tool registration without API key."""

        async def test_func(param: str):
            return f"Result: {param}"

        agent_without_api_key.register_tool(
            name="test_tool",
            description="A test tool",
            parameters={"param": {"type": "string"}},
            handler=test_func,
        )

        assert len(agent_without_api_key.tools) == 1
        assert "test_tool" in agent_without_api_key.tool_handlers

    def test_register_multiple_tools(self, agent_without_api_key):
        """Test registering multiple tools."""

        async def tool1():
            return "tool1"

        async def tool2():
            return "tool2"

        agent_without_api_key.register_tool(
            name="tool1",
            description="Tool 1",
            parameters={},
            handler=tool1,
        )

        agent_without_api_key.register_tool(
            name="tool2",
            description="Tool 2",
            parameters={},
            handler=tool2,
        )

        assert len(agent_without_api_key.tools) == 2
        assert "tool1" in agent_without_api_key.tool_handlers
        assert "tool2" in agent_without_api_key.tool_handlers

    def test_register_native_tool(self, agent_without_api_key):
        """Native built-in tools are tracked alongside function tools."""

        agent_without_api_key.register_native_tool(
            name="google_search",
            description="Search the public web",
            parameters={"query": {"type": "string"}},
            factory=create_google_search_tool,
        )

        assert "google_search" in agent_without_api_key.native_tools
        assert agent_without_api_key.tool_metadata["google_search"]["description"]
        descriptions = agent_without_api_key._generate_tool_descriptions()
        assert "google_search" in descriptions

    def test_update_policies_preserves_native_tools(self):
        """Native tools remain registered after policy reloads."""

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PolicyAwareLlmAgent(api_key=None, policy_dir=Path(tmpdir))
            agent.register_native_tool(
                name="google_search",
                description="Search the public web",
                parameters={"query": {"type": "string"}},
                factory=create_google_search_tool,
            )

            # Policy directory swap should keep native tool
            new_policy_dir = Path(tmpdir) / "policies"
            new_policy_dir.mkdir(exist_ok=True)

            agent.update_policies(new_policy_dir)

            assert "google_search" in agent.native_tools
            assert agent.tool_metadata["google_search"]["description"]

    @pytest.mark.asyncio
    async def test_chat_without_api_key(self, agent_without_api_key):
        """Test chat fails gracefully without API key."""
        result = await agent_without_api_key.chat("Hello")

        assert "not initialized" in result.lower() or "api key" in result.lower()

    @pytest.mark.asyncio
    async def test_chat_with_mocked_adk(self, agent_with_mock_adk):
        """Test chat with mocked ADK components."""
        # Mock event stream
        mock_event = Mock()
        mock_event.get_function_calls.return_value = []
        mock_event.get_function_responses.return_value = []
        mock_event.is_final_response.return_value = True

        mock_part = Mock()
        mock_part.text = "Hello! How can I help you?"
        mock_content = Mock()
        mock_content.parts = [mock_part]
        mock_event.content = mock_content

        # Setup async generator
        async def mock_event_stream(*args, **kwargs):
            yield mock_event

        agent_with_mock_adk.runner.run_async = mock_event_stream

        result = await agent_with_mock_adk.chat("Hello", context=ExecutionContext())

        assert "Hello" in result
        assert "help" in result

    @pytest.mark.asyncio
    async def test_chat_with_function_calls(self, agent_with_mock_adk):
        """Test chat handles function calls in event stream."""
        # Mock event stream with function calls
        mock_fc = Mock()
        mock_fc.name = "test_tool"

        mock_event1 = Mock()
        mock_event1.get_function_calls.return_value = [mock_fc]
        mock_event1.get_function_responses.return_value = []
        mock_event1.is_final_response.return_value = False
        mock_event1.content = None

        mock_event2 = Mock()
        mock_event2.get_function_calls.return_value = []
        mock_event2.get_function_responses.return_value = [Mock()]
        mock_event2.is_final_response.return_value = False
        mock_event2.content = None

        mock_event3 = Mock()
        mock_event3.get_function_calls.return_value = []
        mock_event3.get_function_responses.return_value = []
        mock_event3.is_final_response.return_value = True
        mock_part = Mock()
        mock_part.text = "Task completed"
        mock_content = Mock()
        mock_content.parts = [mock_part]
        mock_event3.content = mock_content

        async def mock_event_stream(*args, **kwargs):
            yield mock_event1
            yield mock_event2
            yield mock_event3

        agent_with_mock_adk.runner.run_async = mock_event_stream

        result = await agent_with_mock_adk.chat(
            "Do something", context=ExecutionContext()
        )

        assert "Task completed" in result
        # Note: Tool execution notifications removed - now handled by ToolExecutionWidget UI

    @pytest.mark.asyncio
    async def test_chat_handles_permission_error(self, agent_with_mock_adk):
        """Test chat handles PermissionError from policy."""

        async def mock_event_stream(*args, **kwargs):
            raise PermissionError("Tool blocked by policy")
            yield  # Never reached

        agent_with_mock_adk.runner.run_async = mock_event_stream

        result = await agent_with_mock_adk.chat("Do something dangerous")

        assert "blocked by policy" in result.lower()

    @pytest.mark.asyncio
    async def test_chat_handles_general_error(self, agent_with_mock_adk):
        """Test chat handles general exceptions."""

        async def mock_event_stream(*args, **kwargs):
            raise ValueError("Some error")
            yield  # Never reached

        agent_with_mock_adk.runner.run_async = mock_event_stream

        result = await agent_with_mock_adk.chat("Hello")

        assert "error" in result.lower()

    def test_audit_logger_creation_with_path(self):
        """Test audit logger is created when path provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = Path(tmpdir) / "audit.log"

            agent = PolicyAwareLlmAgent(
                api_key=None,
                audit_log_path=audit_path,
            )

            assert agent.audit_logger is not None

    def test_audit_logger_none_without_path(self, agent_without_api_key):
        """Test audit logger is None when no path provided."""
        assert agent_without_api_key.audit_logger is None

    @pytest.mark.asyncio
    async def test_audit_logging_writes_to_file(self):
        """Test audit logger actually writes to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = Path(tmpdir) / "audit.log"

            agent = PolicyAwareLlmAgent(
                api_key=None,
                audit_log_path=audit_path,
            )

            # Trigger audit log
            if agent.audit_logger:
                await agent.audit_logger(
                    tool_name="test_tool", parameters={"param": "value"}, success=True
                )

            # Check file was created and has content
            assert audit_path.exists()
            content = audit_path.read_text()
            assert "test_tool" in content
            assert "param" in content

    def test_update_policies(self, agent_without_api_key):
        """Test updating policies."""

        # Register a tool first
        async def test_func():
            return "result"

        agent_without_api_key.register_tool(
            name="test_tool",
            description="Test",
            parameters={},
            handler=test_func,
        )

        # Update policies
        with tempfile.TemporaryDirectory() as new_tmpdir:
            agent_without_api_key.update_policies(Path(new_tmpdir))

            # Tool should still be registered
            assert "test_tool" in agent_without_api_key.tool_handlers

    def test_set_user_preferences(self, agent_without_api_key):
        """Test setting user preferences."""
        prefs = {"auto_approve": ["read_file"], "never_allow": ["rm"]}

        agent_without_api_key.set_user_preferences(prefs)

        assert "auto_approve" in agent_without_api_key.policy_engine.user_preferences
        assert "never_allow" in agent_without_api_key.policy_engine.user_preferences

    def test_tool_executor_property(self, agent_without_api_key):
        """Test tool_executor property for compatibility."""
        executor = agent_without_api_key.tool_executor

        assert executor is not None
        assert hasattr(executor, "execute")

    @pytest.mark.asyncio
    async def test_tool_executor_execute(self, agent_without_api_key):
        """Test tool_executor.execute method."""

        async def test_func(param: str):
            return f"Result: {param}"

        agent_without_api_key.register_tool(
            name="test_tool",
            description="Test",
            parameters={},
            handler=test_func,
        )

        executor = agent_without_api_key.tool_executor
        result = await executor.execute(
            tool_name="test_tool", parameters={"param": "value"}
        )

        assert result.success is True
        assert "Result: value" in str(result.result)

    @pytest.mark.asyncio
    async def test_tool_executor_execute_not_found(self, agent_without_api_key):
        """Test tool_executor.execute with non-existent tool."""
        executor = agent_without_api_key.tool_executor
        result = await executor.execute(tool_name="nonexistent", parameters={})

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_agent_loading_default_orchestrator(self):
        """Test loading default orchestrator agent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PolicyAwareLlmAgent(
                api_key=None, policy_dir=Path(tmpdir), agent_name="orchestrator"
            )

            # Should load orchestrator agent definition
            assert agent.agent_definition is not None
            assert agent.agent_definition.name == "orchestrator"
            assert agent.agent_definition.model == "gemini-flash-latest"
            assert agent.model_name == "gemini-flash-latest"

    def test_agent_loading_nonexistent_agent(self):
        """Test loading non-existent agent falls back to defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PolicyAwareLlmAgent(
                api_key=None,
                policy_dir=Path(tmpdir),
                agent_name="nonexistent_agent",
                model_name="gemini-pro",
                temperature=0.5,
                max_tokens=1024,
            )

            # Should fallback to passed parameters
            assert agent.agent_definition is None
            assert agent.model_name == "gemini-pro"
            assert agent.temperature == 0.5
            assert agent.max_tokens == 1024

    def test_generate_tool_descriptions_empty(self):
        """Test generating tool descriptions with no tools."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PolicyAwareLlmAgent(api_key=None, policy_dir=Path(tmpdir))

            descriptions = agent._generate_tool_descriptions()
            assert "No tools currently available" in descriptions

    def test_generate_tool_descriptions_with_tools(self):
        """Test generating tool descriptions with registered tools."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PolicyAwareLlmAgent(api_key=None, policy_dir=Path(tmpdir))

            # Register a test tool
            async def test_tool(param: str):
                """Test tool description."""
                return f"Result: {param}"

            agent.register_tool(
                name="test_tool",
                description="A test tool",
                parameters={"param": {"type": "string"}},
                handler=test_tool,
            )

            descriptions = agent._generate_tool_descriptions()
            assert "test_tool" in descriptions
            assert "A test tool" in descriptions

    def test_system_prompt_with_agent_definition(self):
        """Test system prompt uses agent definition."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PolicyAwareLlmAgent(
                api_key=None, policy_dir=Path(tmpdir), agent_name="orchestrator"
            )

            # Register a tool so we have tool descriptions
            async def test_tool(param: str):
                """Test tool."""
                return param

            agent.register_tool(
                name="test_tool", description="Test", parameters={}, handler=test_tool
            )

            prompt = agent._get_system_instruction()

            # Should contain parts of the orchestrator prompt
            assert "helpful AI assistant" in prompt
            assert (
                "Tool Execution Guidelines" in prompt
            )  # Updated from new orchestrator prompt
            assert "Agent Delegation" in prompt  # Should have new delegation section
            # Should have tool descriptions injected
            assert "test_tool" in prompt

    def test_system_prompt_fallback_without_agent_definition(self):
        """Test system prompt falls back when agent definition not loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PolicyAwareLlmAgent(
                api_key=None, policy_dir=Path(tmpdir), agent_name="nonexistent"
            )

            prompt = agent._get_system_instruction()

            # Should contain fallback prompt
            assert "helpful AI assistant" in prompt
            assert "IMMEDIATELY use tools" in prompt

    def test_url_context_failed_detects_success(self, agent_without_api_key):
        """URL context fallback not needed when retrieval succeeds."""

        event = SimpleNamespace(
            custom_metadata={
                "urlContextMetadata": {
                    "urlMetadata": [
                        {
                            "urlRetrievalStatus": genai_types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_SUCCESS.value
                        }
                    ]
                }
            },
            grounding_metadata=None,
        )

        assert (
            agent_without_api_key._url_context_failed(event, initial_response="result")
            is False
        )

    def test_url_context_failed_detects_failure(self, agent_without_api_key):
        """URL context fallback triggers when retrieval metadata signals failure."""

        event = SimpleNamespace(
            custom_metadata={
                "urlContextMetadata": {
                    "urlMetadata": [
                        {
                            "urlRetrievalStatus": genai_types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_ERROR.value
                        }
                    ]
                }
            },
            grounding_metadata=None,
        )

        assert (
            agent_without_api_key._url_context_failed(event, initial_response="")
            is True
        )

    def test_extract_urls_deduplicates(self, agent_without_api_key):
        """URL extraction removes trailing punctuation and duplicates."""

        text = "See https://example.com/path, and https://example.com/path)."

        assert agent_without_api_key._extract_urls(text) == ["https://example.com/path"]

    @pytest.mark.asyncio
    async def test_maybe_run_url_context_fallback_invokes_handler(
        self, agent_with_mock_adk
    ):
        """Fallback handler runs when metadata indicates URL retrieval failure."""

        url = "https://example.com/data"
        event = SimpleNamespace(
            custom_metadata={
                "urlContextMetadata": {
                    "urlMetadata": [
                        {
                            "urlRetrievalStatus": genai_types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_ERROR.value
                        }
                    ]
                }
            },
            grounding_metadata=None,
        )

        agent_with_mock_adk._run_url_context_fallback = AsyncMock(
            return_value="fallback response"
        )

        result = await agent_with_mock_adk._maybe_run_url_context_fallback(
            original_message=f"Please analyze {url}",
            final_event=event,
            initial_response="",
        )

        assert result == "fallback response"
        agent_with_mock_adk._run_url_context_fallback.assert_awaited_once_with(
            original_message=f"Please analyze {url}", urls=[url]
        )

    @pytest.mark.asyncio
    async def test_maybe_run_url_context_fallback_skips_without_urls(
        self, agent_with_mock_adk
    ):
        """Fallback isn't attempted when the message has no URLs."""

        event = SimpleNamespace(custom_metadata={}, grounding_metadata=None)

        result = await agent_with_mock_adk._maybe_run_url_context_fallback(
            original_message="No links here",
            final_event=event,
            initial_response="",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_run_url_context_fallback_happy_path(
        self, agent_with_mock_adk, monkeypatch
    ):
        """Local fetch fallback returns generated text when everything succeeds."""

        async def fake_fetch(url: str, **kwargs):  # noqa: D401 - simple stub
            assert url == "https://example.com/file"
            return {"success": True, "content": "Example content"}

        monkeypatch.setattr(
            "adh_cli.tools.web_tools.fetch_url", fake_fetch, raising=True
        )

        agent_with_mock_adk._generate_fallback_response = AsyncMock(
            return_value=(True, "Generated answer")
        )

        result = await agent_with_mock_adk._run_url_context_fallback(
            original_message="Summarize https://example.com/file",
            urls=["https://example.com/file"],
        )

        assert "Generated answer" in result
        assert "fallback fetch for https://example.com/file" in result

    @pytest.mark.asyncio
    async def test_run_url_context_fallback_multiple_urls(
        self, agent_with_mock_adk, monkeypatch
    ):
        """Fallback collates multiple URLs and reports failures."""

        async def fake_fetch(url: str, **kwargs):
            if url.endswith("first"):
                return {"success": True, "content": "First content"}
            raise ValueError("invalid url")

        monkeypatch.setattr(
            "adh_cli.tools.web_tools.fetch_url", fake_fetch, raising=True
        )

        agent_with_mock_adk._generate_fallback_response = AsyncMock(
            return_value=(True, "Combined answer")
        )

        urls = [
            "https://example.com/first",
            "https://example.com/second",
        ]

        result = await agent_with_mock_adk._run_url_context_fallback(
            original_message="Use these URLs",
            urls=urls,
        )

        assert "Combined answer" in result
        assert "Some URLs failed" in result

        prompt = agent_with_mock_adk._generate_fallback_response.call_args[0][0]
        assert "https://example.com/first" in prompt
        assert "https://example.com/second" in prompt
        assert "Some URLs could not be fetched" in prompt
