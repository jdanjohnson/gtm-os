"""Tests for WS8A: quality gate."""

from __future__ import annotations

import pytest

from gtm_os.engine.quality_gate import QUALITY_THRESHOLD, QualityScore, evaluate_content


def test_quality_score_defaults():
    qs = QualityScore()
    assert qs.overall == 0.0
    assert qs.passed is False
    assert qs.feedback == ""


def test_quality_score_pass():
    qs = QualityScore(overall=8.0, passed=True)
    assert qs.passed is True


def test_quality_score_fail():
    qs = QualityScore(overall=5.0, passed=False)
    assert qs.passed is False


def test_quality_threshold():
    assert QUALITY_THRESHOLD == 7.0


@pytest.mark.asyncio
async def test_evaluate_content_fails_gracefully():
    """When LLM call fails, quality gate auto-passes."""
    from gtm_os.config import LLMConfig

    config = LLMConfig(model="openai/gpt-4o", api_key="invalid-key")
    result = await evaluate_content("Some test content", config=config)
    # Should auto-pass on failure.
    assert result.passed is True
    assert "failed" in result.feedback.lower() or result.feedback == ""


@pytest.mark.asyncio
async def test_evaluate_content_with_brand():
    """Quality gate accepts brand/rules context without crashing."""
    from gtm_os.config import LLMConfig
    from gtm_os.types import BrandConfig, RulesConfig

    config = LLMConfig(model="openai/gpt-4o", api_key="invalid-key")
    brand = BrandConfig(body="We are a B2B SaaS company", tone={"style": "professional"})
    rules = RulesConfig(global_rules="Always use formal language")
    result = await evaluate_content(
        "Test content",
        brand=brand,
        rules=rules,
        config=config,
    )
    assert isinstance(result, QualityScore)
