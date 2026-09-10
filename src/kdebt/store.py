"""Local, version-bound self-check records; never inferred mastery."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from .repository import RepoError


class Store:
    def __init__(self, root):
        self.directory = root / ".kdebt"
        self.path = self.directory / "evidence.sqlite3"
        if self.directory.is_symlink() or self.path.is_symlink():
            raise RepoError("Knowledge Debt state must not be symlinked")

    def initialize(self):
        self.directory.mkdir(exist_ok=True)
        (self.directory / ".gitignore").write_text("*\n", encoding="utf-8")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY, concept_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL, answer TEXT NOT NULL,
                covered TEXT NOT NULL, created_at TEXT NOT NULL,
                head TEXT, provenance TEXT NOT NULL
            )""")

    def latest(self, concept_id):
        if not self.path.exists():
            return None
        with closing(sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM evidence WHERE concept_id = ? ORDER BY id DESC LIMIT 1",
                                     (concept_id,)).fetchone()
        return dict(row) if row else None

    def state(self, concept):
        latest = self.latest(concept.id)
        if latest is None:
            return "unrecorded"
        if latest["fingerprint"] != concept.fingerprint:
            return "stale"
        return "self_checked" if json.loads(latest["covered"]) else "answer_recorded"

    def save(self, concept, answer, covered, head):
        allowed = {f.id for f in concept.facts}
        if not answer.strip():
            raise RepoError("An empty answer cannot be recorded")
        if not set(covered) <= allowed:
            raise RepoError("Unknown fact ID; use the IDs from this drill")
        self.initialize()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("INSERT INTO evidence (concept_id, fingerprint, answer, covered, created_at, head, provenance) "
                               "VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (concept.id, concept.fingerprint, answer, json.dumps(sorted(set(covered))),
                                datetime.now(timezone.utc).isoformat(), head, "user_self_report"))
