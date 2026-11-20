"""
목소리 들어보기.

캐릭터별 샘플 음성을 만들어서 voice_samples/ 폴더에 저장합니다.
들어보고 마음에 드는 목소리로 characters.json 의 voice 값을 바꾸면 됩니다.

실행 (onenglish 폴더에서):

    python tools/voice_test.py
        캐릭터 4종 × 감정 3가지 샘플 생성

    python tools/voice_test.py --character rocky
        한 캐릭터만

    python tools/voice_test.py --character rocky --voices verse,fable,ballad,nova
        같은 대사를 여러 목소리로 만들어 비교 (목소리 고를 때 유용)

    python tools/voice_test.py --list
        쓸 수 있는 목소리 목록

OpenAI 를 실제로 호출하므로 아주 소액의 비용이 발생합니다.
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# .streamlit/secrets.toml 에서 키를 읽어옵니다 (앱과 같은 설정을 씁니다).
def _load_key_from_secrets() -> None:
    if os.environ.get("OPENAI_API_KEY"):
        return
    path = ROOT / ".streamlit" / "secrets.toml"
    if not path.exists():
        return
    try:
        import tomllib
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    for key in ("OPENAI_API_KEY", "TTS_MODEL"):
        value = data.get(key)
        if value:
            os.environ.setdefault(key, str(value))


_load_key_from_secrets()

from core import config, packs, tts  # noqa: E402
from core.llm import LLMError  # noqa: E402

OUT = ROOT / "voice_samples"

ALL_VOICES = [
    "alloy", "ash", "ballad", "coral", "echo", "fable",
    "nova", "onyx", "sage", "shimmer", "verse",
]

# 표현력이 큰 편 → 작은 편 (주관적인 참고용)
EXPRESSIVE = ["fable", "verse", "ballad", "coral", "nova", "sage",
              "shimmer", "alloy", "ash", "echo", "onyx"]

# (감정, 아이가 한 말, 캐릭터 대사)
SCENES = [
    ("excited", "I made a big snowman with my dad today!",
     "A snowman? That is amazing! How tall was it?"),
    ("curious", "I had something funny at lunch.",
     "Ooh, what was it? Tell me everything!"),
    ("comforting", "I fell down at the playground and it hurt.",
     "Oh no, that sounds sore. Are you feeling better now?"),
]

# 음색 흔들림 확인용. 한 대화 안에서 기분이 크게 바뀌는 순서로 배치했습니다.
DRIFT_SCENES = [
    ("happy", "Hi!",
     "Hello there! I am so glad you came today. How are you?"),
    ("excited", "I got a new bike for my birthday!",
     "A new bike? That is wonderful news! What colour is it?"),
    ("comforting", "But I fell off it and scraped my knee.",
     "Oh no. That must have hurt. Are you okay now?"),
    ("playful", "I am okay! I want to ride it again tomorrow.",
     "That is the spirit! Where will you ride to first?"),
]


def synth(character: dict, voice: str, mood: str, child_line: str,
          line: str, filename: str) -> bool:
    try:
        audio = tts.synthesize(
            line,
            voice=voice,
            rate=0.95,
            mood=mood,
            scene=child_line,
            character=character,
        )
    except LLMError as e:
        print(f"    실패: {e}")
        return False
    if not audio:
        print("    실패: 빈 응답")
        return False
    path = OUT / filename
    path.write_bytes(audio)
    print(f"    {filename}  ({len(audio) // 1024} KB)")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--character", help="캐릭터 id (luna, rocky, zoom, mochi)")
    parser.add_argument("--voices", help="비교할 목소리들, 쉼표로 구분")
    parser.add_argument("--list", action="store_true", help="목소리 목록 보기")
    parser.add_argument(
        "--provider", choices=["openai", "google"],
        help="음성 프로바이더 (기본: secrets.toml 의 TTS_PROVIDER)",
    )
    parser.add_argument(
        "--google-voices", action="store_true",
        help="Google 에서 쓸 수 있는 영어 목소리 목록 받아오기",
    )
    parser.add_argument(
        "--drift", action="store_true",
        help="음색 흔들림 비교. 같은 캐릭터의 연속 대사를 VOICE_MODE 3가지로 생성",
    )
    args = parser.parse_args()

    if args.list:
        print("\n쓸 수 있는 목소리:")
        for v in ALL_VOICES:
            print(f"  {v}")
        print("\n표현력이 큰 편 → 작은 편 (참고용, 주관적):")
        print("  " + " > ".join(EXPRESSIVE))
        print("\n활발한 캐릭터에 echo, ash, onyx 는 권하지 않습니다.\n")
        return 0

    if args.provider:
        os.environ["TTS_PROVIDER"] = args.provider

    if args.google_voices:
        from core.tts_providers.google_tts import GoogleProvider
        google = GoogleProvider()
        if not google.is_available():
            print(google.unavailable_reason())
            return 1
        voices = google.list_voices()
        print(f"\nGoogle 영어 목소리 {len(voices)}개:\n")
        for v in voices:
            extra = f"  ({v.label})" if v.label else ""
            print(f"  {v.name}{extra}")
        print("\ncharacters.json 의 voice_google 값에 넣어 쓰세요.")
        print("Chirp3-HD 계열이 가장 자연스럽습니다.\n")
        return 0

    provider = tts.resolve_provider()
    if not provider.is_available():
        print(provider.unavailable_reason())
        return 1

    characters = packs.all_characters()
    if args.character:
        characters = [c for c in characters if c["id"] == args.character]
        if not characters:
            print(f"'{args.character}' 캐릭터를 찾을 수 없습니다.")
            return 1

    OUT.mkdir(exist_ok=True)
    detail = (config.tts_model() if provider.id == "openai" else "Chirp3-HD 등")
    print(f"\n프로바이더: {provider.name} ({detail})")
    print(f"연기 지시 반영: {'예' if provider.supports_direction else '아니오'}")
    print(f"저장 위치: {OUT}\n")

    made = 0

    if args.drift:
        # 같은 캐릭터가 연속으로 말하는 상황을 모드별로 생성합니다.
        # 한 모드 안에서 1~4번 파일을 이어서 들어보고, 같은 사람 목소리로
        # 들리는지 확인하세요.
        character = characters[0]
        print(f"[{character['name']}] 음색 흔들림 비교 — "
              f"voice={provider.voice_for(character)}\n")
        for mode in config.VOICE_MODES:
            os.environ["VOICE_MODE"] = mode
            print(f"  VOICE_MODE={mode}")
            for i, (mood, child_line, line) in enumerate(DRIFT_SCENES, 1):
                if synth(character, "", mood, child_line, line,
                         f"drift_{mode}_{i}_{character['id']}.mp3"):
                    made += 1
            print()
        os.environ.pop("VOICE_MODE", None)
        print("  들을 때: 한 모드 안에서 1→2→3→4 를 이어서 들어보세요.")
        print("  stable 은 음색이 일정하고, expressive 로 갈수록 생기가 커지는")
        print("  대신 목소리가 조금씩 달라집니다. 마음에 드는 모드를")
        print("  .streamlit/secrets.toml 의 VOICE_MODE 에 적으면 됩니다.\n")

    elif args.voices:
        # 같은 대사를 여러 목소리로 — 목소리 고를 때
        voices = [v.strip() for v in args.voices.split(",") if v.strip()]
        character = characters[0]
        mood, child_line, line = SCENES[0]
        print(f"[{character['name']}] 목소리 비교 — \"{line}\"\n")
        for voice in voices:
            if voice not in ALL_VOICES:
                print(f"    건너뜀: '{voice}' 는 없는 목소리입니다")
                continue
            if synth(character, voice, mood, child_line, line,
                     f"compare_{character['id']}_{voice}.mp3"):
                made += 1
    else:
        # 캐릭터별 × 감정별
        for character in characters:
            voice = provider.voice_for(character)
            print(f"[{character['name']}] voice={voice}")
            for mood, child_line, line in SCENES:
                if synth(character, "", mood, child_line, line,
                         f"{character['id']}_{mood}.mp3"):
                    made += 1
            print()

    print(f"\n{made}개 생성 완료. voice_samples 폴더를 열어 들어보세요.")
    print("마음에 드는 목소리를 찾으면 data/packs/kids/characters.json 의")
    print('해당 캐릭터 "voice" 값을 바꾸고 앱을 다시 실행하면 됩니다.\n')
    return 0


if __name__ == "__main__":
    sys.exit(main())
