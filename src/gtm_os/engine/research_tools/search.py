"""Web search tool — Google search via Serper.dev API.

Inspired by PraisonAI's SerperDevTool. Provides structured search results
for market research, prospect discovery, and competitive analysis.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


class WebSearchTool:
    """Search Google via Serper.dev or Brave Search API."""

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout

    def search(
        self,
        query: str,
        num_results: int = 10,
        search_type: str = "search",
    ) -> dict[str, Any]:
        """Execute a web search.

        Args:
            query: Search query.
            num_results: Max results to return.
            search_type: "search", "news", "images", or "places".
        """
        serper_key = os.getenv("SERPER_API_KEY")
        if serper_key:
            return self._serper_search(query, serper_key, num_results, search_type)

        brave_key = os.getenv("BRAVE_SEARCH_API_KEY")
        if brave_key:
            return self._brave_search(query, brave_key, num_results)

        return {
            "ok": False,
            "query": query,
            "error": "No search API key configured. Set SERPER_API_KEY or BRAVE_SEARCH_API_KEY.",
        }

    def search_prospects(
        self,
        industry: str,
        title: str,
        location: str = "",
    ) -> dict[str, Any]:
        """Search for prospects matching ICP criteria on LinkedIn."""
        parts = [f'"{title}"', industry]
        if location:
            parts.append(location)
        parts.append("site:linkedin.com/in/")
        return self.search(" ".join(parts), num_results=10)

    def search_companies(
        self,
        industry: str,
        company_size: str = "",
        location: str = "",
    ) -> dict[str, Any]:
        """Search for companies matching ICP criteria."""
        parts = [industry, "companies"]
        if company_size:
            parts.append(company_size)
        if location:
            parts.append(location)
        return self.search(" ".join(parts), num_results=10)

    def _serper_search(
        self, query: str, api_key: str, num_results: int, search_type: str
    ) -> dict[str, Any]:
        endpoint = f"https://google.serper.dev/{search_type}"
        payload = json.dumps({"q": query, "num": num_results}).encode("utf-8")
        try:
            req = urllib.request.Request(
                endpoint,
                data=payload,
                headers={
                    "X-API-KEY": api_key,
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))

            results = [
                {
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                }
                for item in data.get("organic", [])[:num_results]
            ]
            return {
                "ok": True,
                "query": query,
                "results": results,
                "knowledge_graph": data.get("knowledgeGraph"),
                "people_also_ask": [
                    q.get("question", "") for q in data.get("peopleAlsoAsk", [])
                ],
            }
        except Exception as e:
            return {"ok": False, "query": query, "error": str(e)}

    def _brave_search(
        self, query: str, api_key: str, num_results: int
    ) -> dict[str, Any]:
        encoded = urllib.parse.quote(query)
        url = f"https://api.search.brave.com/res/v1/web/search?q={encoded}&count={num_results}"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                    "X-Subscription-Token": api_key,
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))

            results = [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", ""),
                }
                for item in data.get("web", {}).get("results", [])[:num_results]
            ]
            return {"ok": True, "query": query, "results": results}
        except Exception as e:
            return {"ok": False, "query": query, "error": str(e)}
