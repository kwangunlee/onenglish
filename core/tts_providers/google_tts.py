"""
Google Cloud 음성 합성 (Text-to-Speech REST API).

**API 키 방식만 씁니다.** 서비스 계정 JSON 파일은 쓰지 않습니다.
예전 버전에서 폴더에 그대로 놓여 있던 그 자격증명 파일은 데이터베이스
전체 권한을 가지고 있어서 위험했습니다. TTS 만 쓰는 데에는 제한된 API 키
하나면 충분합니다.

키 발급:
  1. https://console.cloud.google.com 에서 프로젝트 선택
  2. "Cloud Text-to-Speech API" 사용 설정
  3. 사용자 인증 정보 → API 키 만들기
  4. 만든 키는 반드시 "API 제한"에서 Text-to-Speech 만 허용하도록 제한하세요
  5. .streamlit/secrets.toml 의 GOOGLE_TTS_KEY 에 넣기

특징: Chirp3-HD 같은 Google 목소리는 연기 지시를 받지 않습니다. 텍스트와
속도만 받아 읽습니다. 그래서 **음색이 절대 흔들리지 않는 대신 상황에 따른
톤 변화가 없습니다.** OpenAI 쪽과 정확히 반대 성격입니다.
"""

import base64

import requests

from .. import config
from .base import Direction, Provider, Voice, clean_for_speech

ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"
VOICES_ENDPOINT = "https://texttospeech.googleapis.com/v1/voices"
TIMEOUT = 30

# 참고용 기본 목록. 실제 사용 가능한 목록은 list_voices() 로 받아옵니다.
KNOWN_VOICES = [
    Voice("en-US-Chirp3-HD-Leda", "부드러운 여성", "en-US"),
    Voice("en-US-Chirp3-HD-Kore", "밝은 여성", "en-US"),
    Voice("en-US-Chirp3-HD-Aoede", "따뜻한 여성", "en-US"),
    Voice("en-US-Chirp3-HD-Zephyr", "경쾌한 여성", "en-US"),
    Voice("en-US-Chirp3-HD-Orus", "활발한 남성", "en-US"),
    Voice("en-US-Chirp3-HD-Puck", "경쾌한 남성", "en-US"),
    Voice("en-US-Chirp3-HD-Charon", "차분한 남성", "en-US"),
    Voice("en-US-Chirp3-HD-Fenrir", "힘있는 남성", "en-US"),
]


def _language_of(voice: str) -> str:
    """목소리 이름 앞부분이 언어 코드입니다. en-US-Chirp3-HD-Leda -> en-US"""
    parts = voice.split("-")
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return "en-US"


class GoogleProvider(Provider):
    id = "google"
    name = "Google"
    # Chirp3-HD 등은 연기 지시를 받지 않습니다. 음색이 항상 일정합니다.
    supports_direction = False
    voice_field = "voice_google"

    def is_available(self) -> bool:
        return bool(config.google_tts_key())

    def unavailable_reason(self) -> str:
        return config.MISSING_GOOGLE_KEY_MESSAGE

    def list_voices(self) -> list[Voice]:
        key = config.google_tts_key()
        if not key:
            return list(KNOWN_VOICES)
        try:
            response = requests.get(
                VOICES_ENDPOINT,
                params={"key": key, "languageCode": "en-US"},
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            return list(KNOWN_VOICES)

        out = []
        for v in data.get("voices", []):
            name = v.get("name", "")
            if not name:
                continue
            gender = (v.get("ssmlGender") or "").lower()
            out.append(Voice(name, gender, ", ".join(v.get("languageCodes", []))))
        return out or list(KNOWN_VOICES)

    def synthesize(self, text: str, voice: str, direction: Direction) -> bytes:
        from ..llm import LLMError  # 순환 import 방지

        cleaned = clean_for_speech(text)
        if not cleaned:
            return b""

        key = config.google_tts_key()
        if not key:
            raise LLMError(config.MISSING_GOOGLE_KEY_MESSAGE)

        voice = voice or "en-US-Chirp3-HD-Leda"
        rate = max(0.25, min(4.0, direction.rate))

        payload = {
            "input": {"text": cleaned},
            "voice": {"languageCode": _language_of(voice), "name": voice},
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": rate},
        }

        from . import record_call
        record_call(provider=self.id, model="google-tts", voice=voice,
                    mode="n/a (연기 지시 미지원)", used_instructions=False,
                    instructions="")

        audio = self._post(payload, key)
        if audio is not None:
            return audio

        # 일부 목소리는 speakingRate 를 받지 않습니다. 속도를 빼고 한 번 더.
        payload["audioConfig"].pop("speakingRate", None)
        audio = self._post(payload, key, raise_on_fail=True)
        return audio or b""

    def _post(self, payload: dict, key: str, raise_on_fail: bool = False):
        from ..llm import LLMError

        try:
            response = requests.post(
                ENDPOINT, params={"key": key}, json=payload, timeout=TIMEOUT
            )
        except Exception as e:
            raise LLMError(f"Google 음성 서버에 연결하지 못했어요: {e}") from e

        if response.status_code == 200:
            content = response.json().get("audioContent")
            if content:
                return base64.b64decode(content)
            if raise_on_fail:
                raise LLMError("Google 음성 응답이 비어 있어요.")
            return None

        detail = self._error_detail(response)
        if not raise_on_fail and "speakingrate" in detail.lower():
            return None  # 속도 빼고 재시도
        raise LLMError(self._friendly_error(response.status_code, detail))

    @staticmethod
    def _error_detail(response) -> str:
        try:
            return str(response.json().get("error", {}).get("message", ""))
        except Exception:
            return (response.text or "")[:300]

    @staticmethod
    def _friendly_error(status: int, detail: str) -> str:
        if status in (401, 403):
            return (
                "Google 음성 키가 거부됐어요.\n"
                "  · Cloud Text-to-Speech API 가 사용 설정되어 있는지\n"
                "  · API 키 제한에 Text-to-Speech 가 허용되어 있는지\n"
                "  · 결제 계정이 연결되어 있는지\n"
                f"확인해 주세요.\n(원문: {detail})"
            )
        if status == 400:
            return (
                "Google 음성 요청이 잘못됐어요. 목소리 이름이 맞는지 확인해 주세요.\n"
                "  python tools/voice_test.py --google-voices\n"
                f"(원문: {detail})"
            )
        if status == 429:
            return "Google 음성 사용량 한도를 넘었어요. 잠시 뒤에 다시 시도해 주세요."
        return f"Google 음성을 만들지 못했어요 (HTTP {status}): {detail}"
