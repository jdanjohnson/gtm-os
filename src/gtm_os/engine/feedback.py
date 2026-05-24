"""Human feedback learning — diff, classify, and save corrections as memories.

Implements WS8B:
- Track original vs approved content
- Classify changes: tone, factual, structural, word_preference, added, removed
- Save each classified change as a memory with appropriate type
- After 10+ similar corrections, auto-promote pattern to rule
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from .memory import VectorMemory
from .store import Store

logger = logging.getLogger(__name__)

CORRECTION_CATEGORIES = [
    "tone_adjustment",
    "factual_correction",
    "structural_change",
    "word_preference",
    "added_content",
    "removed_content",
]


@dataclass
class Correction:
    category: str
    original: str
    revised: str
    description: str


@dataclass
class FeedbackResult:
    corrections: list[Correction] = field(default_factory=list)
    memories_saved: int = 0
    rules_promoted: int = 0


def diff_content(original: str, approved: str) -> list[Correction]:
    """Diff original vs approved content, classify each change."""
    if not original or not approved:
        return []

    corrections: list[Correction] = []
    orig_lines = original.strip().splitlines()
    appr_lines = approved.strip().splitlines()

    matcher = SequenceMatcher(None, orig_lines, appr_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        orig_chunk = "\n".join(orig_lines[i1:i2])
        appr_chunk = "\n".join(appr_lines[j1:j2])

        if tag == "delete":
            corrections.append(Correction(
                category="removed_content",
                original=orig_chunk,
                revised="",
                description=f"Removed: {orig_chunk[:100]}",
            ))
        elif tag == "insert":
            corrections.append(Correction(
                category="added_content",
                original="",
                revised=appr_chunk,
                description=f"Added: {appr_chunk[:100]}",
            ))
        elif tag == "replace":
            category = _classify_replacement(orig_chunk, appr_chunk)
            corrections.append(Correction(
                category=category,
                original=orig_chunk,
                revised=appr_chunk,
                description=f"{category}: '{orig_chunk[:50]}' → '{appr_chunk[:50]}'",
            ))

    return corrections


def _classify_replacement(original: str, revised: str) -> str:
    """Heuristic classification of a replacement."""
    orig_words = set(original.lower().split())
    rev_words = set(revised.lower().split())
    overlap = orig_words & rev_words

    # If most words are the same, it's likely a tone or word preference change.
    if len(orig_words) > 0 and len(overlap) / max(len(orig_words), 1) > 0.7:
        return "word_preference"

    # If lengths are very different, it's structural.
    if abs(len(original) - len(revised)) > len(original) * 0.5:
        return "structural_change"

    # If few words overlap, could be factual or tone.
    if len(overlap) / max(len(orig_words), 1) < 0.3:
        return "factual_correction"

    return "tone_adjustment"


async def process_feedback(
    *,
    original: str,
    approved: str,
    experiment_id: str,
    memory: VectorMemory,
    store: Store,
) -> FeedbackResult:
    """Process human feedback: diff, classify, save as memories."""
    corrections = diff_content(original, approved)
    result = FeedbackResult(corrections=corrections)

    for correction in corrections:
        # Map correction category to memory type.
        mem_type = "preference" if correction.category == "word_preference" else "learning"
        confidence = 0.6 if correction.category in ("tone_adjustment", "word_preference") else 0.5

        content = f"Human correction ({correction.category}): {correction.description}"
        if correction.original:
            content += f"\nOriginal: {correction.original[:200]}"
        if correction.revised:
            content += f"\nRevised: {correction.revised[:200]}"

        await memory.save(
            content,
            type=mem_type,
            source="human_feedback",
            experiment_id=experiment_id,
            confidence=confidence,
        )
        result.memories_saved += 1

    # Check for accumulated similar corrections → auto-promote to rule.
    if result.memories_saved > 0:
        promoted = await _check_for_pattern_promotion(memory, store)
        result.rules_promoted = promoted

    return result


async def _check_for_pattern_promotion(memory: VectorMemory, store: Store) -> int:
    """If 10+ similar corrections exist, promote the pattern to a rule."""
    promoted = 0
    feedback_memories = store.list_memories(type_filter="preference", limit=100)

    # Group by content similarity.
    groups: dict[str, list[Any]] = {}
    for m in feedback_memories:
        if not m.source or m.source != "human_feedback":
            continue
        key = m.content[:50]
        groups.setdefault(key, []).append(m)

    for key, group in groups.items():
        if len(group) >= 10:
            # Promote to rule.
            rule_content = (
                f"Derived rule from {len(group)} human corrections: "
                f"{group[0].content[:200]}"
            )
            await memory.save(
                rule_content,
                type="rule",
                source="feedback_promotion",
                confidence=0.8,
            )
            promoted += 1
            logger.info("promoted feedback pattern to rule: %s", key[:50])

    return promoted
