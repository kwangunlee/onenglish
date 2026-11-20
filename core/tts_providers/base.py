"""
음성 합성 프로바이더의 공통 규격.

새 프로바이더를 추가하려면 이 파일의 Provider 를 상속해서 만들고
__init__.py 의 레지스트리에 등록하면 됩니다. core/tts.py 나 app.py 는
수정하지 않습니다.
"""

import re
from dataclasses import dataclass

# 이모지, 장식기호, 그림문자 영역
_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # 그림문자 전반
    "\U00002600-\U000027BF"   # 기타 기호 / 딩뱃
    "\U00002B00-\U00002BFF"   # 화살표 등
    "\U0000FE00-\U0000FE0F"   # 변이 선택자
    "\U0001F1E6-\U0001F1FF"   # 국기
    "\U00002190-\U000021FF"   # 화살표
    "\U00002300-\U000023FF"   # 기타 기술 기호
    "]+",
    flags=re.UNICODE,
)

# 마크다운 장식 (TTS 가 "별표"라고 읽어버리는 것 방지)
_MARKDOWN_RE = re.compile(r"[*_`#~>|\[\]]+")


def clean_for_speech(text: str) -> str:
    """읽을 수 없는 기호를 걷어냅니다. 모든 프로바이더가 공통으로 씁니다."""
    text = _EMOJI_RE.sub(" ", text)
    text = _MARKDOWN_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@dataclass
class Direction:
    """그 순간 어떻게 읽을지에 대한 정보.

    프로바이더마다 소화할 수 있는 정도가 다릅니다.
      - OpenAI gpt-4o-mini-tts : 전부 활용 (연기 지시문으로 변환)
      - Google Chirp3-HD       : rate 만 활용 (연기 지시를 받지 않는 모델)
    받지 못하는 항목은 각 프로바이더가 알아서 무시합니다.
    """
    instruction: str = ""   # 캐릭터 고정 연출
    mood: str = ""          # 그 순간의 감정
    scene: str = ""         # 아이가 방금 한 말
    rate: float = 1.0       # 말하는 속도


@dataclass
class Voice:
    """목록에 보여줄 목소리 하나."""
    name: str
    label: str = ""
    language: str = ""


class Provider:
    """음성 합성 프로바이더."""

    id: str = ""
    name: str = ""
    # 연기 지시(감정·상황)를 반영할 수 있는가.
    # False 면 음색이 항상 일정한 대신 톤 변화가 없습니다.
    supports_direction: bool = False
    # 이 프로바이더의 목소리를 캐릭터 정의에서 찾을 때 쓸 필드 이름
    voice_field: str = "voice"

    def is_available(self) -> bool:
        """키가 설정되어 있는지 등, 지금 쓸 수 있는 상태인지."""
        raise NotImplementedError

    def unavailable_reason(self) -> str:
        """쓸 수 없을 때 사용자에게 보여줄 안내문."""
        return f"{self.name} 을(를) 사용할 수 없습니다."

    def voice_for(self, character: dict) -> str:
        """캐릭터 정의에서 이 프로바이더용 목소리 이름을 꺼냅니다."""
        return (character.get(self.voice_field) or "").strip()

    def synthesize(self, text: str, voice: str, direction: Direction) -> bytes:
        """mp3 바이트를 반환합니다."""
        raise NotImplementedError

    def list_voices(self) -> list[Voice]:
        """고를 수 있는 목소리 목록. 못 가져오면 빈 리스트."""
        return []
