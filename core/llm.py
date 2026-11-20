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


# ── 대화 ─────────────────────────────────────────────────────────

def reply(
    character: dict,
    level: dict,
    history: list[dict],
    user_text: str,
    memories: list[dict] | None = None,
    learning: list[dict] | None = None,
    child_name: str | None = None,
) -> Reply:
    """history 는 [{'role': 'user'|'assistant', 'content': str}, ...] 입니다.
    system 메시지는 여기서 직접 만들기 때문에 history 에 넣지 마세요."""

    chat = provider()
    if not chat.is_available():
        raise LLMError(chat.unavailable_reason())

    system_prompt = build_system_prompt(
        character, level, memories, learning, child_name
    ) + _FORMAT_NOTE

    try:
        data = chat.structured(
            system_prompt=system_prompt,
            user_text=user_text,
            schema=REPLY_SCHEMA,
            temperature=0.85,
            max_tokens=config.max_reply_tokens() + 60,
            history=history,
        )
        text = str(data.get("reply", "")).strip()
        mood = str(data.get("mood", "")).strip().lower()
    except LLMError:
        # JSON 을 못 받아도 대화가 끊기면 안 되므로 평문으로 한 번 더.
        text = chat.chat(
            system_prompt=build_system_prompt(
                character, level, memories, learning, child_name
            ),
            history=history,
            user_text=user_text,
            max_tokens=config.max_reply_tokens(),
            temperature=0.85,
        )
        mood = "happy"

    if not text:
        raise LLMError("답변이 비어 있어요. 다시 한 번 말해볼까요?")
    return Reply(text=text, mood=mood if mood in MOODS else "happy")


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
    """첫 인사. API 를 쓰지 않으므로 비용이 들지 않습니다."""
    if is_returning:
        return (
            character.get("greeting_returning")
            or character.get("greeting")
            or "Hi! What did you do today?"
        )
    return character.get("greeting") or "Hi! What did you do today?"
