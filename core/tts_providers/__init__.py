"""
음성 합성 프로바이더 레지스트리.

새 프로바이더를 추가하려면:
  1. base.Provider 를 상속한 파일을 이 폴더에 만들고
  2. 아래 _REGISTRY 에 한 줄 추가
그게 전부입니다. core/tts.py 와 app.py 는 수정하지 않습니다.
"""

from .base import Direction, Provider, Voice, clean_for_speech  # noqa: F401
from .google_tts import GoogleProvider
from .openai_tts import OpenAIProvider

_REGISTRY: dict[str, Provider] = {
    OpenAIProvider.id: OpenAIProvider(),
    GoogleProvider.id: GoogleProvider(),
}

DEFAULT_ID = OpenAIProvider.id

# 마지막 호출 기록. 목소리가 이상할 때 "실제로 어떤 조건으로 나갔는지"
# 확인하는 용도입니다.
LAST_CALL: dict = {
    "provider": None, "model": None, "voice": None,
    "mode": None, "used_instructions": None, "instructions": None,
}


def record_call(**kwargs) -> None:
    LAST_CALL.update(kwargs)


def all_providers() -> list[Provider]:
    return list(_REGISTRY.values())


def get(provider_id: str) -> Provider | None:
    return _REGISTRY.get((provider_id or "").strip().lower())


def ids() -> list[str]:
    return list(_REGISTRY)
