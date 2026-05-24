"""Tests for WS8F: adaptive plays."""

from __future__ import annotations

import tempfile
from pathlib import Path

from gtm_os.engine.adaptive_plays import (
    _extract_play_reference,
    _extract_segment,
    _slugify,
    list_play_variants,
)


def test_extract_play_reference():
    assert _extract_play_reference("play: kol-crm worked well") == "kol-crm"
    assert _extract_play_reference("The b2b-saas-email approach failed") == "b2b-saas-email"
    assert _extract_play_reference("No play mentioned here") is None


def test_extract_segment():
    assert _extract_segment("For enterprise buyers, this works") is not None
    assert _extract_segment("targeting startup founders") is not None
    assert _extract_segment("No segment here") is None


def test_slugify():
    assert _slugify("Enterprise Buyers") == "enterprise-buyers"
    assert _slugify("SMB Startup") == "smb-startup"
    assert _slugify("  spaces  ") == "spaces"


def test_list_play_variants_empty():
    with tempfile.TemporaryDirectory() as td:
        assert list_play_variants(Path(td)) == []


def test_list_play_variants():
    with tempfile.TemporaryDirectory() as td:
        plays_dir = Path(td)
        play_dir = plays_dir / "kol-crm"
        play_dir.mkdir()
        (play_dir / "PLAY.md").write_text("# KOL CRM Play\nContent here")

        variants = list_play_variants(plays_dir)
        assert len(variants) == 1
        assert variants[0]["id"] == "kol-crm"


def test_list_play_variants_with_frontmatter():
    with tempfile.TemporaryDirectory() as td:
        plays_dir = Path(td)
        play_dir = plays_dir / "test-play"
        play_dir.mkdir()
        (play_dir / "PLAY.md").write_text(
            "---\nid: test-play\nparent: original\nsegment: enterprise\n---\n\nContent"
        )

        variants = list_play_variants(plays_dir)
        assert len(variants) == 1
        assert variants[0].get("parent") == "original"
        assert variants[0].get("segment") == "enterprise"
