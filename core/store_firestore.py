"""
저장소 — Google Cloud Firestore 판.

core/store.py 와 함수 이름·인자·돌려주는 모양이 똑같습니다. DB_BACKEND 가
"firestore" 이면 store.py 의 공개 함수가 이 파일의 같은 이름 함수로 넘어옵니다.
그래서 app.py, memory.py 같은 나머지 코드는 어떤 DB 를 쓰는지 모릅니다.

왜 Firestore 인가: 무료 한도(하루 읽기 5만 · 쓰기 2만 · 저장 1GB)가 있어서
가족 규모로 쓰면 비용이 0 입니다. Cloud SQL 은 켜두기만 해도 요금이 나갑니다.

── 데이터 구조 ────────────────────────────────────────────────────
  profiles/{프로필번호}                    이름, 레벨, 비밀번호 해시 ...
      sessions/{프로필번호-uuid}            대화 한 번
          messages/{자동}                   말 한마디
      memories/{자동}                       생활 기억
      learning/{자동}                       학습 기록
  profile_names/{이름의 해시}              같은 이름이 두 번 생기지 않게 잡아두는 표
  meta/counters                            다음 프로필 번호

설계 원칙 — 무료 한도 안에 머무르기
  - 아이별 기록을 프로필 아래(하위 컬렉션)에 둡니다. 그러면 "최근 6개" 같은
    질의가 그 아이 것만, 딱 필요한 만큼만 읽습니다. (Firestore 는 읽은 문서
    수만큼 셉니다)
  - 복합 색인이 필요한 질의는 쓰지 않습니다. 콘솔에서 색인을 따로 만들 필요가
    없도록, 정렬 하나 또는 같음(==) 조건만 씁니다.
  - 자주 세는 값(메시지 수, 아이가 말한 횟수)은 세션 문서에 숫자로 같이
    올려둡니다. 셀 때마다 메시지를 전부 읽지 않기 위해서입니다.

ID 규칙
  - 프로필 id 는 SQLite 때처럼 정수입니다 (1, 2, 3 ...).
  - 세션 id 는 "프로필번호-uuid" 입니다. 세션 id 만 받는 함수가 많아서,
    id 안에 주인을 넣어두면 따로 찾아보는 읽기가 필요 없습니다.
  - 기억 id 는 "프로필번호:문서id" 문자열입니다. 같은 이유입니다.
"""

import hashlib
import json
import threading
import time
import uuid
from typing import Any

from . import config

_client = None
_lock = threading.Lock()
_ready = False


class FirestoreError(RuntimeError):
    """화면에 보여줄 수 있는 형태의 오류 (주로 연결 설정 문제)."""


# ── 연결 ─────────────────────────────────────────────────────────

def _credentials_and_project():
    info = config.gcp_service_account_json()
    if not info:
        return None, None  # 이 컴퓨터의 기본 인증(gcloud) 또는 에뮬레이터
    try:
        data = json.loads(info)
    except json.JSONDecodeError as e:
        raise FirestoreError(
            "GCP_SERVICE_ACCOUNT_JSON 이 올바른 JSON 이 아니에요. "
            "서비스 계정 키 파일 내용을 그대로 옮겼는지 확인해 주세요."
        ) from e
    from google.oauth2 import service_account
    credentials = service_account.Credentials.from_service_account_info(data)
    return credentials, data.get("project_id")


def client():
    global _client
    with _lock:
        if _client is None:
            try:
                from google.cloud import firestore
            except ImportError as e:
                raise FirestoreError(
                    "Firestore 를 쓰려면 패키지가 더 필요해요: "
                    "pip install -r requirements.txt"
                ) from e
            credentials, key_project = _credentials_and_project()
            project = config.firestore_project() or key_project
            try:
                _client = firestore.Client(
                    project=project,
                    credentials=credentials,
                    database=config.firestore_database(),
                )
            except Exception as e:
                if type(e).__name__ == "DefaultCredentialsError":
                    raise FirestoreError(
                        "Firestore 에 접속할 서비스 계정 키가 없어요. secrets 에 "
                        "[gcp_service_account] 를 채워 주세요."
                    ) from e
                raise
    return _client


