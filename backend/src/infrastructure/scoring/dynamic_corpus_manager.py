"""
infrastructure/scoring/dynamic_corpus_manager.py

Зміни відносно попередньої версії:
  - DynamicCorpusManager приймає опціональний llm_extractor: LLMKeywordExtractor
  - add_article_feedback / remove_article_feedback тепер async
    (бо LLM-екстракція асинхронна)
  - Якщо llm_extractor=None — поведінка незмінна (sync fallback через
    extract_keywords, але обгорнута в async для єдиного інтерфейсу)
  - container.py треба оновити: corpus_manager.add_article_feedback → await
"""
from __future__ import annotations

import logging
import math
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from src.infrastructure.scoring.feedback_keyword_store import LLMKeywordExtractor

logger = logging.getLogger(__name__)

REBUILD_THRESHOLD       = 10
DECAY_LAMBDA            = 0.01   # t½ ≈ 70 днів
MIN_WEIGHT              = 0.15
MAX_TOKENS_PER_CLUSTER  = 150
TOP_N_PER_ARTICLE       = 20

# Індекси dynamic кластерів (після 9 статичних)
CAT_USER_INTERESTS  = 9
CAT_USER_ANTITOPICS = 10


class DynamicCorpusManager:
    """
    Керує dynamic розширенням BM25 корпусу на основі feedback.

    Корпус = 9 статичних кластерів + 2 dynamic:
      [9]  user_interests  — токени з liked статей
      [10] user_antitopics — токени з disliked статей

    Rebuild тригер: кожні rebuild_threshold нових feedback-ів.
    Persistence: SQLite (tokens + feedback_log).
    Decay: exponential, λ=0.01/day → t½ ≈ 70 днів.

    Args:
        llm_extractor: LLMKeywordExtractor або None.
                       Якщо передано — ключові слова витягуються через LLM.
                       Якщо None — використовується TF-IDF fallback (стара поведінка).
    """

    def __init__(
        self,
        db_path: str = "data/dynamic_corpus.db",
        rebuild_threshold: int = REBUILD_THRESHOLD,
        llm_extractor: "LLMKeywordExtractor | None" = None,
    ) -> None:
        from src.infrastructure.scoring.bm25_scoring_service import _TOPIC_CORPUS_RAW

        self._static_corpus = list(_TOPIC_CORPUS_RAW)
        self._db_path        = Path(db_path)
        self._threshold      = rebuild_threshold
        self._pending        = 0
        self._llm_extractor  = llm_extractor   # ← новий параметр

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._init_db()

        self._corpus: list[list[str]] = self._static_corpus + [[], []]
        self._bm25 = None
        self._rebuild_bm25()

    # ── DB ────────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                token      TEXT NOT NULL,
                bucket     TEXT NOT NULL,
                weight     REAL NOT NULL DEFAULT 1.0,
                updated_at REAL NOT NULL,
                PRIMARY KEY (token, bucket)
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback_log (
                article_id TEXT,
                bucket     TEXT,
                logged_at  REAL
            )
        """)
        self._conn.commit()

    # ── Public API ────────────────────────────────────────────────────────────

    async def add_article_feedback(
        self,
        article_id: str,
        text: str,
        bucket: Literal["positive", "negative"],
        language: str = "en",
    ) -> bool:
        """
        Додає токени статті до bucket.

        Якщо llm_extractor налаштований — ключові слова витягуються через LLM,
        інакше — TF-IDF fallback (extract_keywords).

        Повертає True якщо тригернувся rebuild.
        """
        keywords = await self._extract(text, language)
        now = time.time()

        for kw in keywords:
            self._conn.execute("""
                INSERT INTO tokens (token, bucket, weight, updated_at)
                VALUES (?, ?, 1.0, ?)
                ON CONFLICT(token, bucket) DO UPDATE SET
                    weight     = MIN(weight + 0.5, 10.0),
                    updated_at = excluded.updated_at
            """, (kw, bucket, now))

        self._conn.execute(
            "INSERT INTO feedback_log VALUES (?, ?, ?)",
            (article_id, bucket, now),
        )
        self._conn.commit()

        self._pending += 1
        if self._pending >= self._threshold:
            self._pending = 0
            self._rebuild_bm25()
            return True
        return False

    async def remove_article_feedback(
        self,
        text: str,
        bucket: Literal["positive", "negative"],
        language: str = "en",
    ) -> None:
        """Зменшує вагу токенів при зміні feedback."""
        keywords = await self._extract(text, language)
        now = time.time()
        for kw in keywords:
            self._conn.execute("""
                UPDATE tokens
                SET weight = MAX(weight - 1.0, 0.0), updated_at = ?
                WHERE token = ? AND bucket = ?
            """, (now, kw, bucket))
        self._conn.commit()

    def force_rebuild(self) -> None:
        """Примусовий rebuild — для тестів і адмін-інтерфейсу."""
        self._rebuild_bm25()

    def get_bm25(self):
        return self._bm25

    def get_corpus(self) -> list[list[str]]:
        return self._corpus

    def stats(self) -> dict:
        cur = self._conn.execute(
            "SELECT bucket, COUNT(*), AVG(weight) FROM tokens GROUP BY bucket"
        )
        rows = cur.fetchall()
        mode = "llm" if self._llm_extractor is not None else "tfidf"
        return {
            "extraction_mode": mode,
            "clusters": {
                "user_interests":  len(self._corpus[CAT_USER_INTERESTS]),
                "user_antitopics": len(self._corpus[CAT_USER_ANTITOPICS]),
            },
            "db": {
                r[0]: {"count": r[1], "avg_weight": round(r[2], 3)}
                for r in rows
            },
            "pending_until_rebuild": self._threshold - self._pending,
        }

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _extract(self, text: str, language: str) -> list[str]:
        """
        Єдина точка екстракції ключових слів.

        LLM якщо llm_extractor налаштований, інакше — TF-IDF.
        """
        if self._llm_extractor is not None:
            return await self._llm_extractor.extract(
                text=text,
                language=language,
                top_n=TOP_N_PER_ARTICLE,
            )

        # Sync fallback обгорнутий в async для єдиного інтерфейсу
        from src.infrastructure.scoring.feedback_keyword_store import extract_keywords
        return extract_keywords(text, language, top_n=TOP_N_PER_ARTICLE)

    def _decay_weight(self, weight: float, updated_at: float) -> float:
        days = (time.time() - updated_at) / 86400.0
        return weight * math.exp(-DECAY_LAMBDA * days)

    def _load_cluster_tokens(self, bucket: str, max_tokens: int) -> list[str]:
        cur = self._conn.execute(
            "SELECT token, weight, updated_at FROM tokens WHERE bucket = ?",
            (bucket,),
        )
        scored = []
        for token, weight, updated_at in cur.fetchall():
            dw = self._decay_weight(weight, updated_at)
            if dw >= MIN_WEIGHT:
                scored.append((token, dw))

        scored.sort(key=lambda x: -x[1])
        return [tok for tok, _ in scored[:max_tokens]]

    def _rebuild_bm25(self) -> None:
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            logger.warning("rank_bm25 not available — dynamic corpus rebuild skipped")
            return

        interests  = self._load_cluster_tokens("positive", MAX_TOKENS_PER_CLUSTER)
        antitopics = self._load_cluster_tokens("negative", MAX_TOKENS_PER_CLUSTER)

        self._corpus = self._static_corpus + [interests, antitopics]
        self._bm25   = BM25Okapi(self._corpus)

        logger.info(
            "DynamicCorpus rebuilt: user_interests=%d tokens, user_antitopics=%d tokens",
            len(interests), len(antitopics),
        )