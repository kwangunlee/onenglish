"""
저장소 (SQLite).

나중에 클라우드로 옮길 때 이 파일만 교체하면 됩니다. 다른 모듈은 여기 있는
함수만 호출하고 SQL 을 직접 쓰지 않습니다.

주의: role 컬럼에는 'user' 와 'assistant' 만 들어갑니다. 예전 버전에서 AI 응답을
'system' 으로 저장해 대화 맥락이 깨지던 버그를 구조적으로 막기 위해 CHECK 제약을
걸어두었습니다.
"""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from . import config

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS profiles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    level         TEXT NOT NULL DEFAULT 'kids',
    created_at    TEXT NOT NULL,
    last_seen_at  TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    profile_id    INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    character_id  TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    ended_at      TEXT,
    turn_count    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memories (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id    INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    session_id    TEXT REFERENCES sessions(id) ON DELETE SET NULL,
    kind          TEXT NOT NULL,
    summary_ko    TEXT NOT NULL,
    summary_en    TEXT NOT NULL,
    people        TEXT NOT NULL DEFAULT '[]',
    sentiment     TEXT,
    occurred_on   TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learning_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id   INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    session_id   TEXT REFERENCES sessions(id) ON DELETE SET NULL,
    kind         TEXT NOT NULL,
    child_said   TEXT,
    better_form  TEXT,
    note_ko      TEXT,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session   ON messages(session_id, id);
CREATE INDEX IF NOT EXISTS idx_sessions_profile   ON sessions(profile_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_profile   ON memories(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_profile   ON learning_log(profile_id, created_at DESC);
"""


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


# ── 프로필 ───────────────────────────────────────────────────────

def list_profiles() -> list[dict]:
    with connect() as conn:
        # (last_seen_at IS NULL) 을 먼저 정렬키로 쓰면 NULLS LAST 와 같은 효과가
        # 나면서 구버전 SQLite 에서도 동작합니다.
        return _rows(conn.execute(
            "SELECT * FROM profiles"
            " ORDER BY (last_seen_at IS NULL), last_seen_at DESC, name"
        ))


def get_profile(profile_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        return dict(row) if row else None


def create_profile(name: str, level: str = "kids") -> dict:
    name = name.strip()
    if not name:
        raise ValueError("이름을 입력해 주세요.")
    with connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO profiles (name, level, created_at) VALUES (?, ?, ?)",
                (name, level, now()),
            )
        except sqlite3.IntegrityError:
            raise ValueError(f"'{name}' 은(는) 이미 있는 이름이에요.") from None
        row = conn.execute(
            "SELECT * FROM profiles WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)


def touch_profile(profile_id: int) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE profiles SET last_seen_at = ? WHERE id = ?", (now(), profile_id)
        )


def delete_profile(profile_id: int) -> None:
    """프로필과 그에 딸린 모든 기록을 지웁니다 (되돌릴 수 없음)."""
    with connect() as conn:
        conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))


# ── 세션 ─────────────────────────────────────────────────────────

def start_session(profile_id: int, character_id: str) -> str:
    session_id = str(uuid.uuid4())
    with connect() as conn:
        conn.execute(
            "INSERT INTO sessions (id, profile_id, character_id, started_at)"
            " VALUES (?, ?, ?, ?)",
            (session_id, profile_id, character_id, now()),
        )
    touch_profile(profile_id)
    return session_id


def end_session(session_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ? AND ended_at IS NULL",
            (now(), session_id),
        )


def list_sessions(profile_id: int, limit: int = 50) -> list[dict]:
    with connect() as conn:
        return _rows(conn.execute(
            "SELECT s.*, (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id)"
            " AS message_count FROM sessions s WHERE s.profile_id = ?"
            " ORDER BY s.started_at DESC LIMIT ?",
            (profile_id, limit),
        ))


def session_is_empty(session_id: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()
        return row["n"] == 0


# ── 메시지 ───────────────────────────────────────────────────────

def add_message(session_id: str, role: str, content: str) -> None:
    if role not in ("user", "assistant"):
        raise ValueError(f"role 은 'user' 또는 'assistant' 여야 합니다: {role!r}")
    with connect() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at)"
            " VALUES (?, ?, ?, ?)",
            (session_id, role, content, now()),
        )
        conn.execute(
            "UPDATE sessions SET turn_count = turn_count + 1 WHERE id = ?",
            (session_id,),
        )


def get_messages(session_id: str) -> list[dict]:
    with connect() as conn:
        return _rows(conn.execute(
            "SELECT role, content, created_at FROM messages"
            " WHERE session_id = ? ORDER BY id",
            (session_id,),
        ))


# ── 생활 기억 ────────────────────────────────────────────────────

def add_memory(
    profile_id: int,
    session_id: str | None,
    kind: str,
    summary_ko: str,
    summary_en: str,
    people: list[str] | None = None,
    sentiment: str | None = None,
    occurred_on: str | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO memories (profile_id, session_id, kind, summary_ko,"
            " summary_en, people, sentiment, occurred_on, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                profile_id,
                session_id,
                kind,
                summary_ko,
                summary_en,
                json.dumps(people or [], ensure_ascii=False),
                sentiment,
                occurred_on or today(),
                now(),
            ),
        )


def recent_memories(profile_id: int, limit: int = 6) -> list[dict]:
    with connect() as conn:
        rows = _rows(conn.execute(
            "SELECT * FROM memories WHERE profile_id = ?"
            " ORDER BY created_at DESC LIMIT ?",
            (profile_id, limit),
        ))
    for r in rows:
        r["people"] = json.loads(r.get("people") or "[]")
    return rows


def all_memories(profile_id: int, limit: int = 200) -> list[dict]:
    return recent_memories(profile_id, limit)


def delete_memory(memory_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))


def memory_exists(profile_id: int, summary_en: str) -> bool:
    """같은 기억이 중복 저장되는 것을 막습니다."""
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM memories WHERE profile_id = ?"
            " AND lower(summary_en) = lower(?) LIMIT 1",
            (profile_id, summary_en.strip()),
        ).fetchone()
        return row is not None


# ── 학습 기록 ────────────────────────────────────────────────────

def add_learning_entry(
    profile_id: int,
    session_id: str | None,
    kind: str,
    child_said: str | None = None,
    better_form: str | None = None,
    note_ko: str | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO learning_log (profile_id, session_id, kind, child_said,"
            " better_form, note_ko, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (profile_id, session_id, kind, child_said, better_form, note_ko, now()),
        )


def recent_learning(profile_id: int, limit: int = 100) -> list[dict]:
    with connect() as conn:
        return _rows(conn.execute(
            "SELECT * FROM learning_log WHERE profile_id = ?"
            " ORDER BY created_at DESC LIMIT ?",
            (profile_id, limit),
        ))


def frequent_mistakes(profile_id: int, limit: int = 10) -> list[dict]:
    """반복되는 실수를 많은 순으로. 부모용 화면에서 씁니다."""
    with connect() as conn:
        return _rows(conn.execute(
            "SELECT better_form, note_ko, COUNT(*) AS times,"
            " MAX(created_at) AS last_seen FROM learning_log"
            " WHERE profile_id = ? AND kind = 'mistake' AND better_form IS NOT NULL"
            " GROUP BY lower(better_form) ORDER BY times DESC, last_seen DESC"
            " LIMIT ?",
            (profile_id, limit),
        ))


# ── 통계 ─────────────────────────────────────────────────────────

def profile_stats(profile_id: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(
            "SELECT (SELECT COUNT(*) FROM sessions WHERE profile_id = ?) AS sessions,"
            " (SELECT COUNT(*) FROM messages m JOIN sessions s ON m.session_id = s.id"
            "   WHERE s.profile_id = ? AND m.role = 'user') AS child_turns,"
            " (SELECT COUNT(*) FROM memories WHERE profile_id = ?) AS memories,"
            " (SELECT COUNT(*) FROM learning_log WHERE profile_id = ?) AS learning",
            (profile_id, profile_id, profile_id, profile_id),
        ).fetchone()
        return dict(row)
