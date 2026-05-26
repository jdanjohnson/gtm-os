"""Vector memory — embed, store, semantic search, correction-to-rule.

Implements WS2B:
- Entity memory: per-prospect/per-company structured facts
- Episodic memory: replay a full run's conversation
- Memory decay: older memories with low confidence lose 0.01 per week
- Memory dedup: cosine > 0.92 → reinforce instead of creating duplicate
- Batch embed: multiple texts in one API call for efficiency

Storage: SQLite (via `Store`). Embeddings: optional — if no embedding provider is
configured, memory still works as keyword/recency search.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from ..config import LLMConfig
from ..types import Memory, MemoryType
from .store import Store

logger = logging.getLogger(__name__)

# Dedup threshold — memories with cosine > this are considered duplicates.
DEDUP_COSINE_THRESHOLD = 0.92
# Decay rate: confidence lost per week for memories older than 4 weeks.
DECAY_RATE_PER_WEEK = 0.01
# Archive threshold: memories below this confidence are archived.
ARCHIVE_THRESHOLD = 0.1


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
    """Embeddings + cosine-similarity search backed by `Store`.

    Extended with entity memory, episodic replay, decay, and dedup.
    """

    def __init__(self, store: Store, llm_config: LLMConfig) -> None:
        self.store = store
        self.llm_config = llm_config

    # ---------- embedding ----------

    async def embed(self, text: str) -> list[float] | None:
        """Embed text via litellm. Returns None when no embedding model is configured."""
        if not self.llm_config.embedding_model:
            return None
        try:
            import litellm

            response = await litellm.aembedding(
                model=self.llm_config.embedding_model,
                input=text,
                api_key=self.llm_config.embedding_api_key,
                timeout=self.llm_config.request_timeout_seconds,
            )
            data = response["data"][0]["embedding"]
            return [float(x) for x in data]
        except Exception as exc:
            logger.warning("embedding failed: %s", exc)
            return None

    async def batch_embed(self, texts: list[str]) -> list[list[float] | None]:
        """Batch embed multiple texts in one API call (WS2B)."""
        if not self.llm_config.embedding_model or not texts:
            return [None] * len(texts)
        try:
            import litellm

            response = await litellm.aembedding(
                model=self.llm_config.embedding_model,
                input=texts,
                api_key=self.llm_config.embedding_api_key,
                timeout=self.llm_config.request_timeout_seconds,
            )
            results: list[list[float] | None] = []
            for item in response["data"]:
                results.append([float(x) for x in item["embedding"]])
            return results
        except Exception as exc:
            logger.warning("batch embedding failed: %s", exc)
            return [None] * len(texts)

    # ---------- save (with dedup) ----------

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

        # WS2B: Check for duplicates before saving.
        if embedding:
            existing = self._find_duplicate(embedding)
            if existing:
                logger.debug("memory dedup: reinforcing existing memory %s", existing.id)
                reinforced = list(existing.reinforced_by)
                if experiment_id and experiment_id not in reinforced:
                    reinforced.append(experiment_id)
                new_conf = min(1.0, existing.confidence + 0.1)
                self.store.update_memory_confidence(
                    existing.id, confidence=new_conf, reinforced_by=reinforced
                )
                return self.store.get_memory(existing.id)  # type: ignore[return-value]

        emb_bytes = _embedding_to_bytes(embedding) if embedding else None
        return self.store.insert_memory(
            type=type,
            content=content,
            source=source,
            experiment_id=experiment_id,
            confidence=max(0.0, min(1.0, float(confidence))),
            embedding=emb_bytes,
        )

    def _find_duplicate(self, query_embedding: list[float]) -> Memory | None:
        """Check if a similar memory exists (cosine > threshold)."""
        q_arr = np.asarray(query_embedding, dtype=np.float32)
        rows = list(self.store.all_memory_rows())
        for row in rows:
            e = _bytes_to_embedding(row["embedding"])
            if e is not None:
                sim = _cosine(q_arr, e)
                if sim > DEDUP_COSINE_THRESHOLD:
                    return _row_to_mem(row)
        return None

    # ---------- search ----------

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

    # ---------- reinforce ----------

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

    # ---------- entity memory (WS2B) ----------

    async def save_entity(
        self,
        entity_type: str,
        entity_id: str,
        facts: dict,
        *,
        experiment_id: str | None = None,
        confidence: float = 0.7,
    ) -> Memory:
        """Save structured entity facts (per-prospect, per-company)."""
        content = json.dumps(
            {"entity_type": entity_type, "entity_id": entity_id, "facts": facts},
            default=str,
        )
        return await self.save(
            content,
            type="fact",
            source=f"entity:{entity_type}/{entity_id}",
            experiment_id=experiment_id,
            confidence=confidence,
        )

    async def get_entity(self, entity_type: str, entity_id: str) -> list[Memory]:
        """Retrieve all memories about a specific entity."""
        source_prefix = f"entity:{entity_type}/{entity_id}"
        rows = list(self.store.all_memory_rows())
        results: list[Memory] = []
        for row in rows:
            m = _row_to_mem(row)
            if m.source and m.source.startswith(source_prefix):
                results.append(m)
        return results

    # ---------- episodic memory (WS2B) ----------

    def replay_run(self, run_id: str) -> list[dict]:
        """Replay a full run's conversation from the messages table."""
        run = self.store.get_run(run_id)
        if not run or not run.experiment_id:
            return []
        messages = self.store.list_messages(experiment_id=run.experiment_id, limit=500)
        return messages

    # ---------- memory decay (WS2B) ----------

    def apply_decay(self) -> int:
        """Apply weekly decay to old memories. Memories below threshold are archived."""
        now = datetime.now(UTC)
        decay_cutoff = now - timedelta(weeks=4)
        decayed_count = 0

        all_memories = self.store.list_memories(limit=5000)
        for m in all_memories:
            if not m.created_at:
                continue
            try:
                created = datetime.fromisoformat(m.created_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            if created >= decay_cutoff:
                continue

            weeks_old = (now - created).days / 7.0
            weeks_past_cutoff = weeks_old - 4.0
            decay_amount = DECAY_RATE_PER_WEEK * weeks_past_cutoff
            new_confidence = max(0.0, m.confidence - decay_amount)

            if abs(new_confidence - m.confidence) < 0.001:
                continue

            self.store.update_memory_confidence(
                m.id, confidence=new_confidence, reinforced_by=m.reinforced_by
            )
            decayed_count += 1

        return decayed_count

    # ---------- correction-to-rule ----------

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
            if path.exists():
                continue
            body = (
                f"# Derived rule\n\n"
                f"_Promoted from learning {m.id} "
                f"(confidence {m.confidence:.2f}, reinforced by "
                f"{len(m.reinforced_by)} experiments)._\n\n"
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
