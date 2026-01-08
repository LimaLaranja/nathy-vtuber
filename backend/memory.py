import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass(frozen=True)
class FactRow:
    fact: str
    created_at: str


class MemoryStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_user ON facts(user_id);")

    def add_fact(self, user_id: str, fact: str) -> None:
        fact_clean = (fact or "").strip()
        if not fact_clean:
            return

        created_at = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO facts(user_id, fact, created_at) VALUES (?, ?, ?)",
                (user_id, fact_clean, created_at),
            )

    def get_top_facts(self, user_id: str, query: str, limit: int = 6) -> List[str]:
        q = (query or "").strip().lower()
        tokens = [t for t in _tokenize(q) if len(t) >= 3]

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT fact, created_at FROM facts WHERE user_id = ? ORDER BY id DESC LIMIT 200",
                (user_id,),
            ).fetchall()

        scored: list[tuple[int, str]] = []
        for fact, created_at in rows:
            fact_l = str(fact).lower()
            score = 0
            for t in tokens:
                if t in fact_l:
                    score += 1
            if score > 0:
                scored.append((score, str(fact)))

        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[str] = []
        seen = set()
        for _, f in scored:
            if f in seen:
                continue
            seen.add(f)
            out.append(f)
            if len(out) >= limit:
                break

        if out:
            return out

        out2: list[str] = []
        for fact, _created_at in rows:
            f = str(fact)
            if f not in seen:
                out2.append(f)
            if len(out2) >= min(limit, 3):
                break
        return out2


def _tokenize(text: str) -> List[str]:
    buff: list[str] = []
    cur: list[str] = []
    for ch in text:
        if ch.isalnum() or ch in "_áàâãéèêíìîóòôõúùûç":
            cur.append(ch)
        else:
            if cur:
                buff.append("".join(cur))
                cur.clear()
    if cur:
        buff.append("".join(cur))
    return buff
