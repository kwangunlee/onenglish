"""
대화 프로바이더 레지스트리.

새 프로바이더를 추가하려면 파일 하나 만들고 아래에 한 줄 더하면 됩니다.
core/llm.py 와 app.py 는 수정하지 않습니다.
"""

from .base import Provider, clean_history  # noqa: F401
from .gemini_chat import GeminiChatProvider
from .openai_chat import OpenAIChatProvider

_REGISTRY: dict[str, Provider] = {
    OpenAIChatProvider.id: OpenAIChatProvider(),
    GeminiChatProvider.id: GeminiChatProvider(),
}

DEFAULT_ID = OpenAIChatProvider.id


def get(provider_id: str) -> Provider | None:
    return _REGISTRY.get((provider_id or "").strip().lower())


def all_providers() -> list[Provider]:
    return list(_REGISTRY.values())


def ids() -> list[str]:
    return list(_REGISTRY)
