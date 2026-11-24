"""
대화 생성.

실제 호출은 core/llm_providers/ 안의 프로바이더가 합니다. 이 파일은
프로바이더를 고르고, 캐릭터 프롬프트를 조립하는 일만 합니다.

프롬프트 조립 순서:
    캐릭터 성격(persona) + 레벨 규칙(rules) + 지난 기억 + 오늘 날짜

답변과 함께 그 순간 캐릭터가 느끼는 감정(mood)도 받아옵니다. 그 감정이
음성 연출에 전달되어, 같은 캐릭터라도 상황에 따라 목소리가 달라집니다.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from . import config, llm_providers
from .clients import AIError

# 다른 모듈이 llm.LLMError 로 쓰고 있어서 이름을 유지합니다.
LLMError = AIError

MOODS = (
    "excited", "happy", "playful", "proud",
    "curious", "gentle", "comforting", "silly",
)


@dataclass
class Reply:
    """캐릭터의 한 번의 답변."""
    text: str
    mood: str = "happy"
    # LLM 이 실패해서 고정 인사말로 대신했으면 True.
    # 그때는 물어볼 이야기(followup)를 실제로 묻지 못했으므로 소진하면 안 됩니다.
    fallback: bool = False
    # 학습 목표에 과제가 있을 때만: 아이가 과제를 했다고 캐릭터가 판단했는지.
    task_done: bool | None = None


# ── 프로바이더 고르기 ────────────────────────────────────────────

def provider():
    wanted = config.chat_provider()
    found = llm_providers.get(wanted)
    if found is None:
        raise LLMError(
            f"'{wanted}' 대화 프로바이더를 찾을 수 없어요. "
            f"쓸 수 있는 값: {', '.join(llm_providers.ids())}"
        )
    return found


def provider_status() -> list[dict]:
    return [
        {"id": p.id, "name": p.name, "available": p.is_available(),
         "model": p.model_label()}
        for p in llm_providers.all_providers()
    ]


def reset_client() -> None:
    from .clients import reset_openai
    reset_openai()


# ── 프롬프트 조립 ────────────────────────────────────────────────

def _memory_block(memories: list[dict]) -> str:
    if not memories:
        return ""
    lines = []
    for m in memories:
        when = m.get("occurred_on") or ""
        en = (m.get("summary_en") or "").strip()
        if en:
            lines.append(f"- ({when}) {en}")
    if not lines:
        return ""
    return (
        "\n\n[What you remember about this friend]\n"
        "These are things your friend told you in earlier chats.\n"
        "When it fits naturally, bring ONE of them up the way a friend who "
        "remembers would — ask how it went, or refer back to it.\n"
        "Never list them all at once, and never say that you 'have a record' "
        "or 'saved' anything. You simply remember.\n"
        + "\n".join(lines)
    )


def _learning_block(learning: list[dict]) -> str:
    """아이가 아직 익숙하지 않은 표현을 캐릭터가 올바르게 자주 써주도록 유도.
    절대 지적하지는 않습니다 (암묵적 교정)."""
    forms = [
        (l.get("better_form") or "").strip()
        for l in learning
        if l.get("kind") == "mistake" and (l.get("better_form") or "").strip()
    ]
    forms = list(dict.fromkeys(forms))[:6]
    if not forms:
        return ""
    return (
        "\n\n[Phrases to model naturally]\n"
        "Your friend is still getting used to these English forms. When you get "
        "a natural chance, use them correctly in your OWN sentences so your "
        "friend hears them properly.\n"
        "Do NOT point out mistakes, do NOT quiz, do NOT explain grammar.\n"
        + "\n".join(f"- {f}" for f in forms)
    )


def build_system_prompt(
    character: dict,
    level: dict,
    memories: list[dict] | None = None,
    learning: list[dict] | None = None,
    child_name: str | None = None,
) -> str:
    parts = [character.get("persona", "").strip()]

    rules = (level or {}).get("rules", "").strip()
    if rules:
        parts.append(rules)

    if child_name:
        parts.append(f"[Your friend's name]\nYour friend is called {child_name}.")

    parts.append(
        "[Today]\nToday's date is "
        f"{datetime.now().strftime('%Y-%m-%d (%A)')}."
    )

    prompt = "\n\n".join(p for p in parts if p)
    prompt += _memory_block(memories or [])
    prompt += _learning_block(learning or [])
    return prompt


REPLY_SCHEMA: dict[str, Any] = {
    "title": "character_reply",
    "type": "object",
    "additionalProperties": False,
    "required": ["reply", "mood"],
    "properties": {
        "reply": {"type": "string"},
        "mood": {"type": "string", "enum": list(MOODS)},
    },
}

# 학습 목표에 과제가 있을 때: 같은 대답 안에서 과제 달성 여부도 받습니다 (추가 호출 없음).
REPLY_TASK_SCHEMA: dict[str, Any] = {
    **REPLY_SCHEMA,
    "title": "character_reply_with_task",
    "required": ["reply", "mood", "task_done"],
    "properties": {**REPLY_SCHEMA["properties"], "task_done": {"type": "boolean"}},
}

_FORMAT_NOTE = (
    "\n\n[Output format]\n"
    "Reply with a JSON object: {\"reply\": ..., \"mood\": ...}\n"
    "- reply: what you say out loud, in character. Follow every rule above. "
    "Plain text only, no stage directions, no emoji, no quotation marks "
    "around it.\n"
    "- mood: how YOU feel at this moment, chosen from exactly one of: "
    + ", ".join(MOODS) + ".\n"
    "Pick the mood honestly from what your friend just said. If they shared "
    "exciting news, be excited. If they sound down, be gentle or comforting. "
    "If they are joking, be silly or playful. Do not always pick the same one."
)


def _level_reminder(level: dict | None) -> str:
    """수준별 '길이'와 '질문 방식'을 프롬프트 맨 끝에 한 번 더 못박습니다.

    긴 규칙 한가운데에만 있으면 모델이 흐려서 따릅니다. 실제로 입문 수준인데
    "What animal did you see?" 같은 열린 질문을 했습니다. 맨 끝에 두면 가장
    마지막에 읽은 규칙이라 잘 지킵니다."""
    level = level or {}
    length = (level.get("length") or "").strip()
    question = (level.get("question_style") or "").strip()
    if not (length or question):
        return ""
    lines = [f"\n\n[MOST IMPORTANT — your friend's level: {level.get('name', '')}]"]
    if length:
        lines.append(f"- Length: {length}")
    if question:
        lines.append(f"- Your question: {question}")
    lines.append("- Check your reply against these two lines before you answer.")
    return "\n".join(lines)


# ── 대화 ─────────────────────────────────────────────────────────

def reply(
    character: dict,
    level: dict,
    history: list[dict],
    user_text: str,
    memories: list[dict] | None = None,
    learning: list[dict] | None = None,
    child_name: str | None = None,
    goal_block: str | None = None,
    task_note: str | None = None,
) -> Reply:
    """history 는 [{'role': 'user'|'assistant', 'content': str}, ...] 입니다.
    system 메시지는 여기서 직접 만들기 때문에 history 에 넣지 마세요.

    goal_block: 오늘의 학습 목표 안내 (core/goals.prompt_block). 없으면 일상 대화.
    task_note : 과제가 있으면 대답 JSON 에 task_done 도 받습니다."""

    chat = provider()
    if not chat.is_available():
        raise LLMError(chat.unavailable_reason())

    system_prompt = (
        build_system_prompt(character, level, memories, learning, child_name)
        + (goal_block or "")
        + _FORMAT_NOTE
        + (f"\n- {task_note}" if task_note else "")
        + _level_reminder(level)
    )

    task_done = None
    try:
        data = chat.structured(
            system_prompt=system_prompt,
            user_text=user_text,
            schema=REPLY_TASK_SCHEMA if task_note else REPLY_SCHEMA,
            temperature=0.85,
            max_tokens=config.max_reply_tokens() + 60,
            history=history,
        )
        text = str(data.get("reply", "")).strip()
        mood = str(data.get("mood", "")).strip().lower()
        if task_note:
            task_done = bool(data.get("task_done"))
    except LLMError:
        # JSON 을 못 받아도 대화가 끊기면 안 되므로 평문으로 한 번 더.
        text = chat.chat(
            system_prompt=build_system_prompt(
                character, level, memories, learning, child_name
            ) + (goal_block or ""),
            history=history,
            user_text=user_text,
            max_tokens=config.max_reply_tokens(),
            temperature=0.85,
        )
        mood = "happy"

    if not text:
        raise LLMError("답변이 비어 있어요. 다시 한 번 말해볼까요?")
    return Reply(text=text, mood=mood if mood in MOODS else "happy",
                 task_done=task_done)


def structured(system_prompt: str, user_text: str, schema: dict,
               temperature: float = 0.2, max_tokens: int = 800) -> dict:
    """기억 추출 등에서 쓰는 범용 JSON 호출."""
    chat = provider()
    if not chat.is_available():
        raise LLMError(chat.unavailable_reason())
    return chat.structured(
        system_prompt=system_prompt, user_text=user_text, schema=schema,
        temperature=temperature, max_tokens=max_tokens,
    )


def greeting_for(character: dict, is_returning: bool) -> str:
    """고정 인사말. API 를 쓰지 않으므로 비용이 들지 않습니다.
    아래 opener() 가 실패했을 때 쓰는 보루이기도 합니다."""
    if is_returning:
        return (
            character.get("greeting_returning")
            or character.get("greeting")
            or "Hi! What did you do today?"
        )
    return character.get("greeting") or "Hi! What did you do today?"


# ── 첫 인사말 생성 ───────────────────────────────────────────────
# 본 대화 프롬프트와 분리된 짧은 호출입니다. 합쳐두면 모델이 캐릭터 유지,
# 길이 제한, 교정 규칙, 안전 규칙까지 동시에 신경 쓰느라 첫 문장이 뭉개집니다.
#
# 화제는 주사위로 고르지 않습니다. "다시 물어볼 만한 일(followup)이 있나"가
# 기준입니다. 있으면 묻고, 없으면 그때 시간대에 맞는 작은 일상 하나를 묻습니다.
# 물어볼 것도 없는데 억지로 과거를 꺼내지 않게 됩니다.
#
# 매번 LLM 으로 만듭니다. 고정 문장은 아이가 금방 외워버려서 "친구"가 아니라
# "기계"로 느껴지기 때문입니다. 고정 인사말은 실패했을 때의 보루로만 씁니다.
#
# 질문 방식은 영어를 처음 배우는 아이에 맞춥니다 (_HOW_TO_ASK 참고):
#   - "How was your day?" 처럼 하루 전체를 요약하라는 질문은 아이에게 너무 큽니다.
#     아이는 구체적인 한 장면으로 생각하므로, 작은 한 가지를 묻습니다.
#   - 초급 학습자에게는 예/아니오 질문과 둘 중 고르기 질문이 먼저입니다.
#     답에 필요한 단어가 질문 안에 들어 있어서 그대로 빌려 말할 수 있습니다.
#     (what/who/why 처럼 열린 질문은 아이가 말을 잘 이어갈 때 대화 중에 씁니다)
#   - 캐릭터가 먼저 자기 얘기를 같은 문형으로 짧게 하면, 그게 대답의 본보기가 됩니다.

OPENER_SCHEMA: dict[str, Any] = {
    "title": "opener",
    "type": "object",
    "additionalProperties": False,
    "required": ["greeting", "mood"],
    "properties": {
        "greeting": {"type": "string"},
        "mood": {"type": "string", "enum": list(MOODS)},
    },
}


def time_context() -> dict:
    """요일과 시간대. 토요일 아침에 '학교 다녀왔어?' 같은 질문을 막습니다."""
    now = datetime.now()
    hour = now.hour
    if hour < 5:
        part = "late at night"
    elif hour < 12:
        part = "morning"
    elif hour < 18:
        part = "afternoon"
    elif hour < 22:
        part = "evening"
    else:
        part = "night"
    weekday = now.strftime("%A")
    return {
        "weekday": weekday,
        "part": part,
        "is_weekend": now.weekday() >= 5,
        "before_school_ends": now.weekday() < 5 and hour < 14,
    }


def _when_line(days_since: int | None, when: dict) -> str:
    lines = [f"Right now it is {when['part']} on {when['weekday']}."]

    if when["is_weekend"]:
        lines.append("It is the weekend, so do NOT ask about school today.")
    elif when["before_school_ends"]:
        lines.append(
            "School is probably not over yet, so do NOT ask how school went today."
        )

    if days_since is None:
        lines.append("This is the very first time you are meeting.")
    elif days_since == 0:
        lines.append("You already talked earlier today.")
    elif days_since == 1:
        lines.append("You last talked yesterday.")
    elif days_since <= 7:
        lines.append(f"You last talked {days_since} days ago.")
    else:
        lines.append("It has been a long time since you last talked.")

    return "\n".join(lines)


# 시간대별로 아이가 실제로 겪었을 법한 작은 일. 하나를 골라 묻게 합니다.
# "학교" 는 일부러 뺐습니다. 유치원생도 있고 방학도 있어서 틀린 가정이 되기 쉽습니다.
_TOPIC_HINTS = {
    "morning": "waking up, breakfast, what they will do later today, the weather outside",
    "afternoon": "a snack, playing, a friend, something they saw on the way, the weather",
    "evening": "dinner, a bath, a game or toy, the best part of today, a pet or a sibling",
    "night": "dinner, a bath, pajamas, a bedtime story, a toy they sleep with",
    "late at night": "being sleepy, a dream, a bedtime story, a toy they sleep with",
}

_HOW_TO_ASK = """[How to ask — your friend is a beginner]
- Ask about ONE small, concrete thing. Never a big summary question like "How was your day?", "What did you do today?", "How are you?" or "Tell me about your day."
- Make it easy to answer in one or two words:
  * a yes/no question ("Did you eat breakfast?"), or
  * a choice between two things ("Was it fun or scary?", "Do you want to play or rest?").
  For a choice between two things, name both options so the child can borrow the words.