def reset_client() -> None:
    """설정을 바꾼 뒤 다시 연결할 때 (테스트용)."""
    global _client, _ready
    with _lock:
        _client = None
        _ready = False


def _profile_ref(profile_id):
    return client().collection("profiles").document(str(int(profile_id)))


def _session_ref(session_id: str):
    profile_id = str(session_id).split("-", 1)[0]
    return _profile_ref(profile_id).collection("sessions").document(str(session_id))


def _memory_ref(memory_id: str):
    profile_id, doc_id = str(memory_id).split(":", 1)
    return _profile_ref(profile_id).collection("memories").document(doc_id)


def _name_key(name: str) -> str:
    # 문서 id 에는 '/' 같은 글자를 못 씁니다. 이름을 해시해서 씁니다.
    return hashlib.sha256(name.strip().lower().encode("utf-8")).hexdigest()


def _store():
    from . import store
    return store


def _desc():
    from google.cloud import firestore
    return firestore.Query.DESCENDING


def _eq(field: str, value):
    """같음(==) 조건. 복합 색인 없이도 되는 조건만 씁니다."""
    from google.cloud.firestore_v1.base_query import FieldFilter
    return FieldFilter(field, "==", value)


# ── 준비 ─────────────────────────────────────────────────────────

def init_db() -> None:
    """Firestore 는 테이블을 미리 만들 필요가 없습니다. 대신 처음 한 번
    접속이 되는지만 확인해서, 설정이 틀렸으면 첫 화면에서 바로 알려줍니다."""
    global _ready
    if _ready:
        return
    try:
        client().collection("meta").document("counters").get()
    except FirestoreError:
        raise
    except Exception as e:
        text = str(e)
        hint = ""
        if "PermissionDenied" in type(e).__name__ or "403" in text:
            hint = ("\n서비스 계정에 'Cloud Datastore 사용자' 역할이 있는지, "
                    "Firestore 데이터베이스를 만들었는지 확인해 주세요.")
        elif "NotFound" in type(e).__name__ or "404" in text:
            hint = ("\n이 프로젝트에 Firestore 데이터베이스가 아직 없어요. "
                    "콘솔에서 Firestore 를 '네이티브 모드'로 만들어 주세요.")
        raise FirestoreError(f"Firestore 에 연결하지 못했어요: {text}{hint}") from e
    _ready = True


# ── 프로필 ───────────────────────────────────────────────────────

def _profile_row(doc) -> dict:
    data = doc.to_dict() or {}
    return {
        "id": int(doc.id),
        "name": data.get("name"),
        "level": data.get("level", "kids"),
        "created_at": data.get("created_at"),
        "last_seen_at": data.get("last_seen_at"),
        "password_hash": data.get("password_hash"),
        "class_id": data.get("class_id"),
    }


def list_profiles() -> list[dict]:
    rows = [_profile_row(d) for d in client().collection("profiles").stream()]
    # 최근에 들어온 순서, 한 번도 안 들어온 사람은 맨 뒤 (SQLite 판과 같은 순서)
    # 같은 초에 들어왔으면 이름순 (SQLite 판의 ORDER BY ..., name 과 같게)
    seen = sorted((r for r in rows if r["last_seen_at"]), key=lambda r: r["name"] or "")
    seen.sort(key=lambda r: r["last_seen_at"], reverse=True)
    never = sorted((r for r in rows if not r["last_seen_at"]),
                   key=lambda r: r["name"] or "")
    return seen + never


def get_profile(profile_id: int) -> dict | None:
    doc = _profile_ref(profile_id).get()
    return _profile_row(doc) if doc.exists else None


