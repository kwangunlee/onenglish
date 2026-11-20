"""
텍스트 → 음성.

실제 합성은 core/tts_providers/ 안의 프로바이더가 합니다. 이 파일은 어떤
프로바이더를 쓸지 고르고 넘겨주는 역할만 합니다.

프로바이더 선택 순서:
  1. 캐릭터 정의의 "tts_provider"   (캐릭터마다 다르게 쓸 수 있음)
  2. 설정의 TTS_PROVIDER
  3. 기본값 (openai)

지금 쓸 수 있는 프로바이더:
  openai  gpt-4o-mini-tts  연기 지시를 반영 → 생기 있음, 음색이 미세하게 흔들림
  google  Chirp3-HD 등     텍스트와 속도만 → 음색이 일정함, 톤 변화 없음

성격이 정반대라서 어느 쪽이 낫다고 말하기 어렵습니다. 캐릭터별로 섞어 쓸 수도
있습니다 (예: 차분한 캐릭터는 google, 활발한 캐릭터는 openai).
"""

from . import config, tts_providers
from .tts_providers import Direction, clean_for_speech  # noqa: F401  (외부 호환)
from .tts_providers.openai_tts import MOOD_DIRECTION  # noqa: F401  (외부 호환)

# 마지막 호출 기록 (tts_providers.LAST_CALL 과 같은 객체)
LAST_CALL = tts_providers.LAST_CALL


def resolve_provider(character: dict | None = None):
    """이 캐릭터에 쓸 프로바이더를 고릅니다."""
    from .llm import LLMError

    wanted = ""
    if character:
        wanted = (character.get("tts_provider") or "").strip().lower()
    if not wanted:
        wanted = config.tts_provider()

    provider = tts_providers.get(wanted)
    if provider is None:
        raise LLMError(
            f"'{wanted}' 음성 프로바이더를 찾을 수 없어요. "
            f"쓸 수 있는 값: {', '.join(tts_providers.ids())}"
        )
    return provider


def provider_status() -> list[dict]:
    """설정 확인용. 각 프로바이더가 지금 쓸 수 있는 상태인지."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "available": p.is_available(),
            "supports_direction": p.supports_direction,
            "voice_field": p.voice_field,
        }
        for p in tts_providers.all_providers()
    ]


def voice_for(character: dict) -> str:
    """이 캐릭터가 지금 프로바이더에서 쓸 목소리 이름."""
    provider = resolve_provider(character)
    return provider.voice_for(character)


def synthesize(
    text: str,
    voice: str = "",
    voice_instruction: str = "",
    rate: float = 1.0,
    mood: str = "",
    scene: str = "",
    character: dict | None = None,
) -> bytes:
    """읽어줄 mp3 바이트를 반환합니다.

    character 를 넘기면 그 캐릭터에 맞는 프로바이더와 목소리를 알아서 고릅니다.
    voice 를 직접 넘기면 그 값이 우선합니다 (목소리 비교 도구에서 사용)."""
    from .llm import LLMError

    provider = resolve_provider(character)

    if not provider.is_available():
        raise LLMError(provider.unavailable_reason())

    if not voice and character:
        voice = provider.voice_for(character)
        if not voice:
            raise LLMError(
                f"{character.get('name', '이 캐릭터')} 에 {provider.name} 목소리가 "
                f"지정되지 않았어요. characters.json 의 "
                f'"{provider.voice_field}" 값을 채워 주세요.'
            )

    direction = Direction(
        instruction=voice_instruction or (character or {}).get("voice_instruction", ""),
        mood=mood,
        scene=scene,
        rate=rate,
    )
    return provider.synthesize(text, voice, direction)
