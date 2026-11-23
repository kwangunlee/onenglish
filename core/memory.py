"""
기억 (생활 기억 + 학습 기록).

대화가 끝나면 대화 전체를 한 번 더 읽어서 구조화된 정보만 뽑아 저장합니다.
다음 대화를 시작할 때 그 기억이 캐릭터 프롬프트에 주입되어, 캐릭터가 지난 일을
먼저 꺼낼 수 있게 됩니다.

두 종류를 뽑습니다.
  - 생활 기억(memories): 활동 / 사람 / 좋아하는 것 / 사건
      → 다음 대화에서 캐릭터가 자연스럽게 언급
  - 학습 기록(learning): 반복되는 실수 / 새로 쓴 표현
      → 캐릭터가 올바른 형태를 자연스럽게 더 많이 쓰도록 유도 + 부모용 리포트

structured outputs(json_schema, strict)를 쓰기 때문에 형식이 어긋나는 응답이
나오지 않습니다. 파싱 실패로 기억을 날리는 일이 없습니다.
"""

import json

from . import config, store
from .llm import LLMError, structured

MIN_CHILD_TURNS = 2  # 이보다 짧은 대화는 뽑을 게 없으므로 API 를 쓰지 않습니다.

_SCHEMA = {
    "title": "conversation_notes",
    **{
        "type": "object",
        "additionalProperties": False,
        "required": ["memories", "learning"],
        "properties": {
            "memories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "kind", "summary_ko", "summary_en",
                        "people", "sentiment", "occurred_on",
                        "upcoming_on", "followup", "expires_on",
                    ],
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": ["activity", "person", "favorite",
                                     "event", "other"],
                        },
                        "summary_ko": {"type": "string"},
                        "summary_en": {"type": "string"},
                        "people": {"type": "array", "items": {"type": "string"}},
                        "sentiment": {
                            "type": "string",
                            "enum": ["fun", "happy", "excited", "proud",
                                     "tired", "sad", "neutral"],
                        },
                        "occurred_on": {"type": ["string", "null"]},
                        "upcoming_on": {"type": ["string", "null"]},
                        "followup": {"type": ["string", "null"]},
                        "expires_on": {"type": ["string", "null"]},
                    },
                },
            },
            "learning": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "child_said", "better_form", "note_ko"],
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": ["mistake", "new_expression"],
                        },
                        "child_said": {"type": ["string", "null"]},
                        "better_form": {"type": ["string", "null"]},
                        "note_ko": {"type": ["string", "null"]},
                    },
                },
            },
        },
    },
}

_INSTRUCTIONS = """You are reviewing a chat between a young child learning English and a friendly character.

Pull out two kinds of notes.

[memories] — things worth remembering about the CHILD's life, so the character can bring them up next time like a friend who remembers.
- Only what the child actually said. Never invent or infer beyond what was stated.
- One entry per distinct fact. Keep each one short.
- summary_en must be a short plain English phrase written in the third person, e.g. "had a snowball fight with friends", "favorite food is tteokbokki", "has a puppy named Kkomi".
- summary_ko is the same thing in short natural Korean, e.g. "친구들과 눈싸움을 했다".
- people: names or words the child used for people involved, in the child's own words. Empty list if none.
- occurred_on: "YYYY-MM-DD" for something that ALREADY happened, if the child indicated when ("today" = today, "yesterday" = the day before). null for things that have not happened yet, or if unclear.
- upcoming_on: "YYYY-MM-DD" for something that has NOT happened yet, read from "Next 7 days" in the calendar. Example: today is Monday and the child says "my recital is on Saturday" -> the Saturday listed under "Next 7 days". "tomorrow" = the first day under "Next 7 days". null if it already happened or no day was given.
- followup: ONLY if this is something a friend would naturally ask about again next time — an open thread. Write it as a short instruction, e.g. "ask how the piano recital went", "ask if the loose tooth came out". Use null for closed facts that need no follow-up (favorites, traits, things already finished and fully told).
- expires_on: "YYYY-MM-DD" after which the follow-up would feel stale. A week after the event is usually right; a few days for small things. null if there is no follow-up.
- Skip small talk, greetings, and anything the character said about itself.
- Do NOT record anything about the child's health conditions, family conflict, money, or anything a parent would consider private or distressing. If the child mentioned something worrying, leave it out entirely.
- Return an empty list if there is nothing worth remembering. An empty list is a perfectly good answer.

[learning] — English the child is still getting used to.
- kind "mistake": the child used a form incorrectly. child_said = roughly what they wrote or said. better_form = the natural correct version, short. note_ko = a one-line explanation in Korean for a parent.
- kind "new_expression": the child used something notably well or for the first time. better_form = that expression.
- At most 4 entries. Pick the most useful ones. Skip spelling slips from speech recognition.
- Return an empty list if nothing stands out.

Respond only with the JSON object."""


