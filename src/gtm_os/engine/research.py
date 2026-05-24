"""Research skill — web search + content extraction for the GTM-OS agent.

Gives the agent the ability to search the web and read pages during experiment
execution. Used for:
- Finding prospects (founders, companies, leads)
- Researching companies and markets
- Learning how to configure tools
- Validating hypotheses with real data
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

from ..types import Tool

logger = logging.getLogger(__name__)

# DuckDuckGo HTML search — no API key required.
_DDG_URL = "https://html.duckduckgo.com/html/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Max content to extract per page (chars).
_MAX_PAGE_CONTENT = 8000
_TIMEOUT = 15


async def _web_search(query: str, num_results: int = 10) -> list[dict[str, str]]:
    """Search using DuckDuckGo HTML endpoint. Returns list of {title, url, snippet}."""
    results: list[dict[str, str]] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = await client.post(
                _DDG_URL,
                data={"q": query, "b": ""},
                headers=_HEADERS,
            )
            if resp.status_code != 200:
                return [{"error": f"Search returned {resp.status_code}"}]
            html = resp.text

        # Parse results from DDG HTML response.
        # Each result is in a <div class="result"> with <a class="result__a"> and <a class="result__snippet">.
        result_blocks = re.findall(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        )
        for url, title, snippet in result_blocks[:num_results]:
            # DDG wraps URLs in a redirect; extract the actual URL.
            actual_url = url
            ud_match = re.search(r"uddg=([^&]+)", url)
            if ud_match:
                from urllib.parse import unquote

                actual_url = unquote(ud_match.group(1))
            results.append(
                {
                    "title": re.sub(r"<[^>]+>", "", title).strip(),
                    "url": actual_url,
                    "snippet": re.sub(r"<[^>]+>", "", snippet).strip(),
                }
            )
    except Exception as exc:
        logger.warning("web_search failed: %s", exc)
        results = [{"error": f"Search failed: {exc}"}]
    return results


async def _web_read(url: str) -> dict[str, str]:
    """Extract text content from a URL. Returns {url, title, content}."""
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, follow_redirects=True, headers=_HEADERS
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {"url": url, "error": f"HTTP {resp.status_code}"}
            html = resp.text

        # Extract title.
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
        title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else ""

        # Strip scripts, styles, and HTML tags to get text.
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        # Truncate to avoid blowing context.
        if len(text) > _MAX_PAGE_CONTENT:
            text = text[:_MAX_PAGE_CONTENT] + "... [truncated]"

        return {"url": url, "title": title, "content": text}
    except Exception as exc:
        logger.warning("web_read failed for %s: %s", url, exc)
        return {"url": url, "error": f"Failed: {exc}"}


async def _web_search_and_read(query: str, num_results: int = 3) -> list[dict[str, Any]]:
    """Search + read the top N results. Convenience combo."""
    search_results = await _web_search(query, num_results=num_results)
    if not search_results or "error" in search_results[0]:
        return search_results

    # Read pages in parallel.
    async def _read_one(r: dict[str, str]) -> dict[str, Any]:
        page = await _web_read(r["url"])
        return {**r, "content": page.get("content", ""), "page_title": page.get("title", "")}

    tasks = [_read_one(r) for r in search_results if "url" in r]
    pages = await asyncio.gather(*tasks, return_exceptions=True)
    out: list[dict[str, Any]] = []
    for p in pages:
        if isinstance(p, Exception):
            out.append({"error": str(p)})
        else:
            out.append(p)
    return out


def build_research_tools() -> list[Tool]:
    """Tools for web research during experiment execution."""

    async def _search_tool(query: str, num_results: int = 10) -> Any:
        return await _web_search(query, num_results=int(num_results))

    async def _read_tool(url: str) -> Any:
        return await _web_read(url)

    async def _research_tool(query: str, num_results: int = 3) -> Any:
        return await _web_search_and_read(query, num_results=int(num_results))

    return [
        Tool(
            name="web_search",
            description=(
                "Search the web using DuckDuckGo. Returns titles, URLs, and snippets. "
                "Use for finding prospects, researching companies, learning about tools, "
                "validating market data. Phrase queries like a human, not a librarian."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query. Be specific. Use quotes for exact phrases.",
                    },
                    "num_results": {
                        "type": "integer",
                        "default": 10,
                        "description": "Max results to return (1-20).",
                    },
                },
                "required": ["query"],
            },
            execute=_search_tool,
        ),
        Tool(
            name="web_read",
            description=(
                "Read and extract text content from a URL. Use after web_search to get "
                "full page content. Good for reading docs, articles, company pages, "
                "LinkedIn profiles (public), product pages."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full URL to read (include https://).",
                    },
                },
                "required": ["url"],
            },
            execute=_read_tool,
        ),
        Tool(
            name="research",
            description=(
                "Search the web AND read the top results in one call. Combines web_search + "
                "web_read for efficiency. Use when you want both search results and their "
                "content. Good for research tasks: 'find founders doing X', 'how does Y work', "
                "'what tools exist for Z'."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query.",
                    },
                    "num_results": {
                        "type": "integer",
                        "default": 3,
                        "description": "How many pages to search + read (1-5). Higher = slower.",
                    },
                },
                "required": ["query"],
            },
            execute=_research_tool,
        ),
    ]
