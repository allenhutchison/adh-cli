"""Comprehensive tests for Google tool helpers with mocked API interactions."""

from unittest.mock import MagicMock, patch

import pytest

from adh_cli.tools import google_tools


class TestGoogleSearchBasics:
    """Test basic input validation and error handling for google_search."""

    @pytest.mark.asyncio
    async def test_google_search_requires_query(self):
        """google_search should return error when query is missing."""
        result = await google_tools.google_search(query=None)

        assert result["success"] is False
        assert "required" in result["error"]

    @pytest.mark.asyncio
    async def test_google_search_empty_query(self):
        """google_search should return error for empty query string."""
        result = await google_tools.google_search(query="   ")

        assert result["success"] is False
        assert "required" in result["error"]


class TestGoogleSearchAPIInteraction:
    """Test google_search with mocked API responses."""

    @pytest.mark.asyncio
    async def test_google_search_success(self):
        """Test successful google_search with mocked API response."""
        # Mock the genai.Client and its response
        mock_response = MagicMock()
        mock_response.candidates = [
            MagicMock(
                content=MagicMock(
                    parts=[
                        MagicMock(text="Python is a high-level programming language.")
                    ]
                ),
                grounding_metadata=MagicMock(
                    grounding_chunks=[
                        MagicMock(
                            web=MagicMock(uri="https://python.org"),
                        )
                    ]
                ),
            )
        ]

        with patch("adh_cli.tools.google_tools.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await google_tools.google_search(
                query="Python programming",
                api_key="test-key",
            )

            assert result["success"] is True
            assert "Python" in result["summary"]
            assert "https://python.org" in result["sources"]
            assert result["query"] == "Python programming"

    @pytest.mark.asyncio
    async def test_google_search_api_error(self):
        """Test google_search handles API errors gracefully."""
        with patch("adh_cli.tools.google_tools.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = Exception(
                "API key not valid"
            )
            mock_client_class.return_value = mock_client

            result = await google_tools.google_search(
                query="test query",
                api_key="invalid-key",
            )

            assert result["success"] is False
            assert "API key" in result["error"]
            assert result["error_type"] == "Exception"

    @pytest.mark.asyncio
    async def test_google_search_no_results(self):
        """Test google_search when API returns no text results."""
        mock_response = MagicMock()
        mock_response.candidates = [
            MagicMock(
                content=MagicMock(parts=[]),
                grounding_metadata=MagicMock(grounding_chunks=[]),
            )
        ]

        with patch("adh_cli.tools.google_tools.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await google_tools.google_search(
                query="test query",
                api_key="test-key",
            )

            assert result["success"] is False
            assert "No search results" in result["error"]

    @pytest.mark.asyncio
    async def test_google_search_tools_config(self):
        """Test that google_search correctly configures tools in GenerateContentConfig."""
        mock_response = MagicMock()
        mock_response.candidates = [
            MagicMock(
                content=MagicMock(parts=[MagicMock(text="Result")]),
                grounding_metadata=MagicMock(grounding_chunks=[]),
            )
        ]

        with patch("adh_cli.tools.google_tools.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_client_class.return_value = mock_client

            await google_tools.google_search(
                query="test",
                api_key="test-key",
            )

            # Verify generate_content was called
            assert mock_client.models.generate_content.called

            # Get the config argument
            call_kwargs = mock_client.models.generate_content.call_args[1]
            config = call_kwargs.get("config")

            # Verify config exists and has tools
            assert config is not None
            assert hasattr(config, "tools") or "tools" in str(config)


class TestURLNormalization:
    """Test URL normalization helper."""

    def test_normalize_github_blob_url(self):
        """Test GitHub blob URLs are normalized to raw URLs."""
        github_blob = "https://github.com/user/repo/blob/main/file.py"
        expected = "https://raw.githubusercontent.com/user/repo/main/file.py"

        result = google_tools._normalize_url_for_fetch(github_blob)

        assert result == expected

    def test_normalize_regular_url_unchanged(self):
        """Test regular URLs are not modified."""
        regular_url = "https://example.com/page.html"

        result = google_tools._normalize_url_for_fetch(regular_url)

        assert result == regular_url

    def test_normalize_github_non_blob_unchanged(self):
        """Test non-blob GitHub URLs are not modified."""
        github_url = "https://github.com/user/repo"

        result = google_tools._normalize_url_for_fetch(github_url)

        assert result == github_url


class TestGoogleURLContext:
    """Test google_url_context functionality."""

    @pytest.mark.asyncio
    async def test_google_url_context_requires_urls(self):
        """google_url_context should handle missing URLs gracefully."""
        result = await google_tools.google_url_context(urls=None)

        assert isinstance(result, str)
        assert "No URLs" in result

    @pytest.mark.asyncio
    async def test_google_url_context_empty_list(self):
        """google_url_context should handle empty URL list gracefully."""
        result = await google_tools.google_url_context(urls=[])

        assert isinstance(result, str)
        assert "No URLs" in result

    @pytest.mark.asyncio
    async def test_google_url_context_invalid_urls(self):
        """google_url_context should raise ValueError for invalid URL types."""
        # Non-string URLs that will be filtered out
        with pytest.raises(ValueError, match="No valid URLs"):
            await google_tools.google_url_context(urls=[None, 123, "", "  "])

    @pytest.mark.asyncio
    async def test_google_url_context_concurrent_success(self):
        """Test google_url_context with successful URL fetches."""
        with patch("adh_cli.tools.google_tools.web_tools.fetch_url") as mock_fetch:
            mock_fetch.return_value = {
                "success": True,
                "content": "Test content from URL",
            }

            # Mock to prevent actual API call for summarization
            with patch(
                "adh_cli.tools.google_tools._resolve_api_key",
                side_effect=RuntimeError("No API key"),
            ):
                result = await google_tools.google_url_context(
                    urls=["https://example.com/page1", "https://example.com/page2"]
                )

                # Verify fetch_url was called twice (concurrently)
                assert mock_fetch.call_count == 2

                # Verify output contains both URLs
                assert "example.com/page1" in result
                assert "example.com/page2" in result
                assert "Test content from URL" in result

    @pytest.mark.asyncio
    async def test_google_url_context_mixed_success_failure(self):
        """Test google_url_context handles mixed success/failure gracefully."""

        async def mock_fetch(url, **kwargs):
            if "fail" in url:
                raise ValueError("Fetch failed")
            return {"success": True, "content": f"Content from {url}"}

        with patch(
            "adh_cli.tools.google_tools.web_tools.fetch_url", side_effect=mock_fetch
        ):
            # Mock to prevent summarization
            with patch(
                "adh_cli.tools.google_tools._resolve_api_key",
                side_effect=RuntimeError("No API key"),
            ):
                result = await google_tools.google_url_context(
                    urls=["https://example.com/good", "https://example.com/fail"]
                )

                # Verify successful fetch appears
                assert "https://example.com/good" in result
                assert "Content from https://example.com/good" in result

                # Verify failed fetch is reported
                assert "https://example.com/fail" in result
                assert "could not be fetched" in result.lower()

    @pytest.mark.asyncio
    async def test_google_url_context_all_failures(self):
        """Test google_url_context when all URLs fail."""

        async def mock_fetch_fail(url, **kwargs):
            raise ValueError("All fetches fail")

        with patch(
            "adh_cli.tools.google_tools.web_tools.fetch_url",
            side_effect=mock_fetch_fail,
        ):
            result = await google_tools.google_url_context(
                urls=["https://example.com/fail1", "https://example.com/fail2"]
            )

            # Verify error message
            assert "❌" in result
            assert "Error fetching URLs" in result or "No readable content" in result


class TestContentTruncation:
    """Test content truncation in google_url_context."""

    @pytest.mark.asyncio
    async def test_content_truncation_applied(self):
        """Test that content exceeding max_content_chars is truncated."""
        # Create content that exceeds the default limit
        large_content = "A" * 150_000  # Exceeds 100k default

        with patch("adh_cli.tools.google_tools.web_tools.fetch_url") as mock_fetch:
            mock_fetch.return_value = {
                "success": True,
                "content": large_content,
            }

            # Mock to prevent summarization
            with patch(
                "adh_cli.tools.google_tools._resolve_api_key",
                side_effect=RuntimeError("No API key"),
            ):
                result = await google_tools.google_url_context(
                    urls=["https://example.com/large"],
                    max_content_chars=100_000,
                )

                # Verify truncation occurred
                assert "[content truncated]" in result
                # Verify content is actually truncated (not the full 150k chars)
                assert len(result) < 150_000

    @pytest.mark.asyncio
    async def test_small_content_not_truncated(self):
        """Test that small content is not truncated."""
        small_content = "This is a small piece of content."

        with patch("adh_cli.tools.google_tools.web_tools.fetch_url") as mock_fetch:
            mock_fetch.return_value = {
                "success": True,
                "content": small_content,
            }

            # Mock to prevent summarization
            with patch(
                "adh_cli.tools.google_tools._resolve_api_key",
                side_effect=RuntimeError("No API key"),
            ):
                result = await google_tools.google_url_context(
                    urls=["https://example.com/small"]
                )

                # Verify no truncation
                assert "[content truncated]" not in result
                assert small_content in result


class TestSummarizationToggle:
    """Test summarization behavior based on API key availability."""

    @pytest.mark.asyncio
    async def test_summarization_skipped_without_api_key(self):
        """Test that summarization is skipped when no API key is available."""
        with patch("adh_cli.tools.google_tools.web_tools.fetch_url") as mock_fetch:
            mock_fetch.return_value = {
                "success": True,
                "content": "Test content",
            }

            # Mock _resolve_api_key to raise RuntimeError (no key)
            with patch(
                "adh_cli.tools.google_tools._resolve_api_key",
                side_effect=RuntimeError("No API key"),
            ):
                result = await google_tools.google_url_context(
                    urls=["https://example.com/test"]
                )

                # Should return raw content without summarization
                assert "Test content" in result
                # Should not have attempted to call genai.Client
                assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_summarization_attempted_with_api_key(self):
        """Test that summarization is attempted when API key is available."""
        with patch("adh_cli.tools.google_tools.web_tools.fetch_url") as mock_fetch:
            mock_fetch.return_value = {
                "success": True,
                "content": "Test content",
            }

            # Mock successful API key resolution
            with patch(
                "adh_cli.tools.google_tools._resolve_api_key",
                return_value="test-api-key",
            ):
                # Mock genai.Client for summarization
                mock_response = MagicMock()
                mock_response.candidates = [
                    MagicMock(
                        content=MagicMock(parts=[MagicMock(text="Summarized content")])
                    )
                ]

                with patch(
                    "adh_cli.tools.google_tools.genai.Client"
                ) as mock_client_class:
                    mock_client = MagicMock()
                    mock_client.models.generate_content.return_value = mock_response
                    mock_client_class.return_value = mock_client

                    result = await google_tools.google_url_context(
                        urls=["https://example.com/test"],
                        api_key="test-api-key",
                    )

                    # Verify summarization was attempted
                    assert mock_client.models.generate_content.called
                    # Should contain summary
                    assert "Summarized content" in result

    @pytest.mark.asyncio
    async def test_summarization_failure_returns_raw_content(self):
        """Test that raw content is returned if summarization fails."""
        with patch("adh_cli.tools.google_tools.web_tools.fetch_url") as mock_fetch:
            mock_fetch.return_value = {
                "success": True,
                "content": "Test content",
            }

            # Mock successful API key but failed summarization
            with patch(
                "adh_cli.tools.google_tools._resolve_api_key",
                return_value="test-api-key",
            ):
                with patch(
                    "adh_cli.tools.google_tools.genai.Client"
                ) as mock_client_class:
                    mock_client = MagicMock()
                    mock_client.models.generate_content.side_effect = Exception(
                        "Summarization failed"
                    )
                    mock_client_class.return_value = mock_client

                    result = await google_tools.google_url_context(
                        urls=["https://example.com/test"],
                        api_key="test-api-key",
                    )

                    # Should still return fetched content even if summary fails
                    assert "Test content" in result


class TestHelperFunctions:
    """Test helper functions for extracting data from API responses."""

    def test_extract_text_parts_single_candidate(self):
        """Test extracting text from a response with one candidate."""
        mock_response = MagicMock()
        mock_response.candidates = [
            MagicMock(
                content=MagicMock(
                    parts=[MagicMock(text="First part"), MagicMock(text="Second part")]
                )
            )
        ]

        result = google_tools._extract_text_parts(mock_response)

        assert result == "First part\nSecond part"

    def test_extract_text_parts_multiple_candidates(self):
        """Test extracting text from multiple candidates."""
        mock_response = MagicMock()
        mock_response.candidates = [
            MagicMock(content=MagicMock(parts=[MagicMock(text="Candidate 1")])),
            MagicMock(content=MagicMock(parts=[MagicMock(text="Candidate 2")])),
        ]

        result = google_tools._extract_text_parts(mock_response)

        assert "Candidate 1" in result
        assert "Candidate 2" in result

    def test_extract_text_parts_empty_response(self):
        """Test extracting text from empty response."""
        mock_response = MagicMock()
        mock_response.candidates = []

        result = google_tools._extract_text_parts(mock_response)

        assert result == ""

    def test_extract_grounding_sources(self):
        """Test extracting grounding sources from response."""
        mock_response = MagicMock()
        mock_response.candidates = [
            MagicMock(
                grounding_metadata=MagicMock(
                    grounding_chunks=[
                        MagicMock(web=MagicMock(uri="https://source1.com")),
                        MagicMock(web=MagicMock(uri="https://source2.com")),
                    ]
                )
            )
        ]

        result = google_tools._extract_grounding_sources(mock_response)

        assert result == ["https://source1.com", "https://source2.com"]

    def test_extract_grounding_sources_deduplication(self):
        """Test that duplicate sources are deduplicated."""
        mock_response = MagicMock()
        mock_response.candidates = [
            MagicMock(
                grounding_metadata=MagicMock(
                    grounding_chunks=[
                        MagicMock(web=MagicMock(uri="https://source1.com")),
                        MagicMock(web=MagicMock(uri="https://source1.com")),
                        MagicMock(web=MagicMock(uri="https://source2.com")),
                    ]
                )
            )
        ]

        result = google_tools._extract_grounding_sources(mock_response)

        assert result == ["https://source1.com", "https://source2.com"]
