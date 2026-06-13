from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS libraries (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    domain TEXT,
    version TEXT,
    path TEXT NOT NULL UNIQUE,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    library_id TEXT NOT NULL,
    title TEXT,
    type TEXT,
    path TEXT,
    trust_level TEXT DEFAULT 'user_added',
    metadata_json TEXT,
    created_at TEXT,
    FOREIGN KEY (library_id) REFERENCES libraries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    library_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    text TEXT NOT NULL,
    chunk_index INTEGER,
    metadata_json TEXT,
    created_at TEXT,
    FOREIGN KEY (library_id) REFERENCES libraries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS model_runs (
    id TEXT PRIMARY KEY,
    library_id TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    input TEXT,
    output TEXT,
    prompt TEXT,
    retrieved_context_json TEXT,
    latency_ms INTEGER,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS eval_runs (
    id TEXT PRIMARY KEY,
    library_id TEXT NOT NULL,
    model_provider TEXT,
    model_name TEXT,
    score REAL,
    result_json TEXT,
    created_at TEXT
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(model_runs)").fetchall()
            }
            if "prompt" not in columns:
                connection.execute("ALTER TABLE model_runs ADD COLUMN prompt TEXT")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> None:
        with self.connect() as connection:
            connection.execute(sql, parameters)

    def fetch_all(self, sql: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(sql, parameters).fetchall()]

    def fetch_one(self, sql: str, parameters: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(sql, parameters).fetchone()
            return dict(row) if row else None

    def replace_chunks(
        self,
        library_id: str,
        rows: list[tuple[Any, ...]],
    ) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM chunks WHERE library_id = ?", (library_id,))
            connection.executemany(
                """
                INSERT INTO chunks
                    (id, library_id, source_id, text, chunk_index, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    @staticmethod
    def json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)
