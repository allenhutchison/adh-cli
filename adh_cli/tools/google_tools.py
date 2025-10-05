"""Helpers for integrating Google built-in tools."""

from __future__ import annotations

from google.adk.tools.google_search_tool import GoogleSearchTool


def create_google_search_tool() -> GoogleSearchTool:
    """Return a GoogleSearchTool instance."""

    return GoogleSearchTool()


__all__ = ["create_google_search_tool"]
