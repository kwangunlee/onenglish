"""
이 컴퓨터의 대화 기록(data/onenglish.db, SQLite)을 Firestore 로 옮깁니다.

    python tools/migrate_to_firestore.py

먼저 .streamlit/secrets.toml 에 DB_BACKEND = "firestore" 와 서비스 계정 키
([gcp_service_account])를 채워야 합니다. 앱과 같은 설정을 읽어서 같은 곳에 넣습니다.

안전장치
  - 원본 SQLite 파일은 읽기만 하고 고치지 않습니다.
  - Firestore 에 이미 프로필이 있으면 멈춥니다. (두 번 옮겨서 섞이는 것 방지)
  - 옮기기 전에 몇 개를 옮길지 보여주고 물어봅니다. (--yes 로 건너뛰기)
  - 다 옮긴 뒤 개수를 다시 세어 맞는지 확인합니다.

옵션
  --source 경로   다른 SQLite 파일에서 옮길 때
  --yes           묻지 않고 바로 옮기기

무료 한도: 쓰기는 하루 2만 번까지 무료입니다. 기록이 아주 많으면(메시지 2만 개
이상) 하루에 다 못 옮길 수 있으니, 그럴 땐 알려주세요.
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load_secrets() -> None:
    """앱과 같은 설정(.streamlit/secrets.toml)을 환경변수로 옮깁니다."""
    path = ROOT / ".streamlit" / "secrets.toml"
    if not path.exists():
        return
    import tomllib
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    for key, value in data.items():
        if key == "gcp_service_account" and isinstance(value, dict):
            os.environ.setdefault("GCP_SERVICE_ACCOUNT_JSON", json.dumps(value))
        elif isinstance(value, (str, int, float)) and str(value).strip():
            os.environ.setdefault(key, str(value).strip())


_load_secrets()

from core import config, store, store_firestore as fs  # noqa: E402


def fail(message: str) -> int:
    print(f"\n  [중단] {message}\n")
    return 1


def _rows(src, table: str) -> list[dict]:
    cols = {r["name"] for r in src.execute(f"PRAGMA table_info({table})")}
    if not cols:
        return []
    order = "id" if "id" in cols else "rowid"
    return [dict(r) for r in src.execute(f"SELECT * FROM {table} ORDER BY {order}")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--source", default=str(config.DB_PATH))
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    print("\n  OnEnglish — 대화 기록을 Firestore 로 옮기기\n")

    if config.db_backend() != "firestore":
        return fail(
            "Firestore 설정이 없습니다.\n"
            "         .streamlit/secrets.toml 에 DB_BACKEND = \"firestore\" 를 넣어 주세요."
        )

    source = Path(args.source)
    if not source.exists():
        return fail(f"원본 파일이 없습니다: {source}")

    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    data = {t: _rows(src, t) for t in store.TABLES}

    print("  Firestore 에 연결하는 중...")
    try:
        fs.init_db()
        db = fs.client()
        existing = fs._count(db.collection("profiles"))
    except Exception as e:
        return fail(f"연결하지 못했습니다: {type(e).__name__}: {e}")
    print(f"  대상  : 프로젝트 {db.project} / DB {config.firestore_database()}")
    print(f"  원본  : {source}\n")

    if existing:
        return fail(
            f"Firestore 에 이미 프로필이 {existing}개 있습니다.\n"
            "         두 번 옮기면 기록이 섞이므로 멈춥니다."
        )

    print("  옮길 내용:")
    for table in store.TABLES:
        print(f"    {table:<13} {len(data[table]):>6}개")

    if not args.yes:
        answer = input("\n  옮길까요? (y/N) ").strip().lower()
        if answer not in ("y", "yes", "ㅛ"):
            print("\n  취소했습니다. 아무것도 바뀌지 않았어요.\n")
            return 0

    print("\n  옮기는 중...")

    # 세션 id 는 Firestore 판 규칙("프로필번호-uuid")으로 바꿉니다.
    session_owner = {s["id"]: s["profile_id"] for s in data["sessions"]}
    new_sid = {sid: f"{pid}-{sid}" for sid, pid in session_owner.items()}

    writer = _Writer(db)
    max_cid = 0
    for c in data["classes"]:
        max_cid = max(max_cid, int(c["id"]))
        writer.set(fs._class_ref(c["id"]), {
            "name": c["name"], "level": c.get("level") or "kids",
            "memo": c.get("memo"), "created_at": c["created_at"],
        })

    max_pid = 0
    for p in data["profiles"]:
        pid = int(p["id"])
        max_pid = max(max_pid, pid)
        writer.set(fs._profile_ref(pid), {
            "name": p["name"], "level": p.get("level") or "kids",
            "created_at": p["created_at"], "last_seen_at": p.get("last_seen_at"),
            "password_hash": p.get("password_hash"),
            "class_id": int(p["class_id"]) if p.get("class_id") is not None else None,
        })
        writer.set(db.collection("profile_names").document(fs._name_key(p["name"])),
                   {"profile_id": pid, "name": p["name"]})

    # 메시지 수와 아이가 말한 횟수는 세션 문서에 같이 올려둡니다.
    turns: dict[str, int] = {}
    user_turns: dict[str, int] = {}
    for m in data["messages"]:
        turns[m["session_id"]] = turns.get(m["session_id"], 0) + 1
        if m["role"] == "user":
            user_turns[m["session_id"]] = user_turns.get(m["session_id"], 0) + 1

    for s in data["sessions"]:
        writer.set(fs._session_ref(new_sid[s["id"]]), {
            "profile_id": int(s["profile_id"]), "character_id": s["character_id"],
            "started_at": s["started_at"], "ended_at": s.get("ended_at"),
            "turn_count": turns.get(s["id"], 0),
            "user_turns": user_turns.get(s["id"], 0),
        })

    # 메시지 순서는 원래 id 순서를 그대로 지킵니다.
    for order, m in enumerate(data["messages"]):
        if m["session_id"] not in new_sid:
            continue
        ref = fs._session_ref(new_sid[m["session_id"]]).collection("messages").document()
        writer.set(ref, {"role": m["role"], "content": m["content"],
                         "created_at": m["created_at"], "ts": order})

    for m in data["memories"]:
        people = m.get("people") or "[]"
        try:
            people = json.loads(people) if isinstance(people, str) else people
        except json.JSONDecodeError:
            people = []
        doc = fs.memory_doc(
            new_sid.get(m.get("session_id")), m["kind"], m["summary_ko"],
            m["summary_en"], people, m.get("sentiment"), m.get("occurred_on"),
            m.get("followup"), m.get("expires_on"), m.get("ask_after"),
            created_at=m["created_at"], opener_used_at=m.get("opener_used_at"),
        )
        writer.set(fs._memories(m["profile_id"]).document(), doc)

    for entry in data["learning_log"]:
        writer.set(fs._learning(entry["profile_id"]).document(), fs.learning_doc(
            new_sid.get(entry.get("session_id")), entry["kind"],
            entry.get("child_said"), entry.get("better_form"),
            entry.get("note_ko"), created_at=entry["created_at"],
        ))

    writer.set(db.collection("meta").document("counters"),
               {"next_profile_id": max_pid + 1, "next_class_id": max_cid + 1}, merge=True)
    try:
        writer.flush()
    except Exception as e:
        return fail(
            f"옮기다 실패했습니다: {type(e).__name__}: {e}\n"
            "         일부만 들어갔을 수 있어요. Firestore 콘솔에서 profiles 등을\n"
            "         지운 뒤 다시 실행하면 처음부터 옮깁니다."
        )

    # 확인
    print("\n  확인:")
    counts = {
        "classes": fs._count(db.collection("classes")),
        "profiles": fs._count(db.collection("profiles")),
        "sessions": sum(fs._count(fs._sessions(p["id"])) for p in data["profiles"]),
        "messages": sum(fs._count(fs._session_ref(sid).collection("messages"))
                        for sid in new_sid.values()),
        "memories": sum(fs._count(fs._memories(p["id"])) for p in data["profiles"]),
        "learning_log": sum(fs._count(fs._learning(p["id"])) for p in data["profiles"]),
    }
    ok = True
    for table in store.TABLES:
        mark = "OK" if counts[table] == len(data[table]) else "!!"
        ok = ok and mark == "OK"
        print(f"    {mark}  {table:<13} {counts[table]:>6}개")

    if not ok:
        return fail("개수가 맞지 않습니다. 위 표를 확인해 주세요.")
    print(
        "\n  다 옮겼어요. 이제 앱을 다시 실행하면 Firestore 의 기록을 씁니다.\n"
        "  원본 data/onenglish.db 는 그대로 있으니, 확인이 끝날 때까지 지우지 마세요.\n"
    )
    return 0


class _Writer:
    """Firestore 는 한 번에 500개까지 묶어서 쓸 수 있습니다. 400개씩 나눠 씁니다."""

    def __init__(self, db):
        self._db = db
        self._batch = db.batch()
        self._n = 0

    def set(self, ref, data, merge=False):
        self._batch.set(ref, data, merge=merge)
        self._n += 1
        if self._n >= 400:
            self.flush()

    def flush(self):
        if self._n:
            self._batch.commit()
        self._batch = self._db.batch()
        self._n = 0


if __name__ == "__main__":
    sys.exit(main())