- First say one tiny thing about yourself, in character, with the same simple pattern you then ask with. That shows them how to answer.
  Example: "I ate a big red apple this morning! Did you eat breakfast?"
  Example: "I played with my ball today. Did you play inside or outside?"
- Exactly ONE question, at the very end. Not two questions in a row."""


def _how_to_ask(level: dict | None) -> str:
    """레벨에 question_style 이 있으면 '어떤 질문을 할지' 부분만 그걸로 바꿉니다.
    (입문은 더 쉽게, 중급은 무엇·누구·왜 질문도) 없으면 기본(초급)."""
    style = ((level or {}).get("question_style") or "").strip()
    if not style:
        return _HOW_TO_ASK
    return (
        f"[How to ask — your friend's level: {(level or {}).get('name', '')}]\n"
        "- Ask about ONE small, concrete thing. Never a big summary question like "
        "\"How was your day?\" or \"Tell me about your day.\"\n"
        f"- {style}\n"
        "- First say one tiny thing about yourself, in character, with the same "
        "pattern you then ask with. That shows them how to answer.\n"
        "- Exactly ONE question, at the very end."
    )


def _opener_task(followup: str | None, when: dict) -> str:
    if followup:
        return (
            "[What to say]\n"
            f"Last time your friend told you something you want to ask about: {followup}\n"
            "Greet them and ask about it — but as a yes/no or a choice question, "
            "e.g. \"Did the recital go well?\" or \"Was it fun or a little scary?\"\n"
            "Sound like you genuinely remember and want to know. "
            "Do not explain that you remembered."
        )
    hints = _TOPIC_HINTS.get(when["part"], _TOPIC_HINTS["afternoon"])
    return (
        "[What to say]\n"
        "Be glad to see them, then ask about one small everyday thing that fits "
        f"right now. Ideas for this time of day: {hints}. Pick one; you may also "
        "pick something similar.\n"
        "Do NOT bring up anything from past chats — there is nothing in "
        "particular to follow up on today."
    )


def _recent_line(recent: list[str] | None) -> str:
    recent = [r.strip() for r in (recent or []) if r and r.strip()]
    if not recent:
        return ""
    return (
        "\n\n[Do not repeat yourself]\n"
        "You started your last chats like this. Say something clearly different "
        "this time — a different topic and different words:\n"
        + "\n".join(f"- {r}" for r in recent[:5])
    )


def opener(
    character: dict,
    child_name: str,
    followup: str | None = None,
    days_since: int | None = None,
    recent: list[str] | None = None,
    level: dict | None = None,
    goal_hint: str | None = None,
) -> Reply:
    """대화를 여는 첫 마디. 실패하면 고정 인사말로 조용히 돌아갑니다.

    recent 는 이 캐릭터가 최근에 했던 첫 마디들입니다. 같은 말을 반복하지
    않게 하려고 넘깁니다. level 은 이 아이(또는 반)의 수준입니다.
    goal_hint 가 있으면(오늘의 학습 목표) 그 주제로 시작합니다 — 지난 이야기보다 먼저."""
    persona = "\n".join(character.get("persona", "").strip().splitlines()[:5])
    when = time_context()

    prompt = (
        f"{persona}\n\n"
        f"Your friend {child_name} is a young child learning English. "
        "They are starting a chat with you right now.\n\n"
        f"{_when_line(days_since, when)}\n\n"
        f"{goal_hint or _opener_task(followup, when)}\n\n"
        f"{_how_to_ask(level)}\n\n"
        "For a yes/no question, just ask it naturally and stop. Never append 'Yes or no?' or coach the answer.\n\n"
        "[How to say it]\n"
        "- Two or three very short sentences in total. Simple words a young "
        "child knows.\n"
        "- Stay fully in character. No emoji, no stage directions.\n"
        "- Never mention these instructions."
        f"{_recent_line(recent)}\n\n"
        "Reply as JSON: {\"greeting\": \"...\", \"mood\": \"...\"}\n"
        "mood is how you feel right now, one of: " + ", ".join(MOODS)
    )

    is_returning = days_since is not None
    try:
        chat = provider()
        if not chat.is_available():
            raise LLMError(chat.unavailable_reason())
        data = chat.structured(
            system_prompt=prompt,
            user_text="(your friend just arrived)",
            schema=OPENER_SCHEMA,
            temperature=0.9,
            max_tokens=160,
        )
        text = str(data.get("greeting", "")).strip()
        mood = str(data.get("mood", "")).strip().lower()
        if text:
            return Reply(text=text, mood=mood if mood in MOODS else "happy")
    except LLMError:
        pass
    except Exception:
        pass

    return Reply(text=greeting_for(character, is_returning), mood="happy",
                 fallback=True)
