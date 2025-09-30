"""Google ADK Agent-based service for improved tool handling."""

import os
import asyncio
from typing import Optional, List, Dict, Any, Callable, AsyncGenerator
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from google.adk.agents import LlmAgent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    USE_AGENT = True
except ImportError:
    USE_AGENT = False

from google import genai
from ..tools.shell import execute_command, list_directory, read_file
from ..tools.tool_registry import ToolRegistry
from ..agents.agent_loader import Agent as CustomAgent


@dataclass
class ADKAgentConfig:
    """Configuration for ADK Agent service."""
    api_key: Optional[str] = None
    model_name: str = "gemini-flash-latest"
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.95
    top_k: int = 40


class ADKAgentService:
    """Agent-based service for Google ADK with automatic tool handling."""

    def __init__(self, config: Optional[ADKAgentConfig] = None, enable_tools: bool = False, custom_agent: Optional[CustomAgent] = None):
        """Initialize the ADK agent service.

        Args:
            config: Configuration for the service
            enable_tools: Whether to enable tool/function calling
            custom_agent: Optional custom agent configuration
        """
        self.config = config or ADKAgentConfig()
        self.enable_tools = enable_tools
        self.custom_agent = custom_agent

        # Get API key
        self.api_key = (
            self.config.api_key
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )
        if not self.api_key:
            raise ValueError("API key not provided")

        # Initialize based on whether we have ADK agents available
        if USE_AGENT and enable_tools:
            self._init_agent_mode()
        else:
            self._init_fallback_mode()

    def _init_agent_mode(self):
        """Initialize using ADK's LlmAgent for proper tool handling."""
        # Configure tools
        tools = []
        if self.enable_tools:
            tools = [execute_command, list_directory, read_file]

        # Create instruction based on custom agent or default
        if self.custom_agent:
            instruction = self.custom_agent.system_prompt
        else:
            instruction = """You are a helpful AI assistant with access to tools for file system operations and code review.
When asked to review code or analyze files, use the available tools to:
1. List directories to understand project structure
2. Read files to examine code content
3. Provide detailed analysis and recommendations"""

        # Create LlmAgent with automatic tool handling
        self.llm_agent = LlmAgent(
            model=self.config.model_name,
            name="adh_assistant",
            description="AI assistant for development tasks",
            instruction=instruction,
            tools=tools if tools else None,
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            top_k=self.config.top_k,
            max_output_tokens=self.config.max_tokens,
        )

        # Session management for conversation history
        self.session_service = InMemorySessionService()
        self.session_id = "chat_session"
        self.user_id = "user"

        # Create runner
        self.runner = Runner(
            agent=self.llm_agent,
            app_name="adh_cli",
            session_service=self.session_service
        )

        # Initialize session
        asyncio.run(self._init_session())

    async def _init_session(self):
        """Initialize the chat session."""
        await self.session_service.create_session(
            app_name="adh_cli",
            user_id=self.user_id,
            session_id=self.session_id
        )

    def _init_fallback_mode(self):
        """Initialize using standard genai client without agents."""
        # Set API key for genai
        os.environ["GOOGLE_API_KEY"] = self.api_key

        self.client = genai.Client(api_key=self.api_key)
        self.llm_agent = None
        self.runner = None

        # Initialize chat session
        self._start_fallback_chat()

    def _start_fallback_chat(self):
        """Start a chat session in fallback mode."""
        config_params = {
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
            "max_output_tokens": self.config.max_tokens,
        }

        if self.enable_tools:
            # Add tools but with manual handling
            config_params["tools"] = [execute_command, list_directory, read_file]

        config = genai.types.GenerateContentConfig(**config_params)

        self.chat_session = self.client.chats.create(
            model=self.config.model_name,
            config=config
        )

    def send_message(self, message: str) -> str:
        """Send a message and get a response.

        Args:
            message: The message to send

        Returns:
            The response text
        """
        if self.llm_agent and self.runner:
            # Use agent mode with automatic tool handling
            return asyncio.run(self._send_agent_message(message))
        else:
            # Use fallback mode
            return self._send_fallback_message(message)

    async def _send_agent_message(self, message: str) -> str:
        """Send message using LlmAgent with automatic tool handling."""
        user_content = types.Content(role='user', parts=[types.Part(text=message)])

        response_text = ""
        async for event in self.runner.run_async(
            user_id=self.user_id,
            session_id=self.session_id,
            new_message=user_content
        ):
            # Collect the final response
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        response_text += part.text

        return response_text if response_text else "I've completed the requested analysis."

    def _send_fallback_message(self, message: str) -> str:
        """Send message using standard chat (fallback mode)."""
        try:
            response = self.chat_session.send_message(message)

            if response and hasattr(response, 'text') and response.text:
                return response.text
            else:
                return "I've completed the requested task."

        except Exception as e:
            return f"Error: {str(e)}"

    def send_message_streaming(self, message: str, status_callback: Optional[Callable[[str], None]] = None) -> str:
        """Send a message with streaming response.

        Args:
            message: The message to send
            status_callback: Callback for status updates

        Returns:
            The response text
        """
        if self.llm_agent and self.runner:
            # Use agent mode with streaming
            return asyncio.run(self._send_agent_message_streaming(message, status_callback))
        else:
            # Use fallback streaming
            return self._send_fallback_streaming(message, status_callback)

    async def _send_agent_message_streaming(self, message: str, status_callback: Optional[Callable[[str], None]] = None) -> str:
        """Send message using LlmAgent with streaming and status updates."""
        if status_callback:
            status_callback("⏳ Sending message to AI...")

        user_content = types.Content(role='user', parts=[types.Part(text=message)])

        response_text = ""
        tool_count = 0

        async for event in self.runner.run_async(
            user_id=self.user_id,
            session_id=self.session_id,
            new_message=user_content
        ):
            # Track tool usage
            if event.type == "tool_call" and status_callback:
                tool_count += 1
                tool_name = event.data.get("name", "tool") if hasattr(event, "data") else "tool"
                status_callback(f"🔧 Using {tool_name}...")

            # Collect response text
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        response_text += part.text
                        # Show preview
                        if status_callback and len(response_text) < 100:
                            preview = response_text[:50].replace('\n', ' ')
                            if len(response_text) > 50:
                                preview += "..."
                            status_callback(f"💭 {preview}")

        if status_callback and tool_count > 0:
            status_callback(f"✅ Executed {tool_count} tools")

        return response_text if response_text else "I've completed the analysis using the available tools."

    def _send_fallback_streaming(self, message: str, status_callback: Optional[Callable[[str], None]] = None) -> str:
        """Send message with streaming in fallback mode."""
        if status_callback:
            status_callback("⏳ Sending message to AI...")

        try:
            if hasattr(self.chat_session, 'send_message_stream'):
                stream = self.chat_session.send_message_stream(message)

                full_text = ""
                for chunk in stream:
                    if chunk and hasattr(chunk, 'text') and chunk.text:
                        full_text += chunk.text
                        if status_callback and len(full_text) < 100:
                            preview = full_text[:50].replace('\n', ' ')
                            if len(full_text) > 50:
                                preview += "..."
                            status_callback(f"💭 {preview}")

                return full_text if full_text else "Task completed."
            else:
                # No streaming available, use regular send
                response = self.chat_session.send_message(message)
                if response and hasattr(response, 'text'):
                    return response.text
                return "Task completed."

        except Exception as e:
            if status_callback:
                status_callback(f"❌ Error: {str(e)}")
            return f"Error: {str(e)}"

    def start_chat(self, history: Optional[List[Dict[str, str]]] = None):
        """Start or restart the chat session."""
        if self.llm_agent:
            # Agent mode manages its own session
            pass
        else:
            # Restart fallback chat
            self._start_fallback_chat()