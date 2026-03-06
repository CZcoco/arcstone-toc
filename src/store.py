"""SqliteStore — a lightweight SQLite-backed implementation of langgraph BaseStore."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable

from langgraph.store.base import (
    BaseStore,
    GetOp,
    Item,
    ListNamespacesOp,
    MatchCondition,
    Op,
    PutOp,
    Result,
    SearchItem,
    SearchOp,
)


class SqliteStore(BaseStore):
    """A thread-safe, synchronous SQLite store for langgraph memory.

    Each ``put`` is committed immediately so data survives crashes.
    Namespaces (``tuple[str, ...]``) are persisted as JSON arrays,
    and values (``dict[str, Any]``) are persisted as JSON objects.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.setup()

        # 语义检索引擎（共享连接）
        from src.memory_search import MemorySearchEngine
        self.search_engine = MemorySearchEngine(self.conn)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def setup(self) -> None:
        """Create the items table if it does not already exist."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                namespace TEXT NOT NULL,
                key       TEXT NOT NULL,
                value     TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (namespace, key)
            )
            """
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Core abstract methods
    # ------------------------------------------------------------------

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        results: list[Result] = []
        for op in ops:
            if isinstance(op, GetOp):
                results.append(self._handle_get(op))
            elif isinstance(op, PutOp):
                results.append(self._handle_put(op))
            elif isinstance(op, SearchOp):
                results.append(self._handle_search(op))
            elif isinstance(op, ListNamespacesOp):
                results.append(self._handle_list_namespaces(op))
            else:
                raise ValueError(f"Unknown op type: {type(op)}")
        return results

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        """Async facade — delegates to the synchronous ``batch``."""
        return self.batch(ops)

    # ------------------------------------------------------------------
    # Op handlers
    # ------------------------------------------------------------------

    def _handle_get(self, op: GetOp) -> Item | None:
        ns_json = _ns_to_json(op.namespace)
        row = self.conn.execute(
            "SELECT value, created_at, updated_at FROM items WHERE namespace = ? AND key = ?",
            (ns_json, op.key),
        ).fetchone()
        if row is None:
            return None
        return _row_to_item(op.namespace, op.key, row)

    def _handle_put(self, op: PutOp) -> None:
        ns_json = _ns_to_json(op.namespace)
        if op.value is None:
            # DELETE semantics
            self.conn.execute(
                "DELETE FROM items WHERE namespace = ? AND key = ?",
                (ns_json, op.key),
            )
            self.conn.commit()
            if op.namespace == ("filesystem",):
                self.search_engine.delete_memory(ns_json, op.key)
            return None

        now = _now_iso()
        # Check if the item already exists to preserve created_at
        existing = self.conn.execute(
            "SELECT created_at FROM items WHERE namespace = ? AND key = ?",
            (ns_json, op.key),
        ).fetchone()
        created_at = existing[0] if existing else now

        self.conn.execute(
            """
            INSERT INTO items (namespace, key, value, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(namespace, key)
            DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (ns_json, op.key, json.dumps(op.value, ensure_ascii=False), created_at, now),
        )
        self.conn.commit()

        # 更新语义检索索引
        if op.namespace == ("filesystem",):
            content = op.value.get("content", [])
            if isinstance(content, list):
                text = "\n".join(content)
            else:
                text = str(content)
            self.search_engine.index_memory(ns_json, op.key, text)

        return None

    def _handle_search(self, op: SearchOp) -> list[SearchItem]:
        ns_prefix_json = _ns_to_json(op.namespace_prefix)
        # Prefix matching: namespace must start with the JSON-serialised prefix
        # e.g. prefix ("filesystem",) -> '["filesystem"]'
        # should match '["filesystem"]' and '["filesystem", "sub"]'
        #
        # Strategy: strip the trailing ']' from the prefix and use LIKE.
        # '["filesystem"'  matches  '["filesystem"]'  and  '["filesystem", ...]'
        like_pattern = ns_prefix_json.rstrip("]") + "%"

        query = "SELECT namespace, key, value, created_at, updated_at FROM items WHERE namespace LIKE ?"
        params: list[Any] = [like_pattern]

        # Apply filters if present
        # filter is a dict of key->value that must match inside the JSON value
        if op.filter:
            for fk, fv in op.filter.items():
                query += " AND json_extract(value, ?) = ?"
                params.append(f"$.{fk}")
                params.append(json.dumps(fv) if not isinstance(fv, (str, int, float, bool)) else fv)

        query += " ORDER BY updated_at DESC"
        query += " LIMIT ? OFFSET ?"
        params.append(op.limit)
        params.append(op.offset)

        rows = self.conn.execute(query, params).fetchall()
        results: list[SearchItem] = []
        for row in rows:
            ns = _json_to_ns(row[0])
            value = json.loads(row[2])
            created_at = datetime.fromisoformat(row[3])
            updated_at = datetime.fromisoformat(row[4])
            results.append(
                SearchItem(
                    namespace=ns,
                    key=row[1],
                    value=value,
                    created_at=created_at,
                    updated_at=updated_at,
                    score=None,
                )
            )
        return results

    def _handle_list_namespaces(self, op: ListNamespacesOp) -> list[tuple[str, ...]]:
        rows = self.conn.execute("SELECT DISTINCT namespace FROM items").fetchall()
        namespaces: list[tuple[str, ...]] = [_json_to_ns(r[0]) for r in rows]

        # Apply match conditions
        if op.match_conditions:
            for cond in op.match_conditions:
                if cond.match_type == "prefix":
                    prefix = tuple(cond.path)
                    namespaces = [ns for ns in namespaces if ns[: len(prefix)] == prefix]
                elif cond.match_type == "suffix":
                    suffix = tuple(cond.path)
                    namespaces = [ns for ns in namespaces if ns[len(ns) - len(suffix) :] == suffix]

        # Apply max_depth — truncate and deduplicate
        if op.max_depth is not None:
            namespaces = list({ns[: op.max_depth] for ns in namespaces})

        # Sort for deterministic output
        namespaces.sort()

        # Apply offset / limit
        namespaces = namespaces[op.offset : op.offset + op.limit]
        return namespaces


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _ns_to_json(ns: tuple[str, ...]) -> str:
    """Serialise a namespace tuple to a JSON array string."""
    return json.dumps(list(ns), ensure_ascii=False)


def _json_to_ns(s: str) -> tuple[str, ...]:
    """Deserialise a JSON array string back to a namespace tuple."""
    return tuple(json.loads(s))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_item(
    namespace: tuple[str, ...],
    key: str,
    row: tuple[str, str, str],
) -> Item:
    """Convert a DB row ``(value, created_at, updated_at)`` to an ``Item``."""
    value = json.loads(row[0])
    created_at = datetime.fromisoformat(row[1])
    updated_at = datetime.fromisoformat(row[2])
    return Item(
        value=value,
        key=key,
        namespace=namespace,
        created_at=created_at,
        updated_at=updated_at,
    )
