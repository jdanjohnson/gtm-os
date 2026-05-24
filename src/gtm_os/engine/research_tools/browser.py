"""Browser tool — fetch web pages and extract readable text.

Inspired by PraisonAI's browser agent. Provides lightweight HTTP-based
page fetching with HTML-to-text conversion for prospect research,
competitor analysis, and content extraction.
"""

from __future__ import annotations

import logging
import re
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class BrowserTool:
    """Fetch a URL and return its text content."""

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout

    def fetch(self, url: str) -> dict[str, Any]:
        """Fetch a page and extract text content."""
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "identity",
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                html = response.read().decode("utf-8", errors="replace")
                return {
                    "ok": True,
                    "url": url,
                    "status": response.status,
                    "title": _extract_title(html),
                    "text": _html_to_text(html)[:8000],
                }
        except urllib.error.HTTPError as e:
            return {"ok": False, "url": url, "error": f"HTTP {e.code}: {e.reason}"}
        except urllib.error.URLError as e:
            return {"ok": False, "url": url, "error": f"Connection error: {e.reason}"}
        except Exception as e:
            return {"ok": False, "url": url, "error": str(e)}


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _html_to_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    for entity, char in [
        ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
        ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " "),
    ]:
        text = text.replace(entity, char)
    text = re.sub(r"\s+", " ", text).strip()
    return text
