"""Tests for WS8B: human feedback learning."""

from __future__ import annotations

from gtm_os.engine.feedback import Correction, diff_content


def test_diff_identical():
    assert diff_content("Hello world", "Hello world") == []


def test_diff_empty():
    assert diff_content("", "") == []
    assert diff_content("Hello", "") == []
    assert diff_content("", "Hello") == []


def test_diff_added_line():
    original = "Line 1"
    approved = "Line 1\nLine 2"
    corrections = diff_content(original, approved)
    assert len(corrections) >= 1
    assert any(c.category == "added_content" for c in corrections)


def test_diff_removed_line():
    original = "Line 1\nLine 2"
    approved = "Line 1"
    corrections = diff_content(original, approved)
    assert len(corrections) >= 1
    assert any(c.category == "removed_content" for c in corrections)


def test_diff_replaced_line():
    original = "Dear sir or madam,"
    approved = "Hey there,"
    corrections = diff_content(original, approved)
    assert len(corrections) >= 1
    # Should classify as tone_adjustment or word_preference.
    categories = [c.category for c in corrections]
    assert any(
        cat in ("tone_adjustment", "word_preference", "factual_correction", "structural_change")
        for cat in categories
    )


def test_diff_multiple_changes():
    original = "Line 1\nLine 2\nLine 3\nLine 4"
    approved = "Line 1\nModified Line 2\nLine 4\nLine 5"
    corrections = diff_content(original, approved)
    assert len(corrections) >= 1


def test_correction_dataclass():
    c = Correction(
        category="tone_adjustment",
        original="Dear sir",
        revised="Hey there",
        description="Casual tone",
    )
    assert c.category == "tone_adjustment"
    assert c.original == "Dear sir"
