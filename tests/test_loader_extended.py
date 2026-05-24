"""Tests for WS3E: play frontmatter parsing + tool declarations."""

from __future__ import annotations

import tempfile
from pathlib import Path

from gtm_os.engine.loader import get_play_tools_needed, parse_play_frontmatter


def test_parse_frontmatter_empty():
    assert parse_play_frontmatter("") == {}
    assert parse_play_frontmatter("No frontmatter here") == {}


def test_parse_frontmatter_basic():
    content = "---\nid: test-play\nchannel: email\n---\n\n# Play content"
    fm = parse_play_frontmatter(content)
    assert fm["id"] == "test-play"
    assert fm["channel"] == "email"


def test_parse_frontmatter_with_tools():
    content = """---
id: kol-crm
channel: linkedin
tools_needed:
  - use_case: LINKEDIN_SEND_MESSAGE
  - use_case: GMAIL_SEND_EMAIL
---

# KOL CRM Play
"""
    fm = parse_play_frontmatter(content)
    assert "tools_needed" in fm
    assert len(fm["tools_needed"]) == 2


def test_parse_frontmatter_incomplete():
    content = "---\nid: broken\n"
    fm = parse_play_frontmatter(content)
    assert fm == {}


def test_get_play_tools_needed_empty():
    with tempfile.TemporaryDirectory() as td:
        result = get_play_tools_needed(td)
        assert result == {}


def test_get_play_tools_needed():
    with tempfile.TemporaryDirectory() as td:
        plays_dir = Path(td) / "plays"
        plays_dir.mkdir()
        play_dir = plays_dir / "kol-crm"
        play_dir.mkdir()
        (play_dir / "PLAY.md").write_text(
            "---\nid: kol-crm\ntools_needed:\n  - use_case: LINKEDIN_SEND_MESSAGE\n---\n\nContent"
        )
        result = get_play_tools_needed(td)
        assert "kol-crm" in result
        assert "LINKEDIN_SEND_MESSAGE" in result["kol-crm"]


def test_get_play_tools_no_frontmatter():
    with tempfile.TemporaryDirectory() as td:
        plays_dir = Path(td) / "plays"
        plays_dir.mkdir()
        play_dir = plays_dir / "basic-play"
        play_dir.mkdir()
        (play_dir / "PLAY.md").write_text("# Basic Play\nNo frontmatter")
        result = get_play_tools_needed(td)
        assert "basic-play" not in result


def test_get_play_tools_string_format():
    with tempfile.TemporaryDirectory() as td:
        plays_dir = Path(td) / "plays"
        plays_dir.mkdir()
        play_dir = plays_dir / "simple"
        play_dir.mkdir()
        (play_dir / "PLAY.md").write_text(
            "---\ntools_needed:\n  - GMAIL_SEND_EMAIL\n  - SLACK_SEND_MESSAGE\n---\n\nContent"
        )
        result = get_play_tools_needed(td)
        assert "simple" in result
        assert len(result["simple"]) == 2
