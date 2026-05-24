"""Website scraper — extract structured data from web pages.

Inspired by PraisonAI's ScrapeWebsiteTool / SeleniumScrapingTool.
Extracts emails, phone numbers, social links, headings, and meta data
for prospect research and company profiling.
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


class WebScraperTool:
    """Scrape structured prospect-relevant data from a URL."""

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout

    def scrape(self, url: str) -> dict[str, Any]:
        """Scrape a URL and return structured data."""
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "text/html,*/*;q=0.8",
                    "Accept-Encoding": "identity",
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                html = response.read().decode("utf-8", errors="replace")

            return {
                "ok": True,
                "url": url,
                "title": _extract_title(html),
                "meta_description": _extract_meta(html, "description"),
                "headings": _extract_headings(html),
                "emails": _extract_emails(html),
                "phone_numbers": _extract_phones(html),
                "social_links": _extract_social_links(html),
                "key_pages": _extract_key_pages(html),
                "text_snippet": _html_to_text(html)[:3000],
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


def _extract_meta(html: str, name: str) -> str:
    for pattern in [
        rf'<meta\s+(?:name|property)=["\'](?:og:)?{name}["\']\s+content=["\'](.*?)["\']',
        rf'<meta\s+content=["\'](.*?)["\']\s+(?:name|property)=["\'](?:og:)?{name}["\']',
    ]:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _extract_headings(html: str) -> list[str]:
    raw = re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, re.IGNORECASE | re.DOTALL)
    return [re.sub(r"<[^>]+>", "", h).strip() for h in raw if h.strip()][:15]


def _extract_emails(html: str) -> list[str]:
    emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", html)
    seen: set[str] = set()
    unique: list[str] = []
    for e in emails:
        lower = e.lower()
        if lower not in seen:
            seen.add(lower)
            unique.append(e)
    return unique[:10]


def _extract_phones(html: str) -> list[str]:
    phones = re.findall(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", html)
    return list(set(phones))[:5]


def _extract_social_links(html: str) -> dict[str, str]:
    social: dict[str, str] = {}
    patterns = {
        "linkedin": r'href=["\'](https?://(?:www\.)?linkedin\.com/[^"\']+)["\']',
        "twitter": r'href=["\'](https?://(?:www\.)?(?:twitter|x)\.com/[^"\']+)["\']',
        "facebook": r'href=["\'](https?://(?:www\.)?facebook\.com/[^"\']+)["\']',
        "youtube": r'href=["\'](https?://(?:www\.)?youtube\.com/[^"\']+)["\']',
        "github": r'href=["\'](https?://(?:www\.)?github\.com/[^"\']+)["\']',
    }
    for platform, pattern in patterns.items():
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            social[platform] = match.group(1)
    return social


def _extract_key_pages(html: str) -> list[dict[str, str]]:
    """Extract links to key business pages (about, team, pricing, etc.)."""
    keywords = {"about", "team", "contact", "pricing", "product", "service", "careers"}
    pages: list[dict[str, str]] = []
    for match in re.finditer(
        r'<a\s+[^>]*href=["\'](.*?)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL
    ):
        href = match.group(1).strip()
        text = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        if any(k in href.lower() or k in text.lower() for k in keywords):
            pages.append({"href": href, "text": text[:80]})
    return pages[:10]


def _html_to_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    for entity, char in [
        ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
        ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " "),
    ]:
        text = text.replace(entity, char)
    return re.sub(r"\s+", " ", text).strip()
