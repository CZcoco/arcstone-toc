"""
MemorySearchEngine — 记忆语义检索引擎

混合搜索：DashScope text-embedding-v3 向量余弦相似度 (70%) + SQLite FTS5 BM25 (30%)。
缺少 jieba / numpy / openai 等扩展依赖时，自动降级为不可用状态，不阻塞应用启动。
共享 SqliteStore 的 sqlite3 连接，新增 embeddings + fts_memory 两张表。
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 元文件，不需要索引
_SKIP_KEYS = {"/index.md"}

_EMBEDDING_MODEL = "text-embedding-v3"
_EMBEDDING_DIMS = 1024
_MAX_TEXT_CHARS = 8000  # text-embedding-v3 上限约 8192 token


class MemorySearchEngine:
    """管理记忆文件的向量索引和全文索引，提供混合检索。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._client = None
        self._jieba = None
        self._np = None
        self._available = False
        self._missing_dependencies: list[str] = []
        self._init_optional_dependencies()
        self._setup_tables()

    def _init_optional_dependencies(self):
        missing: list[str] = []

        try:
            import jieba  # type: ignore
            self._jieba = jieba
        except ImportError:
            missing.append("jieba")

        try:
            import numpy as np  # type: ignore
            self._np = np
        except ImportError:
            missing.append("numpy")

        try:
            from openai import OpenAI  # type: ignore
            self._openai_cls = OpenAI
        except ImportError:
            self._openai_cls = None
            missing.append("openai")

        self._missing_dependencies = missing
        self._available = not missing
        if missing:
            logger.info("Memory search disabled, missing optional dependencies: %s", ", ".join(missing))

    @property
    def available(self) -> bool:
        return self._available

    def status_message(self) -> str:
        if self.available:
            return ""
        if self._missing_dependencies:
            return f"记忆语义搜索不可用：缺少扩展依赖 {', '.join(self._missing_dependencies)}。"
        return "记忆语义搜索不可用。"

    def _jieba_cut(self, text: str) -> str:
        if not self._jieba:
            return text
        return " ".join(self._jieba.cut_for_search(text))

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def _setup_tables(self):
        if not self.available:
            return
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                namespace TEXT NOT NULL,
                key       TEXT NOT NULL,
                embedding BLOB NOT NULL,
                text_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (namespace, key)
            )
        """)
        row = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='fts_memory'"
        ).fetchone()
        if not row:
            self.conn.execute("""
                CREATE VIRTUAL TABLE fts_memory USING fts5(
                    namespace, key, content,
                    tokenize='unicode61'
                )
            """)
        self.conn.commit()

    def _get_client(self):
        if self._client is None:
            api_key = os.environ.get("DASHSCOPE_API_KEY")
            if not api_key:
                raise ValueError("DASHSCOPE_API_KEY not set")
            self._client = self._openai_cls(
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        return self._client

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def _get_embedding(self, text: str):
        client = self._get_client()
        truncated = text[:_MAX_TEXT_CHARS]
        response = client.embeddings.create(
            model=_EMBEDDING_MODEL,
            input=[truncated],
            dimensions=_EMBEDDING_DIMS,
            timeout=8,
        )
        return self._np.array(response.data[0].embedding, dtype=self._np.float32)

    @staticmethod
    def _text_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    # ------------------------------------------------------------------
    # 索引写入
    # ------------------------------------------------------------------

    def index_memory(self, ns_json: str, key: str, content_text: str, force_fts: bool = False):
        """写入/更新一条记忆的索引。内容没变则跳过 embedding（FTS 可强制刷新）。"""
        if not self.available or key in _SKIP_KEYS or not content_text.strip():
            return

        text_hash = self._text_hash(content_text)
        existing = self.conn.execute(
            "SELECT text_hash FROM embeddings WHERE namespace = ? AND key = ?",
            (ns_json, key),
        ).fetchone()
        need_embedding = not existing or existing[0] != text_hash

        if not need_embedding and not force_fts:
            return

        now = datetime.now(timezone.utc).isoformat()

        try:
            if need_embedding:
                vec = self._get_embedding(content_text)
                self.conn.execute("""
                    INSERT INTO embeddings (namespace, key, embedding, text_hash, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(namespace, key)
                    DO UPDATE SET embedding = excluded.embedding,
                                 text_hash = excluded.text_hash,
                                 updated_at = excluded.updated_at
                """, (ns_json, key, vec.tobytes(), text_hash, now))

            self.conn.execute(
                "DELETE FROM fts_memory WHERE namespace = ? AND key = ?",
                (ns_json, key),
            )
            self.conn.execute(
                "INSERT INTO fts_memory (namespace, key, content) VALUES (?, ?, ?)",
                (ns_json, key, self._jieba_cut(content_text)),
            )

            self.conn.commit()
            logger.info("Indexed memory: %s (hash=%s, embedding=%s, fts=True)", key, text_hash, need_embedding)
        except Exception:
            logger.exception("Failed to index memory: %s", key)

    def delete_memory(self, ns_json: str, key: str):
        """删除一条记忆的索引。"""
        if not self.available:
            return
        self.conn.execute(
            "DELETE FROM embeddings WHERE namespace = ? AND key = ?",
            (ns_json, key),
        )
        self.conn.execute(
            "DELETE FROM fts_memory WHERE namespace = ? AND key = ?",
            (ns_json, key),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # 混合检索
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        namespace_json: str = '["filesystem"]',
        top_k: int = 5,
        cosine_weight: float = 0.7,
        bm25_weight: float = 0.3,
    ) -> list[dict[str, Any]]:
        """混合检索：cosine 相似度 + BM25。"""
        if not self.available:
            return []

        results_map: dict[str, dict[str, Any]] = {}

        try:
            query_vec = self._get_embedding(query)
            rows = self.conn.execute(
                "SELECT key, embedding FROM embeddings WHERE namespace = ?",
                (namespace_json,),
            ).fetchall()

            if rows:
                keys = [r[0] for r in rows]
                vecs = self._np.array(
                    [self._np.frombuffer(r[1], dtype=self._np.float32) for r in rows]
                )
                query_norm = query_vec / (self._np.linalg.norm(query_vec) + 1e-10)
                norms = self._np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-10
                cosine_scores = (vecs / norms) @ query_norm

                for key, score in zip(keys, cosine_scores):
                    results_map[key] = {
                        "cosine": float(score), "bm25": 0.0, "snippet": ""
                    }
        except Exception:
            logger.exception("Cosine search failed")

        try:
            terms = list(self._jieba.cut_for_search(query.strip()))
            terms = [t.strip() for t in terms if t.strip()]
            if terms:
                fts_query = " OR ".join(f'"{t}"' for t in terms[:10])
                fts_rows = self.conn.execute(
                    """
                    SELECT key,
                           snippet(fts_memory, 2, '>>>', '<<<', '...', 64),
                           bm25(fts_memory, 0, 0, 1.0)
                    FROM fts_memory
                    WHERE namespace = ? AND fts_memory MATCH ?
                    ORDER BY bm25(fts_memory, 0, 0, 1.0)
                    LIMIT ?
                    """,
                    (namespace_json, fts_query, top_k * 3),
                ).fetchall()

                if fts_rows:
                    raw_scores = [-r[2] for r in fts_rows]
                    max_score = max(raw_scores) or 1e-10

                    for row, raw in zip(fts_rows, raw_scores):
                        key, snippet = row[0], row[1]
                        norm_bm25 = raw / max_score
                        if key in results_map:
                            results_map[key]["bm25"] = norm_bm25
                            results_map[key]["snippet"] = snippet
                        else:
                            results_map[key] = {
                                "cosine": 0.0,
                                "bm25": norm_bm25,
                                "snippet": snippet,
                            }
        except Exception:
            logger.exception("BM25 search failed")

        results = []
        for key, scores in results_map.items():
            hybrid = cosine_weight * scores["cosine"] + bm25_weight * scores["bm25"]
            results.append({
                "key": key,
                "score": round(hybrid, 4),
                "cosine": round(scores["cosine"], 4),
                "bm25": round(scores["bm25"], 4),
                "snippet": scores["snippet"],
            })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    # ------------------------------------------------------------------
    # Backfill
    # ------------------------------------------------------------------

    def backfill(self) -> int:
        """索引所有尚未索引的记忆文件。无可选依赖或 API key 时跳过。"""
        if not self.available:
            logger.info("Memory search disabled, skipping backfill")
            return 0
        if not os.environ.get("DASHSCOPE_API_KEY"):
            logger.info("DASHSCOPE_API_KEY not set, skipping backfill")
            return 0
        ns_json = '["filesystem"]'
        rows = self.conn.execute(
            "SELECT key, value FROM items WHERE namespace = ?",
            (ns_json,),
        ).fetchall()

        count = 0
        for key, value_json in rows:
            if key in _SKIP_KEYS:
                continue
            try:
                value = json.loads(value_json)
                content = value.get("content", [])
                if isinstance(content, list):
                    text = "\n".join(content)
                else:
                    text = str(content)
                if text.strip():
                    self.index_memory(ns_json, key, text, force_fts=True)
                    count += 1
                    time.sleep(0.2)
            except Exception:
                logger.exception("Failed to backfill: %s", key)
        return count


_global_engine: Optional[MemorySearchEngine] = None


def set_global_search_engine(engine: MemorySearchEngine):
    global _global_engine
    _global_engine = engine


def get_global_search_engine() -> Optional[MemorySearchEngine]:
    return _global_engine
