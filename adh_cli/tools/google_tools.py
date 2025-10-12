"""Google-powered tool helpers backed by the Gemini API."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from google import genai
from google.genai import types

from adh_cli.config.models import ModelRegistry

from . import web_tools

LOGGER = logging.getLogger(__name__)

# Default model used when callers do not provide one explicitly.
_DEFAULT_MODEL = ModelRegistry.DEFAULT.api_id

# Limit the amount of source content returned to keep responses manageable.
_DEFAULT_MAX_CONTENT_CHARS = 100_000


def _resolve_api_key(explicit: Optional[str]) -> str:
    """Resolve the API key, preferring an explicit override."""

    api_key = explicit or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Google API key not configured. Set GOOGLE_API_KEY or GEMINI_API_KEY."
        )
    return api_key


def _build_generation_config(
    generation_config: Optional[Dict[str, Any]] = None,
) -> Optional[types.GenerateContentConfig]:
    """Convert a simple dict of generation params to the SDK config object."""

    if not generation_config:
        return None
    return types.GenerateContentConfig(**generation_config)


def _extract_text_parts(response) -> str:
    """Extract concatenated text parts from a generate_content response."""

    texts: List[str] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", []) or []:
            text = getattr(part, "text", None)
            if text:
                texts.append(text)
    return "\n".join(texts).strip()


def _extract_grounding_sources(response) -> List[str]:
    """Extract grounded source URLs from a generate_content response."""

    sources: List[str] = []
    seen: Set[str] = set()

    for candidate in getattr(response, "candidates", []) or []:
        grounding_metadata = getattr(candidate, "grounding_metadata", None)
        if not grounding_metadata:
            continue

        chunks = getattr(grounding_metadata, "grounding_chunks", None) or []
        for chunk in chunks:
            web_chunk = getattr(chunk, "web", None)
            if not web_chunk:
                continue

            uri = getattr(web_chunk, "uri", None)
            if uri and uri not in seen:
                seen.add(uri)
                sources.append(uri)

    return sources


async def google_search(
    query: Optional[str] = None,
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    generation_config: Optional[Dict[str, Any]] = None,
    max_results: int = 6,
) -> Dict[str, Any]:
    """Run a live Google search via Gemini and return a structured summary."""

    if not query or not str(query).strip():
        return {
            "success": False,
            "query": query,
            "error": "Query parameter is required for google_search.",
        }

    query_text = str(query)
    resolved_api_key = _resolve_api_key(api_key)
    model_id = model or _DEFAULT_MODEL

    # Build generation config with tools
    config_dict = generation_config.copy() if generation_config else {}
    config_dict["tools"] = [{"google_search": {}}]
    gen_config = _build_generation_config(config_dict)

    prompt = (
        "Use the google_search tool to look up the following query. "
        "Return the top results with concise markdown bullets including the page title, "
        "URL, and a one-sentence summary. Prioritize official and high-quality sources. "
        f"Limit the response to roughly {max_results} results.\n\n"
        f"Query: {query_text.strip()}"
    )

    def _call() -> Dict[str, Any]:
        client = genai.Client(api_key=resolved_api_key)

        response = client.models.generate_content(
            model=model_id,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=gen_config,
        )

        summary = _extract_text_parts(response)
        sources = _extract_grounding_sources(response)

        if not summary:
            return {
                "success": False,
                "query": query,
                "error": "No search results were returned.",
                "sources": sources,
            }

        return {
            "success": True,
            "query": query_text,
            "summary": summary,
            "sources": sources,
        }

    try:
        return await asyncio.to_thread(_call)
    except Exception as exc:  # noqa: BLE001
        # Provide detailed error information for debugging
        error_type = type(exc).__name__
        error_detail = str(exc)

        # Log full traceback for debugging while returning structured error to caller
        LOGGER.exception("google_search failed for query: %s", query)

        # Check for common error patterns
        if "API key" in error_detail or "INVALID_ARGUMENT" in error_detail:
            error_msg = f"API key error: {error_detail}"
        elif "tools" in error_detail.lower():
            error_msg = f"Tool configuration error: {error_detail}"
        else:
            error_msg = f"{error_type}: {error_detail}"

        return {
            "success": False,
            "query": query,
            "error": error_msg,
            "error_type": error_type,
        }


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    """Deduplicate iterable entries while preserving order."""
    return list(dict.fromkeys(values))


def _normalize_url_for_fetch(url: str) -> str:
    """Normalize URLs that require special handling before fetching."""

    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace(
            "/blob/", "/"
        )
    return url


async def _fetch_url_with_errors(
    original_url: str,
) -> Tuple[str, Dict[str, Any]]:
    """Fetch a URL, returning structured success/failure data."""

    normalized = _normalize_url_for_fetch(original_url)
    try:
        result = await web_tools.fetch_url(normalized)
    except ValueError as exc:
        return original_url, {
            "success": False,
            "error": str(exc),
            "normalized_url": normalized,
        }

    result.update({"normalized_url": normalized})
    return original_url, result


async def google_url_context(
    urls: Optional[List[str]] = None,
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    generation_config: Optional[Dict[str, Any]] = None,
    max_content_chars: int = _DEFAULT_MAX_CONTENT_CHARS,
) -> str:
    """Fetch URL contents and return a formatted block for grounding responses."""

    if not urls:
        return "❌ No URLs were provided."

    cleaned_urls = [url.strip() for url in urls if isinstance(url, str) and url.strip()]
    deduped_urls = _dedupe_preserve_order(cleaned_urls)

    if not deduped_urls:
        raise ValueError("No valid URLs were provided.")

    fetch_results = await asyncio.gather(
        *(_fetch_url_with_errors(url) for url in deduped_urls)
    )

    successes: List[Tuple[str, Dict[str, Any]]] = []
    errors: List[Tuple[str, str]] = []

    for original, result in fetch_results:
        if not result.get("success"):
            errors.append((original, result.get("error") or "Unknown error"))
            continue

        content = (result.get("content") or "").strip()
        if not content:
            errors.append((original, "No readable content returned."))
            continue

        truncated = content[:max_content_chars]
        if len(content) > max_content_chars:
            truncated = f"{truncated}\n... [content truncated]"

        enriched = dict(result)
        enriched["content"] = truncated
        successes.append((original, enriched))

    if not successes:
        if errors:
            error_summary = "; ".join(f"{url} ({message})" for url, message in errors)
            return f"❌ Error fetching URLs: {error_summary}"
        return "❌ No readable content returned from provided URLs."

    sections: List[str] = []
    for original, result in successes:
        normalized_url = result.get("normalized_url", original)
        content = result.get("content", "")
        sections.append(
            "\n".join(
                [
                    f"Source URL: {original}",
                    f"Fetched URL: {normalized_url}",
                    "---",
                    content,
                    "---",
                ]
            )
        )

    error_block = ""
    if errors:
        error_lines = "\n".join(f"- {url}: {message}" for url, message in errors)
        error_block = f"\nSome URLs could not be fetched:\n{error_lines}"

    result_block = "\n\n".join(sections)

    # Optionally summarize the fetched content using Gemini when an API key is available.
    summary: Optional[str] = None
    try:
        resolved_api_key = _resolve_api_key(api_key)
        model_id = model or _DEFAULT_MODEL
        gen_config = _build_generation_config(generation_config)

        summary_prompt = (
            "Summarize the key insights from the fetched sources below. "
            "Focus on factual details and keep the summary concise. "
            "After the summary, list the cited source URLs.\n\n"
            f"{result_block}"
        )

        def _summarize() -> str:
            client = genai.Client(api_key=resolved_api_key)
            response = client.models.generate_content(
                model=model_id,
                contents=[
                    types.Content(role="user", parts=[types.Part(text=summary_prompt)])
                ],
                config=gen_config,
            )
            return _extract_text_parts(response)

        summary = await asyncio.to_thread(_summarize)
    except RuntimeError:
        # No API key available; skip summarization.
        summary = None
    except Exception:
        # Best effort: ignore summarization errors but keep fetched content.
        LOGGER.exception("Optional summarization in google_url_context failed")
        summary = None

    if summary:
        return f"{summary}\n\nSources:\n{result_block}{error_block}"

    return f"{result_block}{error_block}"


__all__ = [
    "google_search",
    "google_url_context",
]
