"""
Google Gemini 대화 프로바이더.

API 키 하나로 동작합니다. 서비스 계정 JSON 은 필요 없습니다.

OpenAI 와 다른 점이 몇 가지 있어서 여기서 흡수합니다.
  - 역할 이름이 assistant 가 아니라 model 입니다.
  - system 메시지가 messages 안에 들어가지 않고 systemInstruction 으로 빠집니다.
  - JSON 형식 강제는 responseSchema 로 하는데, OpenAI 의 JSON Schema 와
    문법이 조금 달라서 변환해 줍니다. 혹시 변환이 안 맞아도 앱이 멈추지
    않도록, 실패하면 스키마 없이 JSON 모드로 한 번 더 시도합니다.
"""

import json
from typing import Any

from .. import config
from ..clients import AIError, gemini_post, gemini_text
from .base import Provider, clean_history


class GeminiChatProvider(Provider):
    id = "google"
    name = "Google Gemini"

    def is_available(self) -> bool:
        return bool(config.google_api_key())

    def unavailable_reason(self) -> str:
        return config.MISSING_GOOGLE_KEY_MESSAGE

    def model_label(self) -> str:
        return config.gemini_chat_model()

    # ── 요청 만들기 ──────────────────────────────────────────────
    @staticmethod
    def _contents(history: list[dict] | None, user_text: str) -> list[dict]:
        contents = []
        for m in clean_history(history, config.max_history_turns()):
            role = "model" if m["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        contents.append({"role": "user", "parts": [{"text": user_text}]})
        return contents

    def _call(self, payload: dict) -> str:
        path = f"models/{config.gemini_chat_model()}:generateContent"
        return gemini_text(gemini_post(path, payload))

    # ── 평문 ─────────────────────────────────────────────────────
    def chat(self, system_prompt, history, user_text,
             max_tokens=160, temperature=0.85) -> str:
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": self._contents(history, user_text),
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        return self._call(payload)

    # ── JSON ─────────────────────────────────────────────────────
    def structured(self, system_prompt, user_text, schema,
                   temperature=0.2, max_tokens=600, history=None) -> dict:
        base = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": self._contents(history, user_text),
        }
        config_block = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        }

        # 1차: 스키마까지 강제
        try:
            payload = dict(base)
            payload["generationConfig"] = {
                **config_block,
                "responseSchema": to_gemini_schema(schema),
            }
            return _parse(self._call(payload))
        except AIError as e:
            if "안전" in str(e):
                raise

        # 2차: 스키마 없이 JSON 모드. 형식 설명은 프롬프트에 이미 들어있습니다.
        payload = dict(base)
        payload["generationConfig"] = config_block
        return _parse(self._call(payload))


def _parse(raw: str) -> dict:
    raw = (raw or "").strip()
    # 가끔 ```json 으로 감싸서 옵니다.
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AIError(f"응답 형식을 읽지 못했어요: {e}") from e
    if not isinstance(data, dict):
        raise AIError("응답이 객체 형태가 아니에요.")
    return data


def to_gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """JSON Schema → Gemini responseSchema.

    Gemini 는 additionalProperties 를 받지 않고, 널 허용을 type 배열이 아니라
    nullable 로 표현합니다."""
    if not isinstance(schema, dict):
        return schema

    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key in ("additionalProperties", "strict", "title", "$schema"):
            continue

        if key == "type":
            if isinstance(value, list):
                non_null = [t for t in value if t != "null"]
                out["type"] = non_null[0] if non_null else "string"
                if "null" in value:
                    out["nullable"] = True
            else:
                out["type"] = value
        elif key == "properties" and isinstance(value, dict):
            out["properties"] = {
                k: to_gemini_schema(v) for k, v in value.items()
            }
        elif key == "items":
            out["items"] = to_gemini_schema(value)
        else:
            out[key] = value
    return out