def _calendar() -> str:
    """오늘 날짜와 요일, 앞뒤 일주일의 날짜.

    아이는 "토요일에 발표회 해", "어제 수영 갔어" 처럼 요일로 말합니다. 날짜만
    주면 모델이 요일을 날짜로 바꾸지 못해 엉뚱한 날을 고릅니다.
    (실제로 월요일에 '토요일 발표회'를 듣고 화요일에 물으려 했습니다)
    다가오는 일이 먼저 보이도록 '앞으로 7일'을 먼저 적습니다."""
    from datetime import date, timedelta

    today = date.fromisoformat(store.today())
    lines = [f"Today is {today.isoformat()} ({today:%A})."]
    past = [f"{d:%A} {d.isoformat()}" for d in
            (today - timedelta(days=n) for n in range(7, 0, -1))]
    coming = [f"{d:%A} {d.isoformat()}" for d in
              (today + timedelta(days=n) for n in range(1, 8))]
    lines.append("Next 7 days: " + ", ".join(coming))
    lines.append("Past 7 days: " + ", ".join(past))
    lines.append("When the child names a weekday, map it to the right date above.")
    return "\n".join(lines)


def followup_window(occurred_on: str | None, expires_on: str | None,
                    has_followup: bool) -> tuple[str | None, str | None]:
    """다시 물어도 되는 기간 (ask_after, expires_on) 을 코드로 정합니다.

    모델은 "그 일이 언제인지"(occurred_on)만 고르고, 날짜 계산은 여기서 합니다.
    모델에게 "그다음 날"까지 계산시키면 자주 틀렸기 때문입니다.
      - ask_after : 그 일이 끝난 다음 날. 이미 지난 일이거나 날짜가 없으면 내일.
                    (같은 날에는 절대 묻지 않음)
      - expires_on: ask_after 로부터 최소 3일은 남게. 모델 값이 없으면 7일 뒤.
    """
    from datetime import date, timedelta

    if not has_followup:
        return None, None
    today = date.fromisoformat(store.today())
    ask = today + timedelta(days=1)
    try:
        event = date.fromisoformat((occurred_on or "").strip()[:10])
        ask = max(ask, event + timedelta(days=1))
    except ValueError:
        pass
    try:
        expires = date.fromisoformat((expires_on or "").strip()[:10])
    except ValueError:
        expires = ask + timedelta(days=7)
    expires = max(expires, ask + timedelta(days=3))
    return ask.isoformat(), expires.isoformat()


def _transcript(messages: list[dict], child_name: str) -> str:
    lines = []
    for m in messages:
        who = child_name if m["role"] == "user" else "Character"
        lines.append(f"{who}: {m['content']}")
    return "\n".join(lines)


def extract(messages: list[dict], child_name: str = "The child") -> dict:
    """대화에서 기억과 학습 기록을 뽑습니다. 저장은 하지 않습니다."""
    child_turns = sum(1 for m in messages if m["role"] == "user")
    if child_turns < MIN_CHILD_TURNS:
        return {"memories": [], "learning": []}

    user_text = (
        f"{_calendar()}\n"
        f"The child is called {child_name}.\n\n"
        f"--- chat ---\n{_transcript(messages, child_name)}"
    )

    try:
        data = structured(
            system_prompt=_INSTRUCTIONS,
            user_text=user_text,
            schema=_SCHEMA,
            temperature=0.2,
            max_tokens=900,
        )
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"기억을 정리하는 중 문제가 생겼어요: {e}") from e

    return {
        "memories": data.get("memories") or [],
        "learning": data.get("learning") or [],
    }


