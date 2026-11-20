"""
음성 → 텍스트.

두 가지 방법 중에서 고릅니다.
  openai  Whisper. 전사 전용 모델.
  google  Gemini 에 오디오를 그대로 보내서 받아 적게 합니다.
          Cloud Speech-to-Text 와 달리 API 키 하나로 동작합니다.

둘 다 브라우저가 녹음한 파일을 통째로 보냅니다. 예전 버전의 Google STT
스트리밍과 달리 5분 제한이 없고, 자격증명 JSON 파일도 필요 없습니다.
"""

import base64
import io

from . import config
from .clients import AIError, gemini_post, gemini_text, openai_client

# 아이가 쓸 만한 일상 단어를 미리 알려주면 인식 정확도가 올라갑니다.
ENGLISH_HINT = (
    "A young child is chatting about their day: school, friends, playground, "
    "snack, dinner, mom, dad, teacher, puppy, drawing, snow, soccer, game, "
    "sleepy, happy, fun."
)

_GEMINI_INSTRUCTION = (
    "Write down exactly what the speaker says in this audio, as plain text.\n"
    "- The speaker is a young child learning English. They may mispronounce "
    "words or speak quietly.\n"
    "- Write only the words spoken. No quotation marks, no speaker labels, "
    "no timestamps, no commentary, no translation.\n"
    "- Keep whatever language they actually used.\n"
    "- If the audio has no speech at all, reply with nothing."
)

_MIME = {
    "wav": "audio/wav", "mp3": "audio/mp3", "m4a": "audio/mp4",
    "ogg": "audio/ogg", "webm": "audio/webm", "flac": "audio/flac",
}


def _mime_for(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "wav"
    return _MIME.get(ext, "audio/wav")


def transcribe(
    audio_bytes: bytes,
    filename: str = "speech.wav",
    language: str | None = None,
) -> str:
    """녹음된 오디오를 텍스트로. language=None 이면 자동 감지."""
    if not audio_bytes:
        return ""

    which = config.stt_provider()
    if which == "google":
        return _transcribe_gemini(audio_bytes, filename)
    if which == "openai":
        return _transcribe_whisper(audio_bytes, filename, language)
    raise AIError(
        f"'{which}' 음성인식 프로바이더를 찾을 수 없어요. "
        "쓸 수 있는 값: openai, google"
    )


def provider_name() -> str:
    return {"openai": "OpenAI Whisper", "google": "Google Gemini"}.get(
        config.stt_provider(), config.stt_provider()
    )


# ── OpenAI Whisper ───────────────────────────────────────────────

def _transcribe_whisper(audio_bytes: bytes, filename: str,
                        language: str | None) -> str:
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
        response = openai_client().audio.transcriptions.create(**kwargs)
    except AIError:
        raise
    except Exception as e:
        raise AIError(f"음성을 알아듣지 못했어요: {e}") from e

    return (getattr(response, "text", "") or "").strip()


# ── Google Gemini ────────────────────────────────────────────────

def _transcribe_gemini(audio_bytes: bytes, filename: str) -> str:
    payload = {
        "systemInstruction": {"parts": [{"text": _GEMINI_INSTRUCTION}]},
        "contents": [{
            "role": "user",
            "parts": [
                {"text": ENGLISH_HINT},
                {"inline_data": {
                    "mime_type": _mime_for(filename),
                    "data": base64.b64encode(audio_bytes).decode("ascii"),
                }},
            ],
        }],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 256},
    }
    path = f"models/{config.gemini_stt_model()}:generateContent"
    text = gemini_text(gemini_post(path, payload))

    # 가끔 따옴표로 감싸서 옵니다.
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text
