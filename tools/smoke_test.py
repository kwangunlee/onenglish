"""
화면 흐름 점검 (브라우저 없이).

    python tools/smoke_test.py

OpenAI 를 실제로 호출하지는 않습니다. 화면 전환, 프로필 생성, 기록 화면이
오류 없이 뜨는지만 확인합니다.
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 실제 키 대신 형식만 맞는 값. 화면 진입 조건을 통과시키기 위한 것입니다.
os.environ["OPENAI_API_KEY"] = "sk-test-smoke-0000000000000000000000000000"
os.environ.setdefault("APP_PASSWORD", "")

# 테스트 중 실제 DB 를 건드리지 않도록 임시 폴더의 SQLite 로 돌립니다.
_tmp = tempfile.mkdtemp(prefix="onenglish-smoke-")
from core import config  # noqa: E402
config.DATA_DIR = Path(_tmp)
config.DB_PATH = Path(_tmp) / "test.db"

# secrets.toml 에 DB_BACKEND = "firestore" 가 있으면, 앱이 시작할 때 그 값을
# 환경변수로 옮겨서 실제 Firestore 에 테스트 기록이 들어갑니다(실제로 그랬습니다).
# 환경변수와 상관없이 무조건 임시 SQLite 를 쓰도록 고정합니다.
config.db_backend = lambda: "sqlite"

from streamlit.testing.v1 import AppTest  # noqa: E402

FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    mark = "OK  " if condition else "FAIL"
    print(f"  {mark} {label}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(label)


def no_exception(at: AppTest, label: str) -> None:
    detail = ""
    if at.exception:
        detail = "; ".join(str(e.value) for e in at.exception)
    check(label, not at.exception, detail)


def main() -> int:
    print("\n[1] 첫 화면 (프로필)")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    no_exception(at, "오류 없이 렌더링")
    body = " ".join(m.value for m in at.markdown)
    check("제목이 보임", "누구세요" in body)

    print("\n[2] 프로필 생성 (이름 + 비밀번호)")
    at.text_input[0].set_value("민준")
    at.text_input[1].set_value("1234")
    at.button[0].click().run()
    no_exception(at, "오류 없이 생성")
    check("캐릭터 화면으로 이동", at.session_state["screen"] == "characters")
    check("프로필이 세션에 저장됨",
          (at.session_state["profile"] or {}).get("name") == "민준")

    print("\n[3] 캐릭터 화면")
    body = " ".join(m.value for m in at.markdown)
    for name in ("Luna", "Rocky", "Zoom", "Mochi"):
        check(f"{name} 카드 표시", name in body)

    print("\n[4] 대화 시작")
    started = False
    for button in at.button:
        if button.label == "이 친구와 이야기하기":
            button.click().run()
            started = True
            break
    check("시작 버튼 눌림", started)
    if started:
        no_exception(at, "오류 없이 대화 화면 진입")
        check("대화 화면", at.session_state["screen"] == "chat")
        messages = at.session_state["messages"]
        check("인사말 1개 생성", len(messages) == 1 and messages[0]["role"] == "assistant",
              str(messages))
        check("세션 생성됨", bool(at.session_state["session_id"]))
        check("마이크 위젯 존재", len(at.get("audio_input")) > 0)
        check("타이핑 입력 존재", len(at.chat_input) > 0)

    print("\n[5] DB 에 기록되었는지")
    from core import store
    profiles = store.list_profiles()
    check("프로필 1개", len(profiles) == 1, str(profiles))
    if profiles:
        sessions = store.list_sessions(profiles[0]["id"])
        check("세션 1개", len(sessions) == 1)
        check("인사말이 assistant 로 저장됨",
              bool(sessions) and store.get_messages(sessions[0]["id"])[0]["role"] == "assistant")

    print("\n[6] 기록 화면")
    at.session_state["parent_authed"] = True
    at.session_state["screen"] = "records"
    at.run()
    no_exception(at, "오류 없이 렌더링")
    body = " ".join(m.value for m in at.markdown)
    check("기록 제목 표시", "기록" in body)

    print("\n[6-2] 프로필 잠금 — 입장 전 기록 비공개")
    at.session_state["profile"] = None
    at.session_state["screen"] = "profiles"
    at.run()
    card = next((b.label for b in at.button if "민준" in b.label), "")
    check("카드에 이름만 표시", "민준" in card and "대화" not in card and "기억" not in card)
    check("잠금 표시", "비밀번호 필요" in card)
    for b in at.button:
        if "민준" in b.label:
            b.click().run()
            break
    check("비밀번호 화면으로 감", at.session_state["screen"] == "unlock")
    check("아직 입장 안 됨", at.session_state["profile"] is None)
    at.text_input[0].set_value("0000")
    at.button[0].click().run()
    check("틀린 비밀번호 거부", at.session_state["profile"] is None)
    at.text_input[0].set_value("1234")
    at.button[0].click().run()
    check("맞는 비밀번호로 입장", at.session_state["screen"] == "characters")

    print("\n[7] 앱 비밀번호 게이트")
    os.environ["APP_PASSWORD"] = "1234"
    at2 = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    no_exception(at2, "오류 없이 렌더링")
    check("비밀번호 화면이 뜸", len(at2.text_input) > 0 and not at2.session_state["authed"])
    at2.text_input[0].set_value("1234")
    at2.button[0].click().run()
    check("올바른 비밀번호로 통과", at2.session_state["authed"])
    os.environ["APP_PASSWORD"] = ""

    print("\n[8] 키 미설정 안내")
    os.environ["OPENAI_API_KEY"] = "sk-여기에_붙여넣기"
    at3 = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    check("안내 문구 표시", len(at3.warning) > 0)
    os.environ["OPENAI_API_KEY"] = "sk-test-smoke-0000000000000000000000000000"

    print()
    if FAILURES:
        print(f"실패 {len(FAILURES)}건: " + ", ".join(FAILURES))
        return 1
    print("전부 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