def extract_and_save(
    profile_id: int,
    session_id: str | None,
    messages: list[dict],
    child_name: str = "The child",
) -> dict:
    """뽑아서 바로 저장합니다. 저장된 개수를 돌려줍니다.

    실패해도 예외를 던지지 않습니다. 기억 저장은 부가 기능이고, 이것 때문에
    대화 종료가 막히면 안 됩니다."""
    result = {"memories": 0, "learning": 0, "error": None}

    try:
        notes = extract(messages, child_name)
    except LLMError as e:
        result["error"] = str(e)
        return result

    for m in notes["memories"]:
        summary_en = (m.get("summary_en") or "").strip()
        summary_ko = (m.get("summary_ko") or "").strip()
        if not summary_en or not summary_ko:
            continue
        if store.memory_exists(profile_id, summary_en):
            continue
        followup = (m.get("followup") or "").strip() or None
        # 다가오는 일이면 그 날짜, 이미 지난 일이면 일어난 날짜를 기준으로 계산
        ask_after, expires_on = followup_window(
            m.get("upcoming_on") or m.get("occurred_on"), m.get("expires_on"),
            has_followup=bool(followup),
        )
        store.add_memory(
            profile_id=profile_id,
            session_id=session_id,
            kind=m.get("kind") or "other",
            summary_ko=summary_ko,
            summary_en=summary_en,
            people=m.get("people") or [],
            sentiment=m.get("sentiment"),
            # 다가오는 일은 그 일의 날짜를 적어둡니다 (기록 화면·대화 맥락용)
            occurred_on=m.get("occurred_on") or m.get("upcoming_on") or None,
            followup=followup,
            expires_on=expires_on,
            ask_after=ask_after,
        )
        result["memories"] += 1

    for l in notes["learning"]:
        better = (l.get("better_form") or "").strip()
        said = (l.get("child_said") or "").strip()
        if not better and not said:
            continue
        store.add_learning_entry(
            profile_id=profile_id,
            session_id=session_id,
            kind=l.get("kind") or "mistake",
            child_said=said or None,
            better_form=better or None,
            note_ko=(l.get("note_ko") or "").strip() or None,
        )
        result["learning"] += 1

    return result


def sweep_orphans(profile_id: int, child_name: str) -> dict:
    """끝맺지 못하고 버려진 대화에서 기억을 건져냅니다.

    아이가 '대화 끝내기' 를 누르지 않고 창을 닫거나, 배터리가 나가거나,
    브라우저가 죽으면 그 대화의 기억이 통째로 사라집니다. 그런 세션은
    ended_at 이 비어 있으므로 찾아낼 수 있습니다.

    다음에 그 아이가 들어올 때 한 번 돌립니다. 버려진 대화가 없으면
    아무 일도 하지 않으므로 평소에는 비용이 들지 않습니다."""
    result = {"sessions": 0, "memories": 0, "learning": 0}

    for session in store.orphan_sessions(profile_id):
        messages = store.get_messages(session["id"])
        saved = extract_and_save(
            profile_id=profile_id,
            session_id=session["id"],
            messages=messages,
            child_name=child_name,
        )
        # 추출에 실패해도 세션은 닫습니다. 안 그러면 들어올 때마다 같은
        # 대화를 다시 시도하면서 비용만 나갑니다.
        store.end_session(session["id"])
        result["sessions"] += 1
        result["memories"] += saved["memories"]
        result["learning"] += saved["learning"]

    return result


def opener_followup(profile_id: int) -> tuple[str | None, int | None]:
    """이번에 꺼낼 만한 이야깃거리 하나. 없으면 (None, None).

    '떡볶이를 좋아한다' 같은 닫힌 사실은 followup 이 비어 있어서 걸리지
    않습니다. 물어볼 게 있을 때만 묻기 위한 구분입니다."""
    rows = store.live_followups(profile_id, limit=5)
    if not rows:
        return None, None
    first = rows[0]
    return (first.get("followup") or "").strip() or None, first["id"]


def recall(profile_id: int) -> tuple[list[dict], list[dict]]:
    """다음 대화에 주입할 기억과 학습 기록."""
    memories = store.recent_memories(profile_id, config.memory_recall_count())
    learning = store.recent_learning(profile_id, 30)
    return memories, learning
