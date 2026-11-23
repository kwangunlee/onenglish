"""
이 컴퓨터의 대화 기록(data/onenglish.db, SQLite)을 Google Cloud SQL 로 옮깁니다.

    python tools/migrate_to_cloudsql.py

먼저 .streamlit/secrets.toml 에 Cloud SQL 설정(CLOUD_SQL_INSTANCE 등)을 채워야
합니다. 앱과 같은 설정을 읽어서 같은 DB 에 넣습니다.

안전장치
  - 원본 SQLite 파일은 읽기만 하고 고치지 않습니다.
  - Cloud SQL 쪽에 이미 프로필이 있으면 멈춥니다. (두 번 옮겨서 섞이는 것 방지)
  - 옮기기 전에 몇 개를 옮길지 보여주고 물어봅니다. (--yes 로 건너뛰기)
  - 전부 한 번에(트랜잭션) 넣습니다. 중간에 실패하면 아무것도 들어가지 않습니다.

옵션
  --source 경로   다른 SQLite 파일에서 옮길 때
  --yes           묻지 않고 바로 옮기기
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

from core import config, store  # noqa: E402


def fail(message: str) -> int:
    print(f"\n  [중단] {message}\n")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--source", default=str(config.DB_PATH))
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    print("\n  OnEnglish — 대화 기록을 Cloud SQL 로 옮기기\n")

    backend = config.db_backend()
    if backend == "sqlite":
        return fail(
            "Cloud SQL 설정이 없습니다.\n"
            "         .streamlit/secrets.toml 에 CLOUD_SQL_INSTANCE 를 채워 주세요."
        )

    source = Path(args.source)
    if not source.exists():
        return fail(f"원본 파일이 없습니다: {source}")

    target = config.cloud_sql_instance() or f"{config.db_host()}:{config.db_port()}"
    print(f"  원본  : {source}")
    print(f"  대상  : {target} / DB {config.db_name()} (사용자 {config.db_user()})\n")

    # 원본은 읽기 전용으로 엽니다.
    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row

    print("  Cloud SQL 에 연결하는 중...")
    try:
        store.init_db()  # 테이블이 없으면 만듭니다.
        with store.connect() as conn:
            existing = conn.execute("SELECT COUNT(*) AS n FROM profiles").fetchone()["n"]
            target_cols = {
                table: [r["column_name"] for r in conn.execute(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_schema = current_schema() AND table_name = ?"
                    " ORDER BY ordinal_position", (table,)
                )]
                for table in store.TABLES
            }
    except Exception as e:
        return fail(f"연결하지 못했습니다: {type(e).__name__}: {e}")

    if existing:
        return fail(
            f"Cloud SQL 에 이미 프로필이 {existing}개 있습니다.\n"
            "         두 번 옮기면 기록이 섞이므로 멈춥니다."
        )

    plan = []
    for table in store.TABLES:
        source_cols = [r["name"] for r in src.execute(f"PRAGMA table_info({table})")]
        if not source_cols:
            plan.append((table, [], []))
            continue
        # 옛 버전 DB 에는 없는 컬럼이 있을 수 있어, 양쪽에 다 있는 컬럼만 옮깁니다.
        cols = [c for c in source_cols if c in target_cols[table]]
        rows = src.execute(
            f"SELECT {', '.join(cols)} FROM {table} ORDER BY rowid"
        ).fetchall()
        plan.append((table, cols, rows))

    print("  옮길 내용:")
    for table, _, rows in plan:
        print(f"    {table:<13} {len(rows):>6}개")

    if not args.yes:
        answer = input("\n  옮길까요? (y/N) ").strip().lower()
        if answer not in ("y", "yes", "ㅛ"):
            print("\n  취소했습니다. 아무것도 바뀌지 않았어요.\n")
            return 0

    print("\n  옮기는 중...")
    try:
        with store.connect() as conn:
            for table, cols, rows in plan:
                if not rows:
                    continue
                sql = (
                    f"INSERT INTO {table} ({', '.join(cols)})"
                    f" VALUES ({', '.join('?' for _ in cols)})"
                )
                for row in rows:
                    conn.execute(sql, tuple(row))
            for table in store.IDENTITY_TABLES:
                store.reset_identity(conn, table)
    except Exception as e:
        return fail(
            f"옮기다 실패했습니다: {type(e).__name__}: {e}\n"
            "         한 번에 넣는 방식이라 Cloud SQL 에는 아무것도 들어가지 않았어요."
        )

    # 확인
    with store.connect() as conn:
        print("\n  확인:")
        ok = True
        for table, _, rows in plan:
            n = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            mark = "OK" if n == len(rows) else "!!"
            ok = ok and n == len(rows)
            print(f"    {mark}  {table:<13} {n:>6}개")

    if not ok:
        return fail("개수가 맞지 않습니다. 위 표를 확인해 주세요.")
    print(
        "\n  다 옮겼어요. 이제 앱을 다시 실행하면 Cloud SQL 의 기록을 씁니다.\n"
        "  원본 data/onenglish.db 는 그대로 있으니, 확인이 끝날 때까지 지우지 마세요.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
