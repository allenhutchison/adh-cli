"""Helpers for integrating Google built-in tools."""

from __future__ import annotations

from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.tools.base_tool import BaseTool
from google.genai import types


class UrlContextTool(BaseTool):
    """Enable Gemini's built-in URL context capability for a request."""

    def __init__(self) -> None:
        super().__init__(
            name="google_url_context",
            description="Enables grounding responses in the content of provided URLs.",
        )

    async def process_llm_request(self, *, tool_context, llm_request) -> None:  # type: ignore[override]
        llm_request.config = llm_request.config or types.GenerateContentConfig()
        llm_request.config.tools = llm_request.config.tools or []

        already_enabled = any(
            getattr(tool, "url_context", None) is not None
            for tool in llm_request.config.tools
        )
        if not already_enabled:
            llm_request.config.tools.append(
                types.Tool(url_context=types.UrlContext())
            )


def create_google_search_tool() -> GoogleSearchTool:
    """Return a GoogleSearchTool instance."""

    return GoogleSearchTool()


def create_url_context_tool() -> UrlContextTool:
    """Return a UrlContextTool instance."""

    return UrlContextTool()


__all__ = ["create_google_search_tool", "create_url_context_tool"]
