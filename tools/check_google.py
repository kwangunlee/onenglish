"""
Google 연결 확인.

    python tools/check_google.py            전체 점검 (대화·음성인식·음성합성)
    python tools/check_google.py --models   쓸 수 있는 Gemini 모델 목록
    python tools/check_google.py --chat     대화만
    python tools/check_google.py --tts      음성합성만

모델 이름은 수시로 바뀝니다. 대화가 "모델을 찾을 수 없어요" 로 실패하면
--models 로 목록을 보고 secrets.toml 의 GEMINI_CHAT_MODEL 을 바꾸세요.
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load_secrets() -> None:
    """앱과 같은 설정(.streamlit/secrets.toml)을 읽어옵니다."""
    path = ROOT / ".streamlit" / "secrets.toml"
    if not path.exists():
        return
    try:
        import tomllib
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    for key, value in data.items():
        if value is not None and str(value).strip():
            os.environ.setdefault(key, str(value).strip())


_load_secrets()

from core import config  # noqa: E402
from core.clients import AIError, gemini_get  # noqa: E402

PASS, FAIL = "  [성공]", "  [실패]"


def show_models() -> int:
    print("\n  쓸 수 있는 Gemini 모델을 받아옵니다...\n")
    try:
        data = gemini_get("models")
    except AIError as e:
        print(f"{FAIL} {e}")
        return 1

    rows = []
    for m in data.get("models", []):
        name = m.get("name", "").replace("models/", "")
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue
        rows.append((name, m.get("displayName", "")))

    if not rows:
        print("  쓸 수 있는 모델이 없습니다. API 키 권한을 확인해 주세요.")
        return 1

    print(f"  {len(rows)}개:\n")
    for name, label in sorted(rows):
        mark = " ←  지금 설정" if name == config.gemini_chat_model() else ""
        print(f"    {name:<42} {label}{mark}")

    print("\n  바꾸려면 .streamlit/secrets.toml 에:")
    print('    GEMINI_CHAT_MODEL = "모델이름"')
    print('    GEMINI_STT_MODEL  = "모델이름"\n')
    return 0


def check_chat() -> bool:
    from core import llm, packs

    print("\n  [1] 대화")
    os.environ["CHAT_PROVIDER"] = "google"
    print(f"      모델: {config.gemini_chat_model()}")

    character = packs.get_character("luna")
    level = packs.get_level("kids")
    if not character or not level:
        print(f"{FAIL} 캐릭터 설정을 읽지 못했습니다.")
        return False

    try:
        answer = llm.reply(
            character=character, level=level, history=[],
            user_text="I made a big snowman with my dad today!",
            child_name="테스트",
        )
    except AIError as e:
        print(f"{FAIL} {e}")
        return False

    print(f'{PASS} "{answer.text}"')
    print(f"      기분: {answer.mood}")
    if answer.mood == "happy":
        print("      (기분이 항상 happy 로만 나오면 JSON 형식을 못 받는 것일 수 있습니다)")
    return True


def check_stt() -> bool:
    print("\n  [2] 음성인식")
    print(f"      모델: {config.gemini_stt_model()}")
    print("      (확인하려면 실제 녹음 파일이 필요해서 여기서는 건너뜁니다)")
    print("      앱에서 마이크로 말해보고 글자가 뜨는지 보면 됩니다.")
    return True


def check_tts() -> bool:
    from core import packs, tts

    print("\n  [3] 음성합성")
    os.environ["TTS_PROVIDER"] = "google"

    character = packs.get_character("luna")
    voice = tts.voice_for(character)
    print(f"      목소리: {voice}")

    try:
        audio = tts.synthesize(
            "Hello! I am so glad you came today.",
            rate=0.95, mood="happy", character=character,
        )
    except AIError as e:
        print(f"{FAIL} {e}")
        return False

    if not audio:
        print(f"{FAIL} 빈 응답")
        return False

    out = ROOT / "voice_samples"
    out.mkdir(exist_ok=True)
    path = out / "google_check.mp3"
    path.write_bytes(audio)
    print(f"{PASS} {len(audio) // 1024} KB")
    print(f"      들어보기: {path}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--models", action="store_true")
    parser.add_argument("--chat", action="store_true")
    parser.add_argument("--stt", action="store_true")
    parser.add_argument("--tts", action="store_true")
    args = parser.parse_args()

    key = config.google_api_key()
    if not key:
        print(config.MISSING_GOOGLE_KEY_MESSAGE)
        return 1
    print(f"\n  Google API 키: {key[:8]}...{key[-4:]}")

    if args.models:
        return show_models()

    run_all = not (args.chat or args.stt or args.tts)
    results = []
    if run_all or args.chat:
        results.append(check_chat())
    if run_all or args.stt:
        results.append(check_stt())
    if run_all or args.tts:
        results.append(check_tts())

    print()
    if all(results):
        print("  전부 통과했습니다.")
        print("  secrets.toml 에 AI_PROVIDER = \"google\" 을 넣으면 앱 전체가")
        print("  Google 로 동작합니다.\n")
        return 0

    print("  실패한 항목이 있습니다.")
    print("  · 모델 이름 문제면:  python tools/check_google.py --models")
    print("  · 권한 문제면 아래 두 API 가 사용 설정되어 있는지 확인하세요.")
    print("      Generative Language API   (대화·음성인식)")
    print("      Cloud Text-to-Speech API  (음성합성)\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