def create_profile(name: str, level: str = "kids", password: str = "") -> dict:
    from google.cloud import firestore

    store = _store()
    name = name.strip()
    if not name:
        raise ValueError("이름을 입력해 주세요.")
    password = (password or "").strip()
    if not password:
        raise ValueError("비밀번호를 입력해 주세요.")

    db = client()
    counter_ref = db.collection("meta").document("counters")
    name_ref = db.collection("profile_names").document(_name_key(name))
    password_hash = store.hash_password(password)
    created_at = store.now()

    # 번호 매기기와 이름 중복 확인을 한 번에(트랜잭션) 합니다.
    # 두 사람이 동시에 같은 이름을 만들어도 하나만 성공합니다.
    @firestore.transactional
    def _create(transaction):
        if name_ref.get(transaction=transaction).exists:
            raise ValueError(f"'{name}' 은(는) 이미 있는 이름이에요.")
        counters = counter_ref.get(transaction=transaction).to_dict() or {}
        new_id = int(counters.get("next_profile_id", 1))
        transaction.set(counter_ref, {"next_profile_id": new_id + 1}, merge=True)
        transaction.set(name_ref, {"profile_id": new_id, "name": name})
        transaction.set(_profile_ref(new_id), {
            "name": name, "level": level, "created_at": created_at,
            "last_seen_at": None, "password_hash": password_hash,
        })
        return new_id

    new_id = _create(db.transaction())
    return get_profile(new_id)


def profile_has_password(profile: dict) -> bool:
    return bool(profile.get("password_hash"))


def verify_profile_password(profile_id: int, password: str) -> bool:
    doc = _profile_ref(profile_id).get()
    if not doc.exists:
        return False
    return _store().check_password(password, (doc.to_dict() or {}).get("password_hash"))


def set_profile_password(profile_id: int, password: str) -> None:
    password = (password or "").strip()
    if not password:
        raise ValueError("비밀번호를 입력해 주세요.")
    _profile_ref(profile_id).update({"password_hash": _store().hash_password(password)})


def touch_profile(profile_id: int) -> None:
    _profile_ref(profile_id).update({"last_seen_at": _store().now()})


def delete_profile(profile_id: int) -> None:
    """프로필과 그에 딸린 모든 기록을 지웁니다 (되돌릴 수 없음)."""
    ref = _profile_ref(profile_id)
    doc = ref.get()
    if doc.exists:
        name = (doc.to_dict() or {}).get("name") or ""
        client().collection("profile_names").document(_name_key(name)).delete()
    client().recursive_delete(ref)


def save_trail_result(profile_id: int, result: dict) -> None:
    from google.cloud import firestore

    profile = _profile_ref(profile_id)
    ref = profile.collection("trail_results").document(result["id"])

    @firestore.transactional
    def save(transaction):
        if not profile.get(transaction=transaction).exists:
            raise ValueError("학생 프로필을 찾을 수 없어요.")
        if not ref.get(transaction=transaction).exists:
            transaction.create(ref, {**result, "created_at": _store().now()})

    save(client().transaction())


def trail_results(profile_id: int) -> list[dict]:
    query = _profile_ref(profile_id).collection("trail_results").order_by("created_at", direction=_desc())
    return [doc.to_dict() for doc in query.stream()]


def update_profile(profile_id: int, name: str | None = None,
                   level: str | None = None) -> dict:
    """(관리자) 이름이나 레벨을 바꿉니다. 이름을 바꿀 때는 '이름 표'도 같이
    옮겨서, 같은 이름이 두 명 생기지 않게 합니다."""
    from google.cloud import firestore

    db = client()
    ref = _profile_ref(profile_id)

    @firestore.transactional
    def _update(transaction):
        doc = ref.get(transaction=transaction)
        if not doc.exists:
            raise ValueError("그 학생을 찾을 수 없어요.")
        changes = {}
        if name is not None:
            new_name = name.strip()
            if not new_name:
                raise ValueError("이름을 입력해 주세요.")
            old_name = (doc.to_dict() or {}).get("name") or ""
            old_key, new_key = _name_key(old_name), _name_key(new_name)
            if new_key != old_key:
                new_ref = db.collection("profile_names").document(new_key)
                if new_ref.get(transaction=transaction).exists:
                    raise ValueError(f"'{new_name}' 은(는) 이미 있는 이름이에요.")
                transaction.delete(db.collection("profile_names").document(old_key))
                transaction.set(new_ref, {"profile_id": int(profile_id), "name": new_name})
            changes["name"] = new_name
        if level is not None:
            changes["level"] = level
        if changes:
            transaction.update(ref, changes)

    _update(db.transaction())
    return get_profile(profile_id)


