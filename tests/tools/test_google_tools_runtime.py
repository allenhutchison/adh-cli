"""Runtime-oriented tests for Google tool helpers."""

import pytest

from adh_cli.tools import google_tools


@pytest.mark.asyncio
async def test_google_search_requires_query():
    """google_search should return a helpful error when query is missing."""
    result = await google_tools.google_search(query=None)

    assert result["success"] is False
    assert "required" in result["error"]


@pytest.mark.asyncio
async def test_google_url_context_requires_urls():
    """google_url_context should handle missing URLs gracefully."""
    result = await google_tools.google_url_context(urls=None)

    assert isinstance(result, str)
    assert "No URLs" in result
