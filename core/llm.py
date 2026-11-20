"""
대화 생성 (OpenAI Chat).

프롬프트 조립 순서:
    캐릭터 성격(persona) + 레벨 규칙(rules) + 지난 기억 + 오늘 날짜

중요: AI 응답은 반드시 role='assistant' 로 쌓습니다. 예전 버전에서 'system' 으로
쌓아 대화가 길어질수록 캐릭터 설정이 희석되던 버그를 고친 부분입니다.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from openai import OpenAI

from . import config

# 캐릭터가 그 순간 느끼는 감정. 음성 연출에 그대로 쓰입니다.
MOODS = (
    "excited", "happy", "playful", "proud",
    "curious", "gentle", "comforting", "silly",
)


@dataclass
class Reply:
    """캐릭터의 한 번의 답변."""
    text: str
    mood: str = "happy"

_client: OpenAI | None = None


class LLMError(RuntimeError):
    """사용자에게 보여줄 수 있는 형태의 오류."""


def client() -> OpenAI:
    global _client
    if _client is None:
        if not config.key_is_configured():
            raise LLMError(config.MISSING_KEY_MESSAGE)
        _client = OpenAI(api_key=config.openai_api_key())
    return _client


def reset_client() -> None:
    """키를 바꿨을 때 호출."""
    global _client
    _client = None


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
    """아이가 아직 익숙하지 않은 표현을 캐릭터가 '올바르게 자주 써주도록' 유도.
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


# ── 모델 호출 (파라미터 호환 처리) ───────────────────────────────

def create_completion(messages: list[dict], **options: Any):
    """chat.completions.create 호출.

    모델마다 받는 파라미터가 다릅니다. 예를 들어 추론 계열 모델은 max_tokens 와
    temperature 를 거부합니다. 나중에 secrets 에서 CHAT_MODEL 만 바꿔도 앱이
    깨지지 않도록, 거부당한 파라미터를 하나씩 빼면서 다시 시도합니다.
    """
    model = config.chat_model()

    attempts: list[dict[str, Any]] = [dict(options)]

    # max_tokens -> max_completion_tokens 로 바꾼 버전
    if "max_tokens" in options:
        swapped = dict(options)
        swapped["max_completion_tokens"] = swapped.pop("max_tokens")
        attempts.append(swapped)

    # 선택적 파라미터를 모두 뺀 최소 버전
    minimal = {
        k: v for k, v in options.items()
        if k not in ("max_tokens", "temperature", "presence_penalty")
    }
    attempts.append(minimal)

    last_error: Exception | None = None
    for kwargs in attempts:
        try:
            return client().chat.completions.create(
                model=model, messages=messages, **kwargs
            )
        except LLMError:
            raise
        except Exception as e:
            last_error = e
            text = str(e).lower()
            retryable = any(
                s in text for s in
                ("unsupported", "unrecognized", "not supported",
                 "invalid_request_error", "max_tokens", "temperature")
            )
            if not retryable:
                break

    raise LLMError(f"답변을 만드는 중 문제가 생겼어요: {last_error}")


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
    system 메시지는 여기서 직접 만들기 때문에 history 에 넣지 마세요.

    답변 텍스트와 함께 그 순간 캐릭터가 느끼는 감정(mood)도 받아옵니다.
    mood 는 음성 연출에 그대로 전달되어, 같은 캐릭터라도 상황에 따라 목소리가
    달라지게 합니다. 호출은 한 번뿐이라 추가 비용은 거의 없습니다."""

    system_prompt = build_system_prompt(
        character, level, memories, learning, child_name
    )
    system_prompt += (
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

    trimmed = _trim_history(history, config.max_history_turns())

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    messages.extend(trimmed)
    messages.append({"role": "user", "content": user_text})

    response = create_completion(
        messages,
        max_tokens=config.max_reply_tokens() + 40,  # JSON 포장 여유분
        temperature=0.85,
        presence_penalty=0.4,
        response_format={"type": "json_schema", "json_schema": _REPLY_SCHEMA},
    )

    raw = (response.choices[0].message.content or "").strip()
    text, mood = _parse_reply(raw)
    if not text:
        raise LLMError("답변이 비어 있어요. 다시 한 번 말해볼까요?")
    return Reply(text=text, mood=mood)


_REPLY_SCHEMA = {
    "name": "character_reply",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["reply", "mood"],
        "properties": {
            "reply": {"type": "string"},
            "mood": {"type": "string", "enum": list(MOODS)},
        },
    },
}


def _parse_reply(raw: str) -> tuple[str, str]:
    """JSON 으로 오는 게 정상이지만, 모델을 바꿔 쓰다 평문이 와도 깨지지 않게
    처리합니다. 대화가 음성 연출 때문에 멈추면 안 되니까요."""
    try:
        data = json.loads(raw)
        text = str(data.get("reply", "")).strip()
        mood = str(data.get("mood", "")).strip().lower()
        if text:
            return text, (mood if mood in MOODS else "happy")
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass
    return raw, "happy"


def _trim_history(history: list[dict], max_turns: int) -> list[dict]:
    """최근 max_turns 쌍만 남깁니다. role 이 이상한 항목은 버립니다."""
    clean = [
        {"role": m["role"], "content": m["content"]}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    keep = max_turns * 2
    return clean[-keep:] if keep > 0 else clean


def greeting_for(character: dict, is_returning: bool) -> str:
    """첫 인사. API 를 쓰지 않으므로 비용이 들지 않습니다."""
    if is_returning:
        return (
            character.get("greeting_returning")
            or character.get("greeting")
            or "Hi! What did you do today?"
        )
    return character.get("greeting") or "Hi! What did you do today?"
