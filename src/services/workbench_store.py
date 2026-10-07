"""SQLite document storage. Transactions serialize queue state changes."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
import uuid


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def public(value):
    if isinstance(value, dict):
        return {key: public(item) for key, item in value.items() if not key.startswith("_")}
    if isinstance(value, list):
        return [public(item) for item in value]
    return value


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.connection = sqlite3.connect(self.root / "workspace.sqlite3", check_same_thread=False)
        (self.root / "workspace.sqlite3").chmod(0o600)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS documents "
            "(kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(kind,id))"
        )
        self.connection.commit()

    @contextmanager
    def transaction(self):
        with self.lock:
            try:
                yield self
                self.connection.commit()
            except BaseException:
                self.connection.rollback()
                raise

    def get(self, kind, key):
        with self.lock:
            row = self.connection.execute(
                "SELECT data FROM documents WHERE kind=? AND id=?", (kind, key)
            ).fetchone()
            return json.loads(row[0]) if row else None

    def all(self, kind):
        with self.lock:
            rows = self.connection.execute(
                "SELECT data FROM documents WHERE kind=? ORDER BY rowid DESC", (kind,)
            ).fetchall()
            return [json.loads(row[0]) for row in rows]

    def put(self, kind, value):
        with self.lock:
            self.connection.execute(
                "INSERT INTO documents(kind,id,data) VALUES(?,?,?) "
                "ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data",
                (kind, value["id"], json.dumps(value, ensure_ascii=False, allow_nan=False)),
            )
            return value

    def delete(self, kind, key):
        with self.lock:
            self.connection.execute("DELETE FROM documents WHERE kind=? AND id=?", (kind, key))

    def close(self):
        self.connection.close()
