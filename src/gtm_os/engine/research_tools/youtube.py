"""YouTube search tool — find prospect content for personalization.

Inspired by PraisonAI's YoutubeChannelSearchTool. Searches YouTube
for channels, videos, and content related to prospects for outreach
personalization and market research.

Uses the YouTube Data API v3 when YOUTUBE_API_KEY is set, otherwise
falls back to web search via the WebSearchTool.
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

_YT_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeSearchTool:
    """Search YouTube for prospect-relevant content."""

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout

    def search_channels(
        self,
        query: str,
        max_results: int = 5,
    ) -> dict[str, Any]:
        """Search for YouTube channels matching a query."""
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            return self._fallback_search(query, "channel")
        return self._api_search(api_key, query, "channel", max_results)

    def search_videos(
        self,
        query: str,
        max_results: int = 10,
    ) -> dict[str, Any]:
        """Search for YouTube videos matching a query."""
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            return self._fallback_search(query, "video")
        return self._api_search(api_key, query, "video", max_results)

    def get_channel_info(self, channel_id: str) -> dict[str, Any]:
        """Get details about a YouTube channel."""
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            return {
                "ok": False,
                "error": "YOUTUBE_API_KEY not configured.",
            }
        params = urllib.parse.urlencode({
            "part": "snippet,statistics",
            "id": channel_id,
            "key": api_key,
        })
        url = f"{_YT_API_BASE}/channels?{params}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            items = data.get("items", [])
            if not items:
                return {"ok": False, "error": "Channel not found"}
            ch = items[0]
            snippet = ch.get("snippet", {})
            stats = ch.get("statistics", {})
            return {
                "ok": True,
                "channel_id": channel_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", "")[:500],
                "subscriber_count": stats.get("subscriberCount", "0"),
                "video_count": stats.get("videoCount", "0"),
                "view_count": stats.get("viewCount", "0"),
                "custom_url": snippet.get("customUrl", ""),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_recent_videos(
        self,
        channel_id: str,
        max_results: int = 5,
    ) -> dict[str, Any]:
        """Get recent videos from a YouTube channel."""
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            return {"ok": False, "error": "YOUTUBE_API_KEY not configured."}
        params = urllib.parse.urlencode({
            "part": "snippet",
            "channelId": channel_id,
            "order": "date",
            "maxResults": max_results,
            "type": "video",
            "key": api_key,
        })
        url = f"{_YT_API_BASE}/search?{params}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            videos = []
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                vid_id = item.get("id", {}).get("videoId", "")
                videos.append({
                    "video_id": vid_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", "")[:300],
                    "published_at": snippet.get("publishedAt", ""),
                    "url": f"https://youtube.com/watch?v={vid_id}" if vid_id else "",
                })
            return {"ok": True, "channel_id": channel_id, "videos": videos}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_search(
        self, api_key: str, query: str, search_type: str, max_results: int
    ) -> dict[str, Any]:
        params = urllib.parse.urlencode({
            "part": "snippet",
            "q": query,
            "type": search_type,
            "maxResults": max_results,
            "key": api_key,
        })
        url = f"{_YT_API_BASE}/search?{params}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            results = []
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                item_id = item.get("id", {})
                if search_type == "channel":
                    results.append({
                        "channel_id": item_id.get("channelId", ""),
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", "")[:300],
                    })
                else:
                    vid_id = item_id.get("videoId", "")
                    results.append({
                        "video_id": vid_id,
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", "")[:300],
                        "published_at": snippet.get("publishedAt", ""),
                        "url": f"https://youtube.com/watch?v={vid_id}" if vid_id else "",
                    })
            return {"ok": True, "query": query, "type": search_type, "results": results}
        except Exception as e:
            return {"ok": False, "query": query, "error": str(e)}

    def _fallback_search(self, query: str, search_type: str) -> dict[str, Any]:
        """Fall back to web search when no YouTube API key is configured."""
        site_filter = "site:youtube.com"
        if search_type == "channel":
            site_filter = "site:youtube.com/@ OR site:youtube.com/c/"
        full_query = f"{query} {site_filter}"

        from .search import WebSearchTool

        ws = WebSearchTool(timeout=self.timeout)
        result = ws.search(full_query, num_results=5)
        if not result["ok"]:
            return {
                "ok": False,
                "query": query,
                "error": (
                    "YOUTUBE_API_KEY not configured and web search fallback failed. "
                    f"{result.get('error', '')}"
                ),
            }
        return {
            "ok": True,
            "query": query,
            "type": search_type,
            "source": "web_search_fallback",
            "results": result.get("results", []),
        }