# ── 세션 ─────────────────────────────────────────────────────────

def _session_row(doc) -> dict:
    data = doc.to_dict() or {}
    turns = int(data.get("turn_count", 0))
    return {
        "id": doc.id,
        "profile_id": int(data.get("profile_id", 0)),
        "character_id": data.get("character_id"),
        "started_at": data.get("started_at"),
        "ended_at": data.get("ended_at"),
        "turn_count": turns,
        # SQLite 판의 message_count 와 같은 값입니다 (메시지마다 1씩 늘어남).
        "message_count": turns,
        "goal_id": data.get("goal_id"),
    }


def start_session(profile_id: int, character_id: str, goal_id=None) -> str:
    session_id = f"{int(profile_id)}-{uuid.uuid4()}"
    _session_ref(session_id).set({
        "profile_id": int(profile_id),
        "character_id": character_id,
        "started_at": _store().now(),
        "ended_at": None,
        "turn_count": 0,
        "user_turns": 0,
        "goal_id": None if goal_id in (None, "") else int(goal_id),
    })
    touch_profile(profile_id)
    return session_id


def end_session(session_id: str) -> None:
    ref = _session_ref(session_id)
    doc = ref.get()
    if doc.exists and not (doc.to_dict() or {}).get("ended_at"):
        ref.update({"ended_at": _store().now()})


def _sessions(profile_id: int):
    return _profile_ref(profile_id).collection("sessions")


def list_sessions(profile_id: int, limit: int = 50) -> list[dict]:
    query = _sessions(profile_id).order_by("started_at", direction=_desc()).limit(limit)
    return [_session_row(d) for d in query.stream()]


def delete_session(session_id: str) -> None:
    """(관리자) 대화 한 번을 메시지째 지웁니다."""
    client().recursive_delete(_session_ref(session_id))


def session_is_empty(session_id: str) -> bool:
    doc = _session_ref(session_id).get()
    return not doc.exists or int((doc.to_dict() or {}).get("turn_count", 0)) == 0


# ── 메시지 ───────────────────────────────────────────────────────

def add_message(session_id: str, role: str, content: str) -> None:
    from google.cloud import firestore

    if role not in ("user", "assistant"):
        raise ValueError(f"role 은 'user' 또는 'assistant' 여야 합니다: {role!r}")
    ref = _session_ref(session_id)
    batch = client().batch()
    batch.set(ref.collection("messages").document(), {
        "role": role,
        "content": content,
        "created_at": _store().now(),
        # 같은 초에 두 마디가 저장돼도 순서가 섞이지 않게 나노초를 씁니다.
        "ts": time.time_ns(),
    })
    counts = {"turn_count": firestore.Increment(1)}
    if role == "user":
        counts["user_turns"] = firestore.Increment(1)
    batch.update(ref, counts)
    batch.commit()


def get_messages(session_id: str) -> list[dict]:
    query = _session_ref(session_id).collection("messages").order_by("ts")
    rows = []
    for doc in query.stream():
        data = doc.to_dict() or {}
        rows.append({"role": data.get("role"), "content": data.get("content"),
                     "created_at": data.get("created_at")})
    return rows


# ── 생활 기억 ────────────────────────────────────────────────────

def _memories(profile_id: int):
    return _profile_ref(profile_id).collection("memories")


def _memory_row(profile_id, doc) -> dict:
    data = doc.to_dict() or {}
    return {
        "id": f"{int(profile_id)}:{doc.id}",
        "profile_id": int(profile_id),
        "session_id": data.get("session_id"),
        "kind": data.get("kind"),
        "summary_ko": data.get("summary_ko"),
        "summary_en": data.get("summary_en"),
        "people": list(data.get("people") or []),
        "sentiment": data.get("sentiment"),
        "occurred_on": data.get("occurred_on"),
        "created_at": data.get("created_at"),
        "followup": data.get("followup"),
        "expires_on": data.get("expires_on"),
        "opener_used_at": data.get("opener_used_at"),
        "ask_after": data.get("ask_after"),
    }


