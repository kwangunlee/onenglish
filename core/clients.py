"""
외부 AI 서비스 호출의 공통 바닥.

여기에 모아둔 이유: 대화(llm), 음성인식(stt), 음성합성(tts)이 모두 같은
서비스를 쓰는데, 각자 클라이언트를 만들면 키를 바꿨을 때 일부만 갱신되는
문제가 생깁니다. 실제로 그 문제를 겪어서 한 곳으로 모았습니다.

키가 바뀌면 클라이언트를 새로 만듭니다.
"""

from typing import Any

import requests

from . import config


class AIError(RuntimeError):
    """사용자에게 그대로 보여줄 수 있는 형태의 오류."""


# ── OpenAI ───────────────────────────────────────────────────────

_openai_client = None
_openai_key = ""


def openai_client():
    from openai import OpenAI

    global _openai_client, _openai_key

    key = config.openai_api_key()
    if not config.key_is_configured():
        raise AIError(config.MISSING_KEY_MESSAGE)

    if _openai_client is None or _openai_key != key:
        _openai_client = OpenAI(api_key=key)
        _openai_key = key
    return _openai_client


def reset_openai() -> None:
    global _openai_client, _openai_key
    _openai_client = None
    _openai_key = ""


# ── Google Gemini ────────────────────────────────────────────────
# SDK 를 쓰지 않고 REST 로 직접 부릅니다. 의존성을 늘리지 않기 위해서이고,
# API 키 하나만 있으면 되기 때문입니다. (서비스 계정 JSON 불필요)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT = 90


def gemini_post(path: str, payload: dict[str, Any]) -> dict:
    """Gemini REST 호출. path 예: 'models/gemini-2.0-flash:generateContent'"""
    key = config.google_api_key()
    if not key:
        raise AIError(config.MISSING_GOOGLE_KEY_MESSAGE)

    try:
        response = requests.post(
            f"{GEMINI_BASE}/{path}",
            params={"key": key},
            json=payload,
            timeout=TIMEOUT,
        )
    except Exception as e:
        raise AIError(f"Google 서버에 연결하지 못했어요: {e}") from e

    if response.status_code != 200:
        raise AIError(_gemini_error(response))

    try:
        return response.json()
    except ValueError as e:
        raise AIError(f"Google 응답을 읽지 못했어요: {e}") from e


def gemini_get(path: str, params: dict | None = None) -> dict:
    key = config.google_api_key()
    if not key:
        raise AIError(config.MISSING_GOOGLE_KEY_MESSAGE)
    try:
        response = requests.get(
            f"{GEMINI_BASE}/{path}",
            params={"key": key, **(params or {})},
            timeout=TIMEOUT,
        )
    except Exception as e:
        raise AIError(f"Google 서버에 연결하지 못했어요: {e}") from e
    if response.status_code != 200:
        raise AIError(_gemini_error(response))
    return response.json()


def _gemini_error(response) -> str:
    try:
        error = response.json().get("error", {})
        detail = error.get("message", "")
        status = error.get("status", "")
    except Exception:
        detail, status = (response.text or "")[:300], ""

    code = response.status_code

    # "API key not valid" 는 400 으로 오는데 내용은 키 문제입니다.
    # 400 을 "요청이 잘못됐어요" 로만 안내하면 원인을 찾기 어려워서 먼저 거릅니다.
    looks_like_key = any(
        s in detail.lower() for s in
        ("api key not valid", "api_key_invalid", "invalid api key",
         "api key expired", "api keys are not supported")
    )

    if looks_like_key:
        return (
            "Google API 키가 올바르지 않아요.\n"
            "  이 키로는 Gemini 를 쓸 수 없습니다. 보통 아래 둘 중 하나입니다.\n"
            "  · 음성합성(Text-to-Speech) 전용으로 만든 키인 경우\n"
            "  · Generative Language API 가 꺼져 있는 경우\n"
            "\n"
            "  가장 쉬운 해결: https://aistudio.google.com/apikey 에서\n"
            "  'Create API key' 로 새 키를 받아 GOOGLE_API_KEY 에 넣으세요.\n"
            "  (AI Studio 키는 Gemini 가 처음부터 켜져 있습니다)\n"
            f"\n  (원문: {detail})"
        )

    if code in (401, 403) or status == "PERMISSION_DENIED":
        return (
            "Google API 키가 거부됐어요.\n"
            "  · Generative Language API 가 사용 설정되어 있는지\n"
            "  · API 키 제한에 그 API 가 허용되어 있는지\n"
            "  확인해 주세요.\n"
            "  사용 설정: https://console.cloud.google.com/apis/library/"
            "generativelanguage.googleapis.com\n"
            f"  (원문: {detail})"
        )
    if code == 404 or status == "NOT_FOUND":
        return (
            "그 모델을 찾을 수 없어요. 모델 이름이 바뀌었을 수 있습니다.\n"
            "  쓸 수 있는 모델 보기:\n"
            "    python tools/check_google.py --models\n"
            f"  (원문: {detail})"
        )
    if code == 429 or status == "RESOURCE_EXHAUSTED":
        return "Google 사용량 한도를 넘었어요. 잠시 뒤에 다시 시도해 주세요."
    if code == 400:
        return f"Google 요청이 잘못됐어요: {detail}"
    return f"Google 호출 실패 (HTTP {code}): {detail}"


def gemini_text(result: dict) -> str:
    """generateContent 응답에서 텍스트만 꺼냅니다."""
    candidates = result.get("candidates") or []
    if not candidates:
        feedback = result.get("promptFeedback", {})
        blocked = feedback.get("blockReason")
        if blocked:
            raise AIError(
                "안전 설정 때문에 답변이 막혔어요. 다른 말로 해볼까요? "
                f"({blocked})"
            )
        raise AIError("Google 이 답변을 돌려주지 않았어요.")

    first = candidates[0]
    if first.get("finishReason") == "SAFETY":
        raise AIError("안전 설정 때문에 답변이 막혔어요. 다른 말로 해볼까요?")

    parts = (first.get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()
