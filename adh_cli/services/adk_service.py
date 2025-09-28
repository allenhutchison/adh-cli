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
from ..tools import shell_tools


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

    def __init__(self, config: Optional[ADKConfig] = None, enable_tools: bool = False):
        """Initialize the ADK service.

        Args:
            config: Configuration for the ADK service
            enable_tools: Whether to enable tool/function calling
        """
        self.config = config or ADKConfig()
        self._client = None
        self._chat_session = None
        self.enable_tools = enable_tools
        self.tools = [shell_tools.execute_command, shell_tools.list_directory, shell_tools.read_file] if enable_tools else []
        self._initialize()

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

    def start_chat(self, history: Optional[List[Dict[str, str]]] = None) -> None:
        """Start a chat session with optional tool support."""
        if not self._client:
            raise RuntimeError("ADK service not initialized")

        chat_history = []
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

    def send_message(self, message: str) -> str:
        """Send a message in the chat session, handling tool calls if needed."""
        if not self._chat_session:
            self.start_chat()

        try:
            response = self._chat_session.send_message(message)

            # The model should now be aware of tools and use them automatically
            # when appropriate based on the user's request
            return response.text

        except Exception as e:
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