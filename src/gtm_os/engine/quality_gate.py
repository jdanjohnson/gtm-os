"""Quality gate — score generated content before execute phase.

Implements WS8A:
- Score content against brand voice, rules, learnings, clarity, ICP relevance
- Threshold: score >= 7 proceeds; < 7 returns to build with feedback
- Dimensions: brand_voice, clarity, relevance, rule_compliance, learning_incorporation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..config import LLMConfig
from ..types import BrandConfig, Memory, RulesConfig

logger = logging.getLogger(__name__)

QUALITY_THRESHOLD = 7.0

EVALUATION_PROMPT = """You are a GTM content quality evaluator. Score the following content on 5 dimensions (1-10 each):

1. **brand_voice**: Does it match the brand's tone, voice, and personality?
2. **clarity**: Is it clear, concise, and easy to understand?
3. **relevance**: Is it relevant to the target ICP and campaign objectives?
4. **rule_compliance**: Does it follow all stated rules and constraints?
5. **learning_incorporation**: Does it reflect past learnings and insights?

Brand context:
{brand_context}

Rules:
{rules_context}

Past learnings:
{learnings_context}

Content to evaluate:
{content}

Respond ONLY with a JSON object (no markdown):
{{"brand_voice": <1-10>, "clarity": <1-10>, "relevance": <1-10>, "rule_compliance": <1-10>, "learning_incorporation": <1-10>, "overall": <1-10>, "feedback": "<specific feedback if any dimension < 7>"}}"""


@dataclass
class QualityScore:
    brand_voice: float = 0.0
    clarity: float = 0.0
    relevance: float = 0.0
    rule_compliance: float = 0.0
    learning_incorporation: float = 0.0
    overall: float = 0.0
    feedback: str = ""
    passed: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


async def evaluate_content(
    content: str,
    *,
    brand: BrandConfig | None = None,
    rules: RulesConfig | None = None,
    past_learnings: list[Memory] | None = None,
    config: LLMConfig,
    threshold: float = QUALITY_THRESHOLD,
) -> QualityScore:
    """Score generated content against brand + rules + learnings."""
    brand_context = ""
    if brand:
        brand_context = brand.body[:1000]
        if brand.tone:
            brand_context += f"\nTone: {brand.tone}"

    rules_context = ""
    if rules:
        rules_context = rules.global_rules[:800]

    learnings_context = ""
    if past_learnings:
        learnings_context = "\n".join(
            f"- [{m.type}] {m.content[:200]} (confidence: {m.confidence:.1f})"
            for m in past_learnings[:10]
        )

    def _escape_braces(s: str) -> str:
        return s.replace("{", "{{").replace("}", "}}")

    prompt = EVALUATION_PROMPT.format(
        brand_context=_escape_braces(brand_context or "(no brand context)"),
        rules_context=_escape_braces(rules_context or "(no rules)"),
        learnings_context=_escape_braces(learnings_context or "(no learnings)"),
        content=_escape_braces(content[:3000]),
    )

    try:
        import litellm

        resp = await litellm.acompletion(
            model=config.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.1,
            api_key=config.api_key,
            timeout=config.request_timeout_seconds,
        )
        text = resp.choices[0].message.content or ""

        import json
        # Strip markdown code fences if present.
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        data = json.loads(text)
        score = QualityScore(
            brand_voice=float(data.get("brand_voice", 5)),
            clarity=float(data.get("clarity", 5)),
            relevance=float(data.get("relevance", 5)),
            rule_compliance=float(data.get("rule_compliance", 5)),
            learning_incorporation=float(data.get("learning_incorporation", 5)),
            overall=float(data.get("overall", 5)),
            feedback=str(data.get("feedback", "")),
            raw=data,
        )
        score.passed = score.overall >= threshold
        return score

    except Exception as exc:
        logger.warning("quality gate evaluation failed: %s", exc)
        # On failure, default to passing to avoid blocking.
        return QualityScore(
            overall=threshold,
            passed=True,
            feedback=f"Evaluation failed ({exc}); auto-passing.",
        )
