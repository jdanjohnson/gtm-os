"""Shared input validation and sanitization for API routes."""

from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]+>")


def strip_html_tags(value: str) -> str:
    """Remove HTML tags and decode entities from a string."""
    cleaned = _TAG_RE.sub("", value)
    return html.unescape(cleaned)


def sanitize_text(value: str) -> str:
    """Sanitize a user-supplied text field: strip HTML and trim whitespace."""
    return strip_html_tags(value).strip()
