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
        ignore = self.directory / ".gitignore"
        if ignore.is_symlink():
            raise RepoError("Knowledge Debt ignore file must not be symlinked")
        ignore.write_text("*\n", encoding="utf-8")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY, concept_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL, answer TEXT NOT NULL,
                covered TEXT NOT NULL, created_at TEXT NOT NULL,
                head TEXT, provenance TEXT NOT NULL
            )""")
            connection.execute("CREATE INDEX IF NOT EXISTS evidence_concept_id ON evidence(concept_id, id)")

    def latest(self, concept_id):
        return self.latest_all().get(concept_id)

    def latest_all(self):
        """One connection/query per scan, including old v0.1.0 databases."""
        if not self.path.exists():
            return {}
        try:
            with closing(sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute("SELECT e.* FROM evidence e JOIN "
                                          "(SELECT MAX(id) AS id FROM evidence GROUP BY concept_id) latest "
                                          "ON latest.id = e.id").fetchall()
            return {row["concept_id"]: dict(row) for row in rows}
        except sqlite3.Error as exc:
            raise RepoError("Cannot read .kdebt/evidence.sqlite3. Back up the file before recovery; "
                            "no records were changed.") from exc

    def state(self, concept):
        return self.state_from_record(concept, self.latest(concept.id))

    @staticmethod
    def state_from_record(concept, latest):
        if latest is None:
            return "unrecorded"
        if latest["fingerprint"] != concept.fingerprint:
            return "stale"
        try:
            covered = json.loads(latest["covered"])
            if not isinstance(covered, list) or not all(isinstance(f, str) for f in covered):
                raise ValueError("Invalid fact IDs")
            covered = set(covered)
            allowed = {fact.id for fact in concept.facts}
            if not covered <= allowed:
                raise ValueError("Unknown stored fact IDs")
        except (TypeError, ValueError) as exc:
            raise RepoError("Invalid stored fact coverage; back up .kdebt/evidence.sqlite3 before recovery") from exc
        if not covered:
            return "answer_recorded"
        return "self_checked" if covered == allowed else "partial"

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
