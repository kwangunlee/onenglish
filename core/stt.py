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
import math
import re
import wave
from array import array

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
    """녹음된 오디오를 텍스트로. language=None 이면 자동 감지.

    아무 말도 없었으면 "" 를 돌려줍니다. 화면은 "잘 안 들렸어요" 를 띄웁니다.

    음성인식 모델은 조용한 녹음을 받으면 말을 지어냅니다. 학습 데이터(유튜브
    자막 등)에 흔한 "Thanks for watching", "Learn more at www..." 같은 문장이
    나오고, 그게 아이가 한 말로 대화에 들어갑니다. 그래서 세 겹으로 막습니다.
      1. 보내기 전: 너무 짧거나 거의 무음이면 API 를 부르지 않음 (비용도 아낌)
      2. Whisper 가 알려주는 "말소리가 없을 확률"이 높은 구간은 버림
      3. 결과가 아이가 했을 리 없는 문장이면 버림 (웹 주소, 방송 자막 문구,
         우리가 준 힌트 문장을 그대로 되풀이한 것 등)"""
    if not audio_bytes or is_silent(audio_bytes):
        return ""

    which = config.stt_provider()
    if which == "google":
        text = _transcribe_gemini(audio_bytes, filename)
    elif which == "openai":
        text = _transcribe_whisper(audio_bytes, filename, language)
    else:
        raise AIError(
            f"'{which}' 음성인식 프로바이더를 찾을 수 없어요. "
            "쓸 수 있는 값: openai, google"
        )
    return "" if looks_made_up(text) else text


# ── 1. 무음 거르기 ───────────────────────────────────────────────
# 브라우저가 녹음한 WAV(16비트)를 직접 읽어서 판단합니다. WAV 가 아니거나 읽을
# 수 없으면 판단하지 않고 그냥 보냅니다 (말을 놓치는 것보다 낫기 때문).

MIN_SECONDS = 0.35          # 이보다 짧으면 누르자마자 멈춘 것
# 가장 큰 구간의 소리 크기 기준 (dBFS). 조용한 방의 잡음은 보통 -55 아래입니다.
# 작게 말하는 아이를 놓치지 않도록 낮게(-50) 잡았습니다. 이 위의 잡음이 넘어가도
# 2·3번 단계에서 걸러집니다. (시험: -50dB 잡음 → Whisper 가 빈 결과를 냄)
SILENCE_DBFS = -50.0


def _loudness_dbfs(audio_bytes: bytes) -> tuple[float, float] | None:
    """(길이 초, 가장 큰 50ms 구간의 크기 dBFS). WAV 가 아니면 None."""
    try:
        with wave.open(io.BytesIO(audio_bytes)) as w:
            if w.getsampwidth() != 2:
                return None
            rate, channels = w.getframerate(), w.getnchannels()
            frames = w.readframes(w.getnframes())
    except (wave.Error, EOFError):
        return None

    samples = array("h")
    samples.frombytes(frames[: len(frames) - len(frames) % 2])
    if channels > 1:
        samples = samples[::channels]  # 첫 채널만 보면 충분합니다
    if not samples or not rate:
        return 0.0, -120.0

    seconds = len(samples) / rate
    window = max(1, int(rate * 0.05))
    loudest = 0.0
    for start in range(0, len(samples), window):
        chunk = samples[start:start + window]
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk))
        loudest = max(loudest, rms)
    dbfs = 20 * math.log10(loudest / 32768) if loudest > 0 else -120.0
    return seconds, dbfs


def is_silent(audio_bytes: bytes) -> bool:
    measured = _loudness_dbfs(audio_bytes)
    if measured is None:
        return False
    seconds, dbfs = measured
    return seconds < MIN_SECONDS or dbfs < SILENCE_DBFS


# ── 3. 지어낸 문장 거르기 ────────────────────────────────────────
# 무음·잡음에서 음성인식 모델이 자주 지어내는 문장들. 아이가 실제로 이런 말을
# 할 일은 거의 없습니다. 영어와 한국어 둘 다 넣었습니다(언어 자동 감지라서).

_MADE_UP = re.compile(
    r"(https?://|www\.|\.com\b|\.org\b|\.net\b|\.kr\b"
    r"|learn more at|thanks? (you )?for watching|please (like|subscribe)"
    r"|subscribe to|subtitles? by|captions? by|transcri(bed|ption) by"
    r"|amara\.org|see you (in the )?next (video|time)"
    r"|시청해 ?주셔서 감사|구독과 좋아요|자막 제공|MBC ?뉴스|KBS ?뉴스|SBS ?뉴스)",
    re.IGNORECASE,
)


def looks_made_up(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return True
    if _MADE_UP.search(text):
        return True
    # 우리가 준 힌트 문장을 그대로 되풀이한 경우 (무음일 때 가끔 일어남)
    hint = ENGLISH_HINT.lower()
    lowered = text.lower().rstrip(".")
    return len(lowered) > 25 and lowered in hint


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

    # whisper-1 은 구간마다 "말소리가 없을 확률"을 알려줍니다 (verbose_json).
    # gpt-4o-transcribe 같은 새 모델은 이 형식을 지원하지 않아 그냥 받습니다.
    detailed = config.stt_model().startswith("whisper")
    if detailed:
        kwargs["response_format"] = "verbose_json"
        kwargs["temperature"] = 0

    try:
        response = openai_client().audio.transcriptions.create(**kwargs)
    except AIError:
        raise
    except Exception as e:
        raise AIError(f"음성을 알아듣지 못했어요: {e}") from e

    segments = getattr(response, "segments", None) if detailed else None
    if segments:
        return _speech_only(segments)
    return (getattr(response, "text", "") or "").strip()


def _speech_only(segments) -> str:
    """말소리가 없었을 가능성이 큰 구간을 뺍니다.

    OpenAI 의 Whisper 기본 기준과 같습니다: 말소리 없음 확률 > 0.6 이면서
    모델의 확신(평균 로그 확률)이 -1 보다 낮으면 무음으로 봅니다."""
    kept = []
    for seg in segments:
        get = seg.get if isinstance(seg, dict) else (lambda k, s=seg: getattr(s, k, None))
        no_speech = float(get("no_speech_prob") or 0)
        logprob = float(get("avg_logprob") or 0)
        if no_speech > 0.6 and logprob < -1.0:
            continue
        kept.append((get("text") or "").strip())
    return " ".join(t for t in kept if t).strip()


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
