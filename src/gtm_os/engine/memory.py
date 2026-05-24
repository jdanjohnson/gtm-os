"""Vector memory — embed, store, semantic search, correction-to-rule.

Storage: SQLite (via `Store`). Embeddings: optional — if no embedding provider is
configured, memory still works as keyword/recency search.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Iterable
from pathlib import Path

import numpy as np

from ..config import LLMConfig
from ..types import Memory, MemoryType
from .store import Store

logger = logging.getLogger(__name__)


def _embedding_to_bytes(vec: list[float] | np.ndarray) -> bytes:
    arr = np.asarray(vec, dtype=np.float32)
    return arr.tobytes()


def _bytes_to_embedding(buf: bytes | None) -> np.ndarray | None:
    if not buf:
        return None
    return np.frombuffer(buf, dtype=np.float32)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0 or b.size == 0 or a.size != b.size:
        return 0.0
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


class VectorMemory:
    """Embeddings + cosine-similarity search backed by `Store`."""

    def __init__(self, store: Store, llm_config: LLMConfig) -> None:
        self.store = store
        self.llm_config = llm_config

    async def embed(self, text: str) -> list[float] | None:
        """Embed text via litellm. Returns None when no embedding model is configured."""
        if not self.llm_config.embedding_model:
            return None
        try:
            import litellm

            response = await litellm.aembedding(
                model=self.llm_config.embedding_model,
                input=text,
                api_key=self.llm_config.api_key,
                timeout=self.llm_config.request_timeout_seconds,
            )
            data = response["data"][0]["embedding"]
            return [float(x) for x in data]
        except Exception as exc:  # pragma: no cover — embeddings are optional
            logger.warning("embedding failed: %s", exc)
            return None

    async def save(
        self,
        content: str,
        *,
        type: MemoryType = "fact",
        source: str | None = None,
        experiment_id: str | None = None,
        confidence: float = 0.5,
    ) -> Memory:
        embedding = await self.embed(content)
        emb_bytes = _embedding_to_bytes(embedding) if embedding else None
        return self.store.insert_memory(
            type=type,
            content=content,
            source=source,
            experiment_id=experiment_id,
            confidence=max(0.0, min(1.0, float(confidence))),
            embedding=emb_bytes,
        )

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        type_filter: str | None = None,
        min_confidence: float = 0.0,
    ) -> list[Memory]:
        rows = list(self.store.all_memory_rows(type_filter=type_filter))
        if not rows:
            return []

        query_vec = await self.embed(query)
        scored: list[tuple[float, Memory]] = []
        if query_vec:
            q_arr = np.asarray(query_vec, dtype=np.float32)
            for row in rows:
                m = _row_to_mem(row)
                if m.confidence < min_confidence:
                    continue
                e = _bytes_to_embedding(row["embedding"])
                score = _cosine(q_arr, e) if e is not None else _keyword_score(query, m.content)
                scored.append((score, m))
        else:
            # Keyword/recency fallback.
            for row in rows:
                m = _row_to_mem(row)
                if m.confidence < min_confidence:
                    continue
                scored.append((_keyword_score(query, m.content), m))

        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[Memory] = []
        for score, m in scored[:limit]:
            m.similarity = float(score)
            out.append(m)
        return out

    async def reinforce(self, memory_id: str, experiment_id: str) -> Memory | None:
        m = self.store.get_memory(memory_id)
        if not m:
            return None
        if experiment_id in m.reinforced_by:
            return m
        reinforced = [*m.reinforced_by, experiment_id]
        new_conf = min(1.0, m.confidence + 0.1)
        self.store.update_memory_confidence(
            memory_id, confidence=new_conf, reinforced_by=reinforced
        )
        return self.store.get_memory(memory_id)

    def write_corrections_to_rules(
        self,
        rules_dir: Path,
        *,
        threshold: float = 0.8,
        min_reinforcements: int = 3,
    ) -> list[Path]:
        """Promote high-confidence learnings to standing rule files."""
        rules_dir = Path(rules_dir)
        derived = rules_dir / "derived"
        derived.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for m in self.store.list_memories(type_filter="learning", limit=500):
            if m.confidence < threshold:
                continue
            if len(m.reinforced_by) < min_reinforcements:
                continue
            slug = _slugify(m.content)[:60] or m.id
            path = derived / f"{slug}.md"
            body = (
                f"# Derived rule\n\n"
                f"_Promoted from learning {m.id} "
                f"(confidence {m.confidence:.2f}, reinforced by {len(m.reinforced_by)} experiments)._\n\n"
                f"{m.content}\n"
            )
            path.write_text(body, encoding="utf-8")
            written.append(path)
        return written


def _row_to_mem(row) -> Memory:
    return Memory(
        id=row["id"],
        type=row["type"],
        content=row["content"],
        source=row["source"],
        experiment_id=row["experiment_id"],
        confidence=float(row["confidence"] or 0.0),
        reinforced_by=_json_or(row["reinforced_by"], []),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _json_or(value, default):
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def _keyword_score(query: str, content: str) -> float:
    q_tokens = set(_tokenize(query))
    c_tokens = set(_tokenize(content))
    if not q_tokens or not c_tokens:
        return 0.0
    overlap = len(q_tokens & c_tokens)
    return overlap / math.sqrt(len(q_tokens) * len(c_tokens))


def _tokenize(text: str) -> Iterable[str]:
    return [t for t in re.split(r"[^a-zA-Z0-9]+", text.lower()) if len(t) > 2]
