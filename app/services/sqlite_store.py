from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any


class SQLiteStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS topics (
                    topic_id TEXT PRIMARY KEY,
                    group_id TEXT NOT NULL,
                    type TEXT,
                    create_time TEXT,
                    create_time_iso TEXT,
                    text TEXT,
                    answer_text TEXT,
                    owner_name TEXT,
                    like_count INTEGER NOT NULL DEFAULT 0,
                    comment_count INTEGER NOT NULL DEFAULT 0,
                    liked INTEGER NOT NULL DEFAULT 0,
                    topic_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def upsert_topics(self, topics: list[dict[str, Any]], group_id: str) -> int:
        saved_count = 0
        with self._connect() as conn:
            for topic in topics:
                topic_id = topic.get("topic_id")
                if topic_id is None:
                    continue
                conn.execute(
                    """
                    INSERT INTO topics (
                        topic_id, group_id, type, create_time, create_time_iso, text,
                        answer_text, owner_name, like_count, comment_count, liked, topic_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(topic_id) DO UPDATE SET
                        group_id=excluded.group_id,
                        type=excluded.type,
                        create_time=excluded.create_time,
                        create_time_iso=excluded.create_time_iso,
                        text=excluded.text,
                        answer_text=excluded.answer_text,
                        owner_name=excluded.owner_name,
                        like_count=excluded.like_count,
                        comment_count=excluded.comment_count,
                        liked=excluded.liked,
                        topic_json=excluded.topic_json,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (
                        str(topic_id),
                        group_id,
                        topic.get("type"),
                        topic.get("create_time"),
                        topic.get("create_time_iso"),
                        topic.get("text"),
                        topic.get("answer_text"),
                        (topic.get("owner") or {}).get("name"),
                        topic.get("like_count", 0),
                        topic.get("comment_count", 0),
                        1 if topic.get("liked") else 0,
                        json.dumps(topic, ensure_ascii=False),
                    ),
                )
                saved_count += 1
        return saved_count

    def list_topics(
        self,
        limit: int = 20,
        offset: int = 0,
        group_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT topic_json
            FROM topics
        """
        params: list[Any] = []
        if group_id:
            query += " WHERE group_id = ?"
            params.append(group_id)
        query += " ORDER BY datetime(create_time_iso) DESC, topic_id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [json.loads(row["topic_json"]) for row in rows]
