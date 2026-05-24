"""Simulation / dry-run mode — predict experiment outcomes from historical data.

Implements WS8E:
- Run design + build normally (LLM generates content)
- Execute phase mocked — records what WOULD be sent
- Measure phase uses historical data to PREDICT outcomes
- Output: predicted metrics with confidence intervals
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from .store import Store

logger = logging.getLogger(__name__)


@dataclass
class PredictedMetric:
    name: str
    predicted_value: float
    confidence_interval_low: float
    confidence_interval_high: float
    based_on_experiments: int
    confidence_pct: float  # 0-100


@dataclass
class SimulationResult:
    experiment_id: str
    predictions: list[PredictedMetric] = field(default_factory=list)
    estimated_token_cost: int = 0
    estimated_dollar_cost: float = 0.0
    similar_experiments_found: int = 0
    message: str = ""


def predict_outcomes(
    store: Store,
    experiment_id: str,
) -> SimulationResult:
    """Predict outcomes based on similar past experiments."""
    exp = store.get_experiment(experiment_id)
    if not exp:
        return SimulationResult(
            experiment_id=experiment_id,
            message="Experiment not found.",
        )

    # Find similar experiments (same play_ids, similar channel).
    all_exps = store.list_experiments(limit=200)
    similar = []
    for other in all_exps:
        if other.id == exp.id:
            continue
        if other.phase not in ("complete", "learn", "measure"):
            continue
        # Similarity: shared play_ids or same channel.
        shared_plays = set(exp.play_ids) & set(other.play_ids)
        same_channel = exp.config.get("channel") == other.config.get("channel")
        if shared_plays or same_channel:
            similar.append(other)

    result = SimulationResult(
        experiment_id=experiment_id,
        similar_experiments_found=len(similar),
    )

    if not similar:
        result.message = (
            "No comparable experiments found. Running this would be exploratory. "
            "Predictions cannot be made without historical data."
        )
        return result

    # Gather metrics from similar experiments.
    metric_values: dict[str, list[float]] = {}
    total_tokens: list[int] = []

    for sim_exp in similar:
        metrics = store.list_metrics(sim_exp.id, limit=100)
        for m in metrics:
            metric_values.setdefault(m["metric_name"], []).append(float(m["metric_value"]))
        if sim_exp.tokens_used > 0:
            total_tokens.append(sim_exp.tokens_used)

    # Build predictions.
    for metric_name, values in metric_values.items():
        if not values:
            continue
        mean = sum(values) / len(values)
        if len(values) > 1:
            variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
            std_dev = math.sqrt(variance)
        else:
            std_dev = mean * 0.3  # Default 30% uncertainty for single data point.

        # 80% confidence interval.
        z = 1.28  # z-score for 80% CI
        ci_low = max(0, mean - z * std_dev)
        ci_high = mean + z * std_dev

        result.predictions.append(PredictedMetric(
            name=metric_name,
            predicted_value=round(mean, 4),
            confidence_interval_low=round(ci_low, 4),
            confidence_interval_high=round(ci_high, 4),
            based_on_experiments=len(values),
            confidence_pct=min(95, 50 + len(values) * 5),
        ))

    # Token cost estimate.
    if total_tokens:
        avg_tokens = sum(total_tokens) / len(total_tokens)
        result.estimated_token_cost = int(avg_tokens)
        result.estimated_dollar_cost = round(avg_tokens / 1000 * 0.003, 2)  # Rough estimate.

    n = len(similar)
    result.message = (
        f"Based on {n} similar experiment{'s' if n != 1 else ''}, "
        f"predicted {len(result.predictions)} metric{'s' if len(result.predictions) != 1 else ''}. "
        f"Estimated cost: ~{result.estimated_token_cost:,} tokens (~${result.estimated_dollar_cost:.2f})."
    )

    return result