def memory_doc(
    session_id, kind, summary_ko, summary_en, people=None, sentiment=None,
    occurred_on=None, followup=None, expires_on=None, ask_after=None,
    created_at=None, opener_used_at=None,
) -> dict:
    """기억 문서 한 개. 이전 스크립트도 같은 모양으로 넣으려고 함수로 뺐습니다."""
    store = _store()
    followup = (followup or "").strip() or None
    return {
        "session_id": session_id,
        "kind": kind,
        "summary_ko": summary_ko,
        "summary_en": summary_en,
        # 대소문자 무시 중복 검사용 (Firestore 는 lower() 질의가 없어서)
        "summary_en_lower": (summary_en or "").strip().lower(),
        "people": list(people or []),
        "sentiment": sentiment,
        "occurred_on": occurred_on or store.today(),
        "created_at": created_at or store.now(),
        "followup": followup,
        "expires_on": (expires_on or "").strip() or None,
        "ask_after": (ask_after or "").strip() or None,
        "opener_used_at": opener_used_at,
        # 아직 물어보지 않은 이야깃거리만 빨리 고르기 위한 표시
        "followup_open": bool(followup) and not opener_used_at,
    }


def add_memory(
    profile_id: int,
    session_id: str | None,
    kind: str,
    summary_ko: str,
    summary_en: str,
    people: list[str] | None = None,
    sentiment: str | None = None,
    occurred_on: str | None = None,
    followup: str | None = None,
    expires_on: str | None = None,
    ask_after: str | None = None,
) -> None:
    _memories(profile_id).document().set(memory_doc(
        session_id, kind, summary_ko, summary_en, people, sentiment,
        occurred_on, followup, expires_on, ask_after,
    ))


def recent_memories(profile_id: int, limit: int = 6) -> list[dict]:
    query = _memories(profile_id).order_by("created_at", direction=_desc()).limit(limit)
    return [_memory_row(profile_id, d) for d in query.stream()]


def all_memories(profile_id: int, limit: int = 200) -> list[dict]:
    return recent_memories(profile_id, limit)


def delete_memory(memory_id) -> None:
    _memory_ref(memory_id).delete()


def live_followups(profile_id: int, limit: int = 5) -> list[dict]:
    """다음에 만나면 물어볼 만한 것들. 조건과 순서는 SQLite 판과 같습니다.
    아직 묻지 않은 것(followup_open)만 읽은 뒤, 날짜 조건은 여기서 거릅니다."""
    day = _store().today()
    rows = [
        _memory_row(profile_id, d)
        for d in _memories(profile_id).where(filter=_eq("followup_open", True)).stream()
    ]
    rows = [
        r for r in rows
        if (r["followup"] or "").strip()
        and (r["created_at"] or "")[:10] < day
        and (not r["ask_after"] or r["ask_after"] <= day)
        and (not r["expires_on"] or r["expires_on"] >= day)
        and not r["opener_used_at"]
    ]
    # 곧 만료되는 것부터, 만료일 없는 것은 뒤로. 같으면 최근 것부터.
    rows.sort(key=lambda r: r["created_at"] or "", reverse=True)
    rows.sort(key=lambda r: (r["expires_on"] is None, r["expires_on"] or ""))
    return rows[:limit]


def recent_openers(profile_id: int, character_id: str, limit: int = 4) -> list[str]:
    """이 캐릭터가 최근에 했던 첫 마디들 (최신순)."""
    query = _sessions(profile_id).order_by("started_at", direction=_desc()).limit(20)
    openers = []
    for doc in query.stream():
        if (doc.to_dict() or {}).get("character_id") != character_id:
            continue
        first = list(doc.reference.collection("messages").order_by("ts").limit(1).stream())
        if first:
            data = first[0].to_dict() or {}
            if data.get("role") == "assistant":
                openers.append(data.get("content"))
        if len(openers) >= limit:
            break
    return openers


