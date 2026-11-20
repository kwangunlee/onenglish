"""
OpenAI 음성 합성 (gpt-4o-mini-tts / tts-1 계열).

연기 지시문(instructions)을 받을 수 있어서 상황에 따라 톤이 바뀝니다.
대신 지시문이 달라질 때마다 음색도 미세하게 흔들립니다. 이 맞바꿈은
VOICE_MODE 설정으로 조절합니다.
"""

from .. import config
from .base import Direction, Provider, Voice, clean_for_speech

VOICES = [
    Voice("fable", "표현력 매우 큼 / 이야기꾼"),
    Voice("verse", "표현력 큼 / 활발한 남성"),
    Voice("ballad", "감정 풍부 / 부드러움"),
    Voice("coral", "따뜻하고 통통 튐 / 여성"),
    Voice("nova", "밝은 여성"),
    Voice("sage", "차분하고 또렷함"),
    Voice("shimmer", "부드러운 여성"),
    Voice("alloy", "중립적"),
    Voice("ash", "평탄한 편"),
    Voice("echo", "평탄한 편"),
    Voice("onyx", "낮고 평탄함"),
]

# 그 순간의 감정 → 연기 지시. llm.MOODS 와 짝을 이룹니다.
MOOD_DIRECTION = {
    "excited": "Right now: you are thrilled by what your friend just told you. "
               "Let your voice jump — brighter, faster, higher energy than usual.",
    "happy": "Right now: you are cheerful and glad to be chatting. "
             "Keep a bright, smiling warmth all the way through.",
    "playful": "Right now: you are teasing and having fun. "
               "Light, bouncy, a little mischievous.",
    "proud": "Right now: you are beaming with pride for your friend. "
             "Full, warm and emphatic — really mean the praise.",
    "curious": "Right now: you genuinely want to know more. "
               "Lean in, lift the question at the end, sound interested.",
    "gentle": "Right now: your friend needs a softer touch. "
              "Quieter, slower, kind. Still warm, never flat.",
    "comforting": "Right now: your friend sounds down. Be tender and reassuring. "
                  "Soft, unhurried, close — like a hug in the voice.",
    "silly": "Right now: you are being goofy on purpose. "
             "Exaggerated, giggly, a bit over the top.",
}


def pace_instruction(rate: float) -> str:
    """속도 지시문. 앞의 캐릭터 연출을 눌러버리지 않도록 "속도만" 조절하라고
    명시합니다."""
    if rate < 0.9:
        speed = ("Slow the delivery down and leave a little more space between "
                 "phrases, so a young learner can follow every word.")
    elif rate <= 1.05:
        speed = "Keep the delivery at a natural speed."
    elif rate <= 1.25:
        speed = "Pick the delivery up a little faster than normal."
    else:
        speed = "Deliver this quickly, with real momentum."

    return (
        f"Speed: {speed} Adjust ONLY the speed. Keep the character's "
        "personality, warmth and expressiveness exactly as described above. "
        "Do not flatten the delivery into a neutral narrator."
    )


def scene_direction(scene: str) -> str:
    """아이가 방금 한 말을 넣어 상황에 맞게 읽도록 합니다."""
    scene = clean_for_speech(scene)
    if not scene:
        return ""
    if len(scene) > 180:
        scene = scene[:180].rsplit(" ", 1)[0] + "..."
    return (
        f'Situation: your friend just said to you — "{scene}". '
        "You are replying to that, right now, out loud. Read your line as a "
        "real reaction to it, not as narration."
    )


def _model_supports_speed(model: str) -> bool:
    # gpt-4o 계열 TTS 는 speed 를 받지 않습니다. tts-1 / tts-1-hd 는 받습니다.
    return model.startswith("tts-")


def _model_supports_instructions(model: str) -> bool:
    return not model.startswith("tts-")


class OpenAIProvider(Provider):
    id = "openai"
    name = "OpenAI"
    supports_direction = True
    voice_field = "voice"

    def is_available(self) -> bool:
        return config.key_is_configured()

    def unavailable_reason(self) -> str:
        return config.MISSING_KEY_MESSAGE

    def list_voices(self) -> list[Voice]:
        return list(VOICES)

    def build_instructions(self, direction: Direction) -> str:
        """VOICE_MODE 에 따라 지시문에 무엇까지 넣을지 정합니다.

        지시문이 매 호출마다 달라질수록 연기는 살아나지만 음색이 흔들립니다.
        변동성이 큰 순서: 아이가 한 말(매번 다름) > 기분(8종) > 속도(거의 고정).
        """
        mode = config.voice_mode()
        parts = [direction.instruction.strip()]
        if mode == "expressive":
            parts.append(scene_direction(direction.scene))
        if mode in ("balanced", "expressive"):
            parts.append(MOOD_DIRECTION.get(direction.mood, ""))
        parts.append(pace_instruction(direction.rate))
        return "\n\n".join(p for p in parts if p)

    def synthesize(self, text: str, voice: str, direction: Direction) -> bytes:
        from ..llm import LLMError, client  # 순환 import 방지를 위해 지연 import

        cleaned = clean_for_speech(text)
        if not cleaned:
            return b""

        model = config.tts_model()
        kwargs = {
            "model": model,
            "voice": voice or "shimmer",
            "input": cleaned,
            "response_format": "mp3",
        }

        instructions = ""
        if _model_supports_instructions(model):
            instructions = self.build_instructions(direction)
            if instructions:
                kwargs["instructions"] = instructions
        if _model_supports_speed(model):
            kwargs["speed"] = max(0.25, min(4.0, direction.rate))

        from . import record_call
        record_call(provider=self.id, model=model, voice=kwargs["voice"],
                    mode=config.voice_mode(),
                    used_instructions=bool(instructions),
                    instructions=instructions)

        try:
            return client().audio.speech.create(**kwargs).content
        except LLMError:
            raise
        except Exception as e:
            # 모델이 instructions 를 지원하지 않는 경우에만 빼고 재시도합니다.
            # 모든 오류에서 빼고 재시도하면, 연출이 사라진 밋밋한 목소리가
            # 조용히 나와서 원인을 찾을 수 없게 됩니다.
            message = str(e).lower()
            unsupported = "instructions" in kwargs and (
                "instructions" in message
                and any(s in message for s in
                        ("unsupported", "unrecognized", "not supported", "unknown"))
            )
            if unsupported:
                kwargs.pop("instructions")
                record_call(provider=self.id, model=model, voice=kwargs["voice"],
                            mode=config.voice_mode(), used_instructions=False,
                            instructions="")
                try:
                    return client().audio.speech.create(**kwargs).content
                except Exception as e2:
                    raise LLMError(f"목소리를 만드는 중 문제가 생겼어요: {e2}") from e2
            raise LLMError(f"목소리를 만드는 중 문제가 생겼어요: {e}") from e
