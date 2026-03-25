"""
MemorySearchEngine — 记忆全文检索引擎

基于 SQLite FTS5 + jieba 分词的全文搜索。
缺少 jieba 时降级为 unicode61 分词（仍可搜索，中文效果稍差）。
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


class MemorySearchEngine:
    """管理记忆文件的全文索引，提供 BM25 检索。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._jieba = None
        self._available = True
        self._init_optional_dependencies()
        self._setup_tables()

    def _init_optional_dependencies(self):
        try:
            import jieba  # type: ignore
            self._jieba = jieba
        except ImportError:
            logger.info("jieba not available, FTS will use unicode61 tokenizer (Chinese search quality may be reduced)")

    @property
    def available(self) -> bool:
        return self._available

    def status_message(self) -> str:
        return ""

    def _jieba_cut(self, text: str) -> str:
        if not self._jieba:
            return text
        return " ".join(self._jieba.cut_for_search(text))

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def _setup_tables(self):
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
        # 用于记录已索引内容的 hash，避免重复索引
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_index_meta (
                namespace TEXT NOT NULL,
                key       TEXT NOT NULL,
                text_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (namespace, key)
            )
        """)
        self.conn.commit()

    @staticmethod
    def _text_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    # ------------------------------------------------------------------
    # 索引写入
    # ------------------------------------------------------------------

    def index_memory(self, ns_json: str, key: str, content_text: str, force_fts: bool = False):
        """写入/更新一条记忆的 FTS 索引。内容没变则跳过。"""
        if key in _SKIP_KEYS or not content_text.strip():
            return

        text_hash = self._text_hash(content_text)
        existing = self.conn.execute(
            "SELECT text_hash FROM memory_index_meta WHERE namespace = ? AND key = ?",
            (ns_json, key),
        ).fetchone()
        need_update = not existing or existing[0] != text_hash

        if not need_update and not force_fts:
            return

        now = datetime.now(timezone.utc).isoformat()

        try:
            # 更新 FTS 索引
            self.conn.execute(
                "DELETE FROM fts_memory WHERE namespace = ? AND key = ?",
                (ns_json, key),
            )
            self.conn.execute(
                "INSERT INTO fts_memory (namespace, key, content) VALUES (?, ?, ?)",
                (ns_json, key, self._jieba_cut(content_text)),
            )

            # 更新元数据
            self.conn.execute("""
                INSERT INTO memory_index_meta (namespace, key, text_hash, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(namespace, key)
                DO UPDATE SET text_hash = excluded.text_hash,
                             updated_at = excluded.updated_at
            """, (ns_json, key, text_hash, now))

            self.conn.commit()
            logger.info("Indexed memory: %s (hash=%s)", key, text_hash)
        except Exception:
            logger.exception("Failed to index memory: %s", key)

    def delete_memory(self, ns_json: str, key: str):
        """删除一条记忆的索引。"""
        self.conn.execute(
            "DELETE FROM memory_index_meta WHERE namespace = ? AND key = ?",
            (ns_json, key),
        )
        self.conn.execute(
            "DELETE FROM fts_memory WHERE namespace = ? AND key = ?",
            (ns_json, key),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # 全文检索
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        namespace_json: str = '["filesystem"]',
        top_k: int = 5,
        **_kwargs: Any,
    ) -> list[dict[str, Any]]:
        """BM25 全文检索。"""
        if not query.strip():
            return []

        try:
            if self._jieba:
                terms = list(self._jieba.cut_for_search(query.strip()))
                terms = [t.strip() for t in terms if t.strip()]
            else:
                terms = query.strip().split()

            if not terms:
                return []

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
                (namespace_json, fts_query, top_k),
            ).fetchall()

            results = []
            for row in fts_rows:
                key, snippet, raw_score = row[0], row[1], -row[2]
                results.append({
                    "key": key,
                    "score": round(raw_score, 4),
                    "cosine": 0.0,
                    "bm25": round(raw_score, 4),
                    "snippet": snippet,
                })
            return results

        except Exception:
            logger.exception("FTS search failed")
            return []

    # ------------------------------------------------------------------
    # Backfill
    # ------------------------------------------------------------------

    def backfill(self) -> int:
        """索引所有尚未索引的记忆文件。"""
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
            except Exception:
                logger.exception("Failed to backfill: %s", key)
        return count


_global_engine: Optional[MemorySearchEngine] = None


def set_global_search_engine(engine: MemorySearchEngine):
    global _global_engine
    _global_engine = engine


def get_global_search_engine() -> Optional[MemorySearchEngine]:
    return _global_engine