def mark_opener_used(memory_id) -> None:
    _memory_ref(memory_id).update({
        "opener_used_at": _store().now(),
        "followup_open": False,
    })


def days_since_last_chat(profile_id: int) -> int | None:
    from datetime import datetime

    query = _sessions(profile_id).order_by("started_at", direction=_desc()).limit(50)
    for doc in query.stream():
        data = doc.to_dict() or {}
        if int(data.get("turn_count", 0)) > 1 and data.get("started_at"):
            try:
                last = datetime.fromisoformat(data["started_at"]).date()
            except ValueError:
                return None
            return (datetime.now().date() - last).days
    return None


def orphan_sessions(profile_id: int, min_messages: int = 3) -> list[dict]:
    rows = [
        _session_row(d)
        for d in _sessions(profile_id).where(filter=_eq("ended_at", None)).stream()
    ]
    rows = [r for r in rows if r["turn_count"] >= min_messages]
    return sorted(rows, key=lambda r: r["started_at"] or "")


def memory_exists(profile_id: int, summary_en: str) -> bool:
    query = (_memories(profile_id)
             .where(filter=_eq("summary_en_lower", summary_en.strip().lower()))
             .limit(1))
    return any(True for _ in query.stream())


# ── 학습 기록 ────────────────────────────────────────────────────

def _learning(profile_id: int):
    return _profile_ref(profile_id).collection("learning")


def learning_doc(session_id, kind, child_said=None, better_form=None,
                 note_ko=None, created_at=None) -> dict:
    return {
        "session_id": session_id,
        "kind": kind,
        "child_said": child_said,
        "better_form": better_form,
        "note_ko": note_ko,
        "created_at": created_at or _store().now(),
    }


def add_learning_entry(
    profile_id: int,
    session_id: str | None,
    kind: str,
    child_said: str | None = None,
    better_form: str | None = None,
    note_ko: str | None = None,
) -> None:
    _learning(profile_id).document().set(
        learning_doc(session_id, kind, child_said, better_form, note_ko)
    )


def _learning_row(profile_id, doc) -> dict:
    data = doc.to_dict() or {}
    return {"id": f"{int(profile_id)}:{doc.id}", "profile_id": int(profile_id),
            **{k: data.get(k) for k in ("session_id", "kind", "child_said",
                                         "better_form", "note_ko", "created_at")}}


def delete_learning_entry(entry_id) -> None:
    """(관리자) 학습 기록 한 줄을 지웁니다. id 는 "프로필번호:문서id"."""
    profile_id, doc_id = str(entry_id).split(":", 1)
    _learning(profile_id).document(doc_id).delete()


def recent_learning(profile_id: int, limit: int = 100) -> list[dict]:
    query = _learning(profile_id).order_by("created_at", direction=_desc()).limit(limit)
    return [_learning_row(profile_id, d) for d in query.stream()]


def frequent_mistakes(profile_id: int, limit: int = 10) -> list[dict]:
    """반복되는 실수를 많은 순으로. 부모용 화면에서만 씁니다."""
    groups: dict[str, dict[str, Any]] = {}
    for doc in _learning(profile_id).where(filter=_eq("kind", "mistake")).stream():
        data = doc.to_dict() or {}
        better = data.get("better_form")
        if not better:
            continue
        g = groups.setdefault(better.lower(), {
            "better_form": better, "note_ko": None, "times": 0, "last_seen": "",
        })
        g["times"] += 1
        g["better_form"] = min(g["better_form"], better)
        if data.get("note_ko") and (g["note_ko"] is None or data["note_ko"] > g["note_ko"]):
            g["note_ko"] = data["note_ko"]
        g["last_seen"] = max(g["last_seen"], data.get("created_at") or "")
    rows = sorted(groups.values(), key=lambda g: g["last_seen"], reverse=True)
    rows.sort(key=lambda g: g["times"], reverse=True)
    return rows[:limit]


# ── 통계 ─────────────────────────────────────────────────────────

def _count(query) -> int:
    """문서를 전부 읽지 않고 개수만 셉니다 (1,000개당 읽기 1회로 계산됨)."""
    result = query.count().get()
    return int(result[0][0].value)


