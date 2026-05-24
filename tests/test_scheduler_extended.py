"""Tests for scheduler — backoff, escalation, cost tracking."""

from gtm_os.engine.scheduler import (
    BACKOFF_DELAYS,
    _backoff_delay,
    _estimate_cost,
    _next_run_at,
)


def test_backoff_delay_first():
    assert _backoff_delay(0) == BACKOFF_DELAYS[0]  # 60s


def test_backoff_delay_progressive():
    assert _backoff_delay(1) == 120
    assert _backoff_delay(2) == 240
    assert _backoff_delay(3) == 480


def test_backoff_delay_ceiling():
    assert _backoff_delay(100) == 1800  # max


def test_estimate_cost_openai():
    cost = _estimate_cost(1000, "openai/gpt-4o")
    assert abs(cost - 0.005) < 0.0001


def test_estimate_cost_mini():
    cost = _estimate_cost(1000, "openai/gpt-4o-mini")
    assert abs(cost - 0.00015) < 0.00001


def test_estimate_cost_anthropic():
    cost = _estimate_cost(1000, "anthropic/claude-3-5-sonnet-20241022")
    assert abs(cost - 0.003) < 0.0001


def test_estimate_cost_ollama_free():
    cost = _estimate_cost(10000, "ollama/llama3.1")
    assert cost == 0.0


def test_estimate_cost_unknown_model():
    cost = _estimate_cost(1000, "some/unknown-model")
    assert cost > 0  # fallback estimate


def test_next_run_at_interval():
    result = _next_run_at(cron_expr=None, interval_seconds=300)
    assert "T" in result  # ISO format


def test_next_run_at_cron():
    result = _next_run_at(cron_expr="0 9 * * *", interval_seconds=None)
    assert "T" in result


def test_next_run_at_default_interval():
    result = _next_run_at(cron_expr=None, interval_seconds=None)
    assert "T" in result  # defaults to 3600s
