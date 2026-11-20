"""
OpenAI 대화 프로바이더 (gpt-4o-mini 등).
"""

import json
from typing import Any

from .. import config
from ..clients import AIError, openai_client
from .base import Provider, clean_history


class OpenAIChatProvider(Provider):
    id = "openai"
    name = "OpenAI"

    def is_available(self) -> bool:
        return config.key_is_configured()

    def unavailable_reason(self) -> str:
        return config.MISSING_KEY_MESSAGE

    def model_label(self) -> str:
        return config.chat_model()

    # ── 공통 호출 ────────────────────────────────────────────────
    def _create(self, messages: list[dict], **options: Any):
        """모델마다 받는 파라미터가 다릅니다. 거부당한 것을 빼면서 재시도해서,
        나중에 모델 이름만 바꿔도 앱이 깨지지 않게 합니다."""
        model = config.chat_model()

        attempts: list[dict[str, Any]] = [dict(options)]
        if "max_tokens" in options:
            swapped = dict(options)
            swapped["max_completion_tokens"] = swapped.pop("max_tokens")
            attempts.append(swapped)
        attempts.append({
            k: v for k, v in options.items()
            if k not in ("max_tokens", "temperature", "presence_penalty")
        })

        last: Exception | None = None
        for kwargs in attempts:
            try:
                return openai_client().chat.completions.create(
                    model=model, messages=messages, **kwargs
                )
            except AIError:
                raise
            except Exception as e:
                last = e
                text = str(e).lower()
                if not any(s in text for s in (
                    "unsupported", "unrecognized", "not supported",
                    "max_tokens", "temperature",
                )):
                    break
        raise AIError(f"답변을 만드는 중 문제가 생겼어요: {last}")

    # ── 평문 ─────────────────────────────────────────────────────
    def chat(self, system_prompt, history, user_text,
             max_tokens=160, temperature=0.85) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]
        messages.extend(clean_history(history, config.max_history_turns()))
        messages.append({"role": "user", "content": user_text})

        response = self._create(
            messages, max_tokens=max_tokens, temperature=temperature,
            presence_penalty=0.4,
        )
        return (response.choices[0].message.content or "").strip()

    # ── JSON ─────────────────────────────────────────────────────
    def structured(self, system_prompt, user_text, schema,
                   temperature=0.2, max_tokens=600, history=None) -> dict:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]
        messages.extend(clean_history(history, config.max_history_turns()))
        messages.append({"role": "user", "content": user_text})

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.get("title", "result"),
                "strict": True,
                "schema": _strip_title(schema),
            },
        }
        try:
            response = self._create(
                messages, max_tokens=max_tokens, temperature=temperature,
                response_format=response_format,
            )
        except AIError:
            # 구조화 출력을 못 받는 모델이면 그냥 JSON 모드로.
            response = self._create(
                messages, max_tokens=max_tokens, temperature=temperature,
                response_format={"type": "json_object"},
            )

        raw = (response.choices[0].message.content or "").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise AIError(f"응답 형식을 읽지 못했어요: {e}") from e


def _strip_title(schema: dict) -> dict:
    out = {k: v for k, v in schema.items() if k != "title"}
    return out
