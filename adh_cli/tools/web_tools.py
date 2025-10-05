"""Web tools for fetching content over HTTP/HTTPS without extra deps.

Designed to be safe-by-default and compatible with our async tool model.
Uses the Python standard library and runs blocking I/O in a thread.
"""

from __future__ import annotations

import base64
import urllib.request
import urllib.parse
from typing import Dict, Optional, Any
import asyncio


def _validate_http_url(url: str) -> None:
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in {"http", "https"}:
        raise ValueError("Only http/https URLs are allowed")
    if not parts.netloc:
        raise ValueError("URL must include a host")


def _fetch_sync(
    url: str,
    timeout: int,
    max_bytes: int,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    req = urllib.request.Request(url)
    ua = headers.get("User-Agent") if headers else None
    req.add_header(
        "User-Agent", ua or "adh-cli/0.1 (+https://github.com/allenhutchison/adh-cli)"
    )
    if headers:
        for k, v in headers.items():
            if k.lower() == "user-agent":
                continue
            req.add_header(k, v)

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        info = resp.info()
        content_type = (
            info.get_content_type()
            if hasattr(info, "get_content_type")
            else info.get("Content-Type", "")
        )

        # Read up to max_bytes + 1 so we can flag truncation
        data = resp.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        if truncated:
            data = data[:max_bytes]

        return {
            "final_url": resp.geturl(),
            "status_code": getattr(resp, "status", 200),
            "headers": {k: v for k, v in info.items()},
            "content_bytes": data,
            "truncated": truncated,
            "content_type": content_type,
        }


async def fetch_url(
    url: str,
    *,
    timeout: int = 20,
    max_bytes: int = 500_000,
    as_text: bool = True,
    encoding: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Fetch content from a URL (GET), safely and with size limits.

    Args:
        url: HTTP/HTTPS URL to fetch.
        timeout: Request timeout in seconds (default 20).
        max_bytes: Maximum bytes to read (default 500k).
        as_text: If True, decode bytes to text. Otherwise return base64.
        encoding: Optional text encoding. If None, try from response -> utf-8.
        headers: Optional request headers.

    Returns:
        Dict with response metadata and content. Keys:
        - success (bool), url, final_url, status_code, content_type,
          truncated (bool), content (str) or content_base64 (str), content_length (int).
    """
    _validate_http_url(url)

    try:
        result = await asyncio.to_thread(_fetch_sync, url, timeout, max_bytes, headers)
        data = result.pop("content_bytes")

        content_length = len(data)
        content_type = result.get("content_type") or "application/octet-stream"

        text_out: Optional[str] = None
        b64_out: Optional[str] = None

        if as_text:
            # Try encoding -> header charset, then provided encoding, fallback utf-8
            hdrs = result.get("headers", {})
            charset = None
            ctype = hdrs.get("Content-Type", "")
            if "charset=" in ctype:
                charset = ctype.split("charset=", 1)[1].split(";")[0].strip()
            use_encoding = encoding or charset or "utf-8"
            text_out = data.decode(use_encoding, errors="replace")
        else:
            b64_out = base64.b64encode(data).decode("ascii")

        return {
            "success": True,
            "url": url,
            **result,
            "content_type": content_type,
            "content_length": content_length,
            "content": text_out if as_text else None,
            "content_base64": b64_out if not as_text else None,
        }
    except Exception as e:
        return {
            "success": False,
            "url": url,
            "error": str(e),
        }
