"""Tests for web tools."""

import base64
import pytest
from unittest.mock import Mock, patch, MagicMock
from urllib.error import URLError, HTTPError

from adh_cli.tools.web_tools import _validate_http_url, _fetch_sync, fetch_url


class TestValidateHttpUrl:
    """Test URL validation."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://example.com",
            "http://example.com/path",
            "http://example.com:8080/path?query=1",
            "https://example.com",
            "https://example.com/path",
            "https://example.com:443/path?query=1",
        ],
    )
    def test_valid_urls(self, url):
        """Test that valid HTTP/HTTPS URLs pass validation."""
        _validate_http_url(url)  # Should not raise

    @pytest.mark.parametrize(
        "url", ["ftp://example.com", "file:///etc/passwd", "example.com"]
    )
    def test_invalid_schemes(self, url):
        """Test that URLs with invalid schemes are rejected."""
        with pytest.raises(ValueError, match="Only http/https URLs are allowed"):
            _validate_http_url(url)

    @pytest.mark.parametrize("url", ["http://", "http:///path"])
    def test_missing_host(self, url):
        """Test that URLs without a host are rejected."""
        with pytest.raises(ValueError, match="URL must include a host"):
            _validate_http_url(url)


class TestFetchSync:
    """Test synchronous fetch function."""

    def test_fetch_success(self):
        """Test successful fetch with text content."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = b"Hello, World!"
        mock_response.geturl.return_value = "http://example.com"
        mock_response.status = 200

        mock_info = Mock()
        mock_info.get_content_type.return_value = "text/html"
        mock_info.items.return_value = [("Content-Type", "text/html")]
        mock_response.info.return_value = mock_info

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = _fetch_sync("http://example.com", timeout=10, max_bytes=1000)

        assert result["final_url"] == "http://example.com"
        assert result["status_code"] == 200
        assert result["content_bytes"] == b"Hello, World!"
        assert result["truncated"] is False
        assert result["content_type"] == "text/html"

    def test_fetch_with_custom_headers(self):
        """Test fetch with custom headers."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = b"Response"
        mock_response.geturl.return_value = "http://example.com"
        mock_response.status = 200

        mock_info = Mock()
        mock_info.get_content_type.return_value = "text/plain"
        mock_info.items.return_value = []
        mock_response.info.return_value = mock_info

        with patch(
            "urllib.request.urlopen", return_value=mock_response
        ) as mock_urlopen:
            custom_headers = {
                "User-Agent": "CustomAgent/1.0",
                "Authorization": "Bearer token123",
            }
            _fetch_sync(
                "http://example.com", timeout=10, max_bytes=1000, headers=custom_headers
            )

            # Verify request was created with custom headers
            request = mock_urlopen.call_args[0][0]
            assert request.get_header("User-agent") == "CustomAgent/1.0"
            assert request.get_header("Authorization") == "Bearer token123"

    def test_fetch_default_user_agent(self):
        """Test that default User-Agent is added when not provided."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = b"Response"
        mock_response.geturl.return_value = "http://example.com"
        mock_response.status = 200

        mock_info = Mock()
        mock_info.get_content_type.return_value = "text/plain"
        mock_info.items.return_value = []
        mock_response.info.return_value = mock_info

        with patch(
            "urllib.request.urlopen", return_value=mock_response
        ) as mock_urlopen:
            _fetch_sync("http://example.com", timeout=10, max_bytes=1000)

            # Verify default User-Agent was added
            request = mock_urlopen.call_args[0][0]
            user_agent = request.get_header("User-agent")
            assert "adh-cli" in user_agent
            assert "github.com" in user_agent

    def test_fetch_truncated(self):
        """Test that content is truncated when exceeding max_bytes."""
        # Return more data than max_bytes
        large_data = b"x" * 1001
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = large_data
        mock_response.geturl.return_value = "http://example.com"
        mock_response.status = 200

        mock_info = Mock()
        mock_info.get_content_type.return_value = "text/plain"
        mock_info.items.return_value = []
        mock_response.info.return_value = mock_info

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = _fetch_sync("http://example.com", timeout=10, max_bytes=100)

        assert result["truncated"] is True
        assert len(result["content_bytes"]) == 100
        assert result["content_bytes"] == b"x" * 100

    def test_fetch_not_truncated(self):
        """Test that content is not truncated when within max_bytes."""
        data = b"Small response"
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = data
        mock_response.geturl.return_value = "http://example.com"
        mock_response.status = 200

        mock_info = Mock()
        mock_info.get_content_type.return_value = "text/plain"
        mock_info.items.return_value = []
        mock_response.info.return_value = mock_info

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = _fetch_sync("http://example.com", timeout=10, max_bytes=1000)

        assert result["truncated"] is False
        assert result["content_bytes"] == data