def profile_stats(profile_id: int) -> dict[str, Any]:
    sessions = _sessions(profile_id)
    try:
        child_turns = int(sessions.sum("user_turns").get()[0][0].value or 0)
    except AttributeError:  # 아주 오래된 SDK
        child_turns = sum(int((d.to_dict() or {}).get("user_turns", 0))
                          for d in sessions.stream())
    return {
        "sessions": _count(sessions),
        "child_turns": child_turns,
        "memories": _count(_memories(profile_id)),
        "learning": _count(_learning(profile_id)),
    }


# ── 반 ───────────────────────────────────────────────────────────
#   classes/{반번호}   이름, 레벨, 메모
# 반 번호도 프로필처럼 meta/counters 로 매깁니다. 반은 몇 개 안 되므로 이름 중복은
# 전체를 읽어 확인합니다 (읽기 몇 번이면 충분).

def _class_ref(class_id):
    return client().collection("classes").document(str(int(class_id)))


def _class_row(doc) -> dict:
    data = doc.to_dict() or {}
    return {"id": int(doc.id), "name": data.get("name"), "level": data.get("level", "kids"),
            "memo": data.get("memo"), "created_at": data.get("created_at")}


def list_classes() -> list[dict]:
    rows = [_class_row(d) for d in client().collection("classes").stream()]
    return sorted(rows, key=lambda r: r["name"] or "")


def get_class(class_id) -> dict | None:
    if class_id in (None, ""):
        return None
    doc = _class_ref(class_id).get()
    return _class_row(doc) if doc.exists else None


def _class_name_taken(name: str, except_id=None) -> bool:
    key = name.strip().lower()
    return any((c["name"] or "").strip().lower() == key and c["id"] != except_id
               for c in list_classes())


def create_class(name: str, level: str, memo: str = "") -> dict:
    from google.cloud import firestore

    name = (name or "").strip()
    if not name:
        raise ValueError("반 이름을 입력해 주세요.")
    if _class_name_taken(name):
        raise ValueError(f"'{name}' 반이 이미 있어요.")
    db = client()
    counter_ref = db.collection("meta").document("counters")

    @firestore.transactional
    def _create(transaction):
        counters = counter_ref.get(transaction=transaction).to_dict() or {}
        new_id = int(counters.get("next_class_id", 1))
        transaction.set(counter_ref, {"next_class_id": new_id + 1}, merge=True)
        transaction.set(_class_ref(new_id), {
            "name": name, "level": level, "memo": (memo or "").strip() or None,
            "created_at": _store().now(),
        })
        return new_id

    return get_class(_create(db.transaction()))


def update_class(class_id, name: str | None = None, level: str | None = None,
                 memo: str | None = None) -> dict:
    changes = {}
    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError("반 이름을 입력해 주세요.")
        if _class_name_taken(name, except_id=int(class_id)):
            raise ValueError(f"'{name}' 반이 이미 있어요.")
        changes["name"] = name
    if level is not None:
        changes["level"] = level
    if memo is not None:
        changes["memo"] = memo.strip() or None
    if get_class(class_id) is None:
        raise ValueError("그 반을 찾을 수 없어요.")
    if changes:
        _class_ref(class_id).update(changes)
    return get_class(class_id)


def delete_class(class_id) -> None:
    """반을 지웁니다. 그 반 학생들은 '반 없음'이 됩니다."""
    db = client()
    batch = db.batch()
    for doc in db.collection("profiles").where(filter=_eq("class_id", int(class_id))).stream():
        batch.update(doc.reference, {"class_id": None})
    batch.delete(_class_ref(class_id))
    batch.commit()


def set_profile_class(profile_id: int, class_id) -> None:
    if class_id in (None, ""):
        _profile_ref(profile_id).update({"class_id": None})
        return
    if get_class(class_id) is None:
        raise ValueError("그 반을 찾을 수 없어요.")
    _profile_ref(profile_id).update({"class_id": int(class_id)})


