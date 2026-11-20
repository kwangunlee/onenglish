"""
음성 → 텍스트 (OpenAI Whisper).

예전 버전의 Google Cloud Speech 스트리밍을 대체합니다. 바뀐 점:
  - 자격증명 JSON 파일이 필요 없습니다 (OpenAI 키 하나로 끝)
  - 5분 스트리밍 제한이 없습니다
  - pyaudio 가 필요 없습니다 (브라우저가 녹음)
  - 실시간 중간 결과는 없습니다. 녹음을 멈춘 뒤 한 번에 인식합니다.

언어는 기본적으로 자동 감지입니다. 아이가 한국어로 말해도 그대로 인식되고,
그 경우 캐릭터는 (레벨 규칙에 따라) 쉬운 영어로 답합니다.
"""

import io

from . import config
from .llm import LLMError, client

# 아이가 쓸 만한 일상 단어를 미리 알려주면 영어 인식 정확도가 올라갑니다.
ENGLISH_HINT = (
    "A young child is chatting about their day: school, friends, playground, "
    "snack, dinner, mom, dad, teacher, puppy, drawing, snow, soccer, game, "
    "sleepy, happy, fun."
)


def transcribe(
    audio_bytes: bytes,
    filename: str = "speech.wav",
    language: str | None = None,
) -> str:
    """녹음된 오디오 바이트를 텍스트로. language=None 이면 자동 감지."""
    if not audio_bytes:
        return ""

    buffer = io.BytesIO(audio_bytes)
    # OpenAI SDK 는 파일 객체의 name 으로 포맷을 판단하므로 꼭 필요합니다.
    buffer.name = filename

    kwargs = {
        "model": config.stt_model(),
        "file": buffer,
        "prompt": ENGLISH_HINT,
    }
    if language:
        kwargs["language"] = language

    try:
        response = client().audio.transcriptions.create(**kwargs)
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"음성을 알아듣지 못했어요: {e}") from e

    return (getattr(response, "text", "") or "").strip()