class TestFetchUrl:
    """Test async fetch_url function."""

    @pytest.mark.asyncio
    async def test_fetch_url_success_text(self):
        """Test successful async fetch with text content."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = b"Hello, World!"
        mock_response.geturl.return_value = "http://example.com"
        mock_response.status = 200

        mock_info = Mock()
        mock_info.get_content_type.return_value = "text/html"
        mock_info.items.return_value = [("Content-Type", "text/html")]
        mock_response.info.return_value = mock_info

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = await fetch_url("http://example.com")

        assert result["success"] is True
        assert result["url"] == "http://example.com"
        assert result["final_url"] == "http://example.com"
        assert result["status_code"] == 200
        assert result["content"] == "Hello, World!"
        assert result["content_base64"] is None
        assert result["truncated"] is False
        assert result["content_length"] == 13

    @pytest.mark.asyncio
    async def test_fetch_url_success_binary(self):
        """Test successful async fetch with binary content (base64)."""
        binary_data = b"\x89PNG\r\n\x1a\n"
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = binary_data
        mock_response.geturl.return_value = "http://example.com/image.png"
        mock_response.status = 200

        mock_info = Mock()
        mock_info.get_content_type.return_value = "image/png"
        mock_info.items.return_value = [("Content-Type", "image/png")]
        mock_response.info.return_value = mock_info

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = await fetch_url("http://example.com/image.png", as_text=False)

        assert result["success"] is True
        assert result["content"] is None
        assert result["content_base64"] == base64.b64encode(binary_data).decode("ascii")
        assert result["content_length"] == len(binary_data)

    @pytest.mark.asyncio
    async def test_fetch_url_encoding_from_header(self):
        """Test encoding detection from Content-Type header."""
        utf8_text = "Héllo, Wörld!".encode("utf-8")
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = utf8_text
        mock_response.geturl.return_value = "http://example.com"
        mock_response.status = 200

        mock_info = Mock()
        mock_info.get_content_type.return_value = "text/html"
        mock_info.items.return_value = [("Content-Type", "text/html; charset=utf-8")]
        mock_response.info.return_value = mock_info

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = await fetch_url("http://example.com")

        assert result["success"] is True
        assert result["content"] == "Héllo, Wörld!"

    @pytest.mark.asyncio
    async def test_fetch_url_custom_encoding(self):
        """Test custom encoding parameter."""
        latin1_text = "Héllo, Wörld!".encode("latin-1")
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = latin1_text
        mock_response.geturl.return_value = "http://example.com"
        mock_response.status = 200

        mock_info = Mock()
        mock_info.get_content_type.return_value = "text/html"
        mock_info.items.return_value = [("Content-Type", "text/html")]
        mock_response.info.return_value = mock_info

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = await fetch_url("http://example.com", encoding="latin-1")

        assert result["success"] is True
        assert result["content"] == "Héllo, Wörld!"

    @pytest.mark.asyncio
    async def test_fetch_url_truncated(self):
        """Test truncation is reported in async result."""
        large_data = b"x" * 1001
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = large_data
        mock_response.geturl.return_value = "http://example.com"
        mock_response.status = 200

        mock_info = Mock()
        mock_info.get_content_type.return_value = "text/plain"
        mock_info.items.return_value = []
        mock_response.info.return_value = mock_info

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = await fetch_url("http://example.com", max_bytes=100)

        assert result["success"] is True
        assert result["truncated"] is True
        assert result["content_length"] == 100

    @pytest.mark.asyncio
    async def test_fetch_url_custom_headers(self):
        """Test async fetch with custom headers."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = b"Response"
        mock_response.geturl.return_value = "http://example.com"
        mock_response.status = 200

        mock_info = Mock()
        mock_info.get_content_type.return_value = "text/plain"
        mock_info.items.return_value = []
        mock_response.info.return_value = mock_info

        with patch("urllib.request.urlopen", return_value=mock_response):
            custom_headers = {"Authorization": "Bearer token123"}
            result = await fetch_url("http://example.com", headers=custom_headers)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_fetch_url_invalid_url(self):
        """Test that invalid URL raises error before fetching."""
        with pytest.raises(ValueError, match="Only http/https URLs are allowed"):
            await fetch_url("ftp://example.com")

    @pytest.mark.asyncio
    async def test_fetch_url_timeout_error(self):
        """Test timeout error handling."""
        with patch(
            "urllib.request.urlopen", side_effect=URLError("Connection timed out")
        ):
            result = await fetch_url("http://example.com")

        assert result["success"] is False
        assert result["url"] == "http://example.com"
        assert "error" in result
        assert "timed out" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_fetch_url_http_error(self):
        """Test HTTP error handling (e.g., 404)."""
        http_error = HTTPError("http://example.com", 404, "Not Found", {}, None)
        with patch("urllib.request.urlopen", side_effect=http_error):
            result = await fetch_url("http://example.com")

        assert result["success"] is False
        assert result["url"] == "http://example.com"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_fetch_url_connection_error(self):
        """Test connection error handling."""
        with patch(
            "urllib.request.urlopen",
            side_effect=URLError("Connection refused"),
        ):
            result = await fetch_url("http://example.com")

        assert result["success"] is False
        assert result["url"] == "http://example.com"
        assert "error" in result
        assert "refused" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_fetch_url_decoding_error_fallback(self):
        """Test that decoding errors use 'replace' strategy."""
        # Invalid UTF-8 sequence
        invalid_utf8 = b"\xff\xfe Invalid UTF-8"
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = invalid_utf8
        mock_response.geturl.return_value = "http://example.com"
        mock_response.status = 200

        mock_info = Mock()
        mock_info.get_content_type.return_value = "text/plain"
        mock_info.items.return_value = [("Content-Type", "text/plain; charset=utf-8")]
        mock_response.info.return_value = mock_info

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = await fetch_url("http://example.com")

        # Should succeed with replacement characters
        assert result["success"] is True
        assert "error" not in result
        # Verify replacement character is used for invalid bytes
        assert result["content"] == "\ufffd\ufffd Invalid UTF-8"