# ── 학습 목표 ────────────────────────────────────────────────────
#   goals/{목표번호}            대상(반/학생), 기간, 주제, 단어, 표현, 과제
#   goal_results/{대화 id}      그 대화의 목표 결과 (대화 id 가 문서 id 라 덮어쓰기 쉬움)
# 목표는 몇 개 안 되므로 목록은 전부 읽습니다. 결과는 같음(==) 조건으로 찾습니다.

def _goal_ref(goal_id):
    return client().collection("goals").document(str(int(goal_id)))


def _goal_row(doc) -> dict:
    data = doc.to_dict() or {}
    return {"id": int(doc.id), **{k: data.get(k) for k in _store().GOAL_FIELDS},
            "words": list(data.get("words") or []),
            "expressions": list(data.get("expressions") or []),
            "created_at": data.get("created_at")}


def list_goals() -> list[dict]:
    rows = [_goal_row(d) for d in client().collection("goals").stream()]
    rows.sort(key=lambda g: g["id"], reverse=True)
    rows.sort(key=lambda g: g["start_on"] or "", reverse=True)
    return rows


def get_goal(goal_id) -> dict | None:
    if goal_id in (None, ""):
        return None
    doc = _goal_ref(goal_id).get()
    return _goal_row(doc) if doc.exists else None


def create_goal(**fields) -> dict:
    from google.cloud import firestore

    g = _store()._check_goal(fields)
    db = client()
    counter_ref = db.collection("meta").document("counters")

    @firestore.transactional
    def _create(transaction):
        counters = counter_ref.get(transaction=transaction).to_dict() or {}
        new_id = int(counters.get("next_goal_id", 1))
        transaction.set(counter_ref, {"next_goal_id": new_id + 1}, merge=True)
        transaction.set(_goal_ref(new_id), {**g, "created_at": _store().now()})
        return new_id

    return get_goal(_create(db.transaction()))


def update_goal(goal_id, **fields) -> dict:
    current = get_goal(goal_id)
    if current is None:
        raise ValueError("그 목표를 찾을 수 없어요.")
    g = _store()._check_goal({**{k: current.get(k) for k in _store().GOAL_FIELDS}, **fields})
    _goal_ref(goal_id).update(g)
    return get_goal(goal_id)


def delete_goal(goal_id) -> None:
    db = client()
    batch = db.batch()
    for doc in db.collection("goal_results").where(filter=_eq("goal_id", int(goal_id))).stream():
        batch.delete(doc.reference)
    batch.delete(_goal_ref(goal_id))
    batch.commit()
    # 대화 쪽의 goal_id 는 지우지 않아도 됩니다 (목표가 없으면 그냥 무시됨).


def _result_row(doc) -> dict:
    data = doc.to_dict() or {}
    td = data.get("task_done")
    return {"session_id": doc.id, "goal_id": data.get("goal_id"),
            "profile_id": data.get("profile_id"),
            "words_used": list(data.get("words_used") or []),
            "words_heard": list(data.get("words_heard") or []),
            "task_done": None if td is None else bool(td),
            "achieved": bool(data.get("achieved")), "note": data.get("note"),
            "updated_at": data.get("updated_at")}


def save_goal_result(session_id: str, goal_id, profile_id: int, words_used: list,
                     words_heard: list, task_done, achieved: bool,
                     note: str | None = None) -> None:
    client().collection("goal_results").document(str(session_id)).set({
        "goal_id": int(goal_id), "profile_id": int(profile_id),
        "words_used": list(words_used), "words_heard": list(words_heard),
        "task_done": None if task_done is None else bool(task_done),
        "achieved": bool(achieved), "note": note, "updated_at": _store().now(),
    })


def goal_results_for_goal(goal_id) -> list[dict]:
    docs = client().collection("goal_results").where(filter=_eq("goal_id", int(goal_id))).stream()
    return sorted((_result_row(d) for d in docs), key=lambda r: r["updated_at"] or "")


def goal_results_for_profile(profile_id: int) -> list[dict]:
    docs = client().collection("goal_results").where(
        filter=_eq("profile_id", int(profile_id))).stream()
    return sorted((_result_row(d) for d in docs), key=lambda r: r["updated_at"] or "",
                  reverse=True)
