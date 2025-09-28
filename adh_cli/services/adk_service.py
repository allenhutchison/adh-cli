"""Google ADK (AI Development Kit) service integration."""

import os
import json
from typing import Optional, List, Dict, Any, Callable
from google import genai
from google.genai import types
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import our tools
from ..tools.shell import execute_command, list_directory, read_file
from ..tools.tool_registry import ToolRegistry
from ..agents.agent_loader import Agent


@dataclass
class ADKConfig:
    """Configuration for Google ADK."""
    api_key: Optional[str] = None
    model_name: str = "gemini-flash-latest"
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.95
    top_k: int = 40


class ADKService:
    """Service class for Google ADK interactions."""

    def __init__(self, config: Optional[ADKConfig] = None, enable_tools: bool = False, agent: Optional[Agent] = None):
        """Initialize the ADK service.

        Args:
            config: Configuration for the ADK service
            enable_tools: Whether to enable tool/function calling
            agent: Optional Agent to configure the service
        """
        self.config = config or ADKConfig()
        self.agent = agent
        self._client = None
        self._chat_session = None
        self.enable_tools = enable_tools
        self.tool_registry = ToolRegistry()

        # Configure from agent if provided
        if agent:
            self._configure_from_agent(agent)
        else:
            # Legacy tool loading
            self.tools = [execute_command, list_directory, read_file] if enable_tools else []

        self._initialize()

    def _configure_from_agent(self, agent: Agent):
        """Configure the service from an agent definition.

        Args:
            agent: Agent instance with configuration
        """
        # Update config from agent
        self.config.model_name = agent.model
        self.config.temperature = agent.temperature
        self.config.max_tokens = agent.max_tokens
        self.config.top_p = agent.top_p
        self.config.top_k = agent.top_k

        # Load tools specified by the agent
        if agent.tools:
            self.enable_tools = True
            self.tools = self.tool_registry.get_functions(agent.tools)
        else:
            self.tools = []

    def _initialize(self) -> None:
        """Initialize the Google ADK client."""
        # Check for API key in multiple places
        api_key = (
            self.config.api_key
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )
        if not api_key:
            raise ValueError(
                "API key not provided. Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable or pass it in config."
            )

        self._client = genai.Client(api_key=api_key)

    def generate_text(self, prompt: str) -> str:
        """Generate text based on a prompt."""
        if not self._client:
            raise RuntimeError("ADK service not initialized")

        config = genai.types.GenerateContentConfig(
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            top_k=self.config.top_k,
            max_output_tokens=self.config.max_tokens,
        )

        response = self._client.models.generate_content(
            model=self.config.model_name,
            contents=prompt,
            config=config
        )
        return response.text

    def start_chat(self, history: Optional[List[Dict[str, str]]] = None, variables: Optional[Dict[str, Any]] = None) -> None:
        """Start a chat session with optional tool support.

        Args:
            history: Optional chat history
            variables: Variables for agent prompt rendering
        """
        if not self._client:
            raise RuntimeError("ADK service not initialized")

        chat_history = []

        # Add system prompt from agent if available
        if self.agent and self.agent.system_prompt:
            tool_descriptions = ""
            if self.agent.tools:
                tool_descriptions = self.tool_registry.get_tool_descriptions(self.agent.tools)

            system_prompt = self.agent.render_system_prompt(
                variables or {},
                tool_descriptions
            )

            # Add system prompt as first message
            chat_history.append({
                "role": "user",
                "parts": [{"text": f"System: {system_prompt}"}]
            })
            chat_history.append({
                "role": "model",
                "parts": [{"text": "Understood. I'll follow these instructions."}]
            })

        if history:
            for msg in history:
                role = "user" if msg.get("role") == "user" else "model"
                chat_history.append({
                    "role": role,
                    "parts": [{"text": msg.get("content", "")}]
                })

        # Build config with tools if enabled
        config_params = {
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
            "max_output_tokens": self.config.max_tokens,
        }

        if self.enable_tools and self.tools:
            config_params["tools"] = self.tools

        config = genai.types.GenerateContentConfig(**config_params)

        # Create chat session with tools in config
        self._chat_session = self._client.chats.create(
            model=self.config.model_name,
            config=config,
            history=chat_history if chat_history else None
        )

    def send_message(self, message: str, variables: Optional[Dict[str, Any]] = None) -> str:
        """Send a message in the chat session, handling tool calls if needed.

        Args:
            message: The message to send
            variables: Optional variables for agent prompt rendering

        Returns:
            Response text from the model
        """
        if not self._chat_session:
            self.start_chat(variables=variables)

        try:
            # If agent has user prompt template, use it
            if self.agent and self.agent.user_prompt_template and variables:
                # Check if this is meant to use the template
                if any(var in variables for var in self.agent.variables):
                    message = self.agent.render_user_prompt(variables)

            response = self._chat_session.send_message(message)

            # The model should now be aware of tools and use them automatically
            # when appropriate based on the user's request
            return response.text

        except Exception as e:
            return f"Error: {str(e)}"

    def send_message_streaming(self, message: str, status_callback: Optional[Callable[[str], None]] = None, variables: Optional[Dict[str, Any]] = None):
        """Send a message with streaming response and status updates.

        Args:
            message: The message to send
            status_callback: Optional callback for status updates
            variables: Optional variables for agent prompt rendering

        Returns:
            Response text from the model
        """
        if not self._chat_session:
            self.start_chat(variables=variables)

        # If agent has user prompt template, use it
        if self.agent and self.agent.user_prompt_template and variables:
            if any(var in variables for var in self.agent.variables):
                message = self.agent.render_user_prompt(variables)

        try:
            # Send initial status
            if status_callback:
                status_callback("⏳ Sending message to AI...")

            # Try to use streaming if available
            # The Google genai library uses send_message_stream for streaming
            if hasattr(self._chat_session, 'send_message_stream'):
                # Stream the response
                stream = self._chat_session.send_message_stream(message)

                full_text = ""
                for chunk in stream:
                    # Process each chunk
                    if hasattr(chunk, 'text'):
                        chunk_text = chunk.text
                        if chunk_text:
                            full_text += chunk_text
                            # Show progress in status
                            if status_callback and len(full_text) < 100:
                                preview = full_text[:50].replace('\n', ' ')
                                if len(full_text) > 50:
                                    preview += "..."
                                status_callback(f"💭 {preview}")

                    # Check for tool calls in chunk
                    if hasattr(chunk, 'candidates') and chunk.candidates:
                        candidate = chunk.candidates[0]
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            for part in candidate.content.parts:
                                if hasattr(part, 'function_call'):
                                    tool_name = part.function_call.name if hasattr(part.function_call, 'name') else 'tool'
                                    if status_callback:
                                        status_callback(f"🔧 Calling {tool_name}...")

                return full_text
            else:
                # Fallback to non-streaming
                if status_callback:
                    status_callback("💭 AI is processing...")

                response = self._chat_session.send_message(message)
                return response.text

        except Exception as e:
            if status_callback:
                status_callback(f"❌ Error: {str(e)}")
            return f"Error: {str(e)}"

    def list_models(self) -> List[str]:
        """List available models."""
        if not self._client:
            raise RuntimeError("ADK service not initialized")

        models = []
        for model in self._client.models.list():
            models.append(model.name)
        return models

    def update_config(self, **kwargs: Any) -> None:
        """Update configuration settings."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self._initialize()