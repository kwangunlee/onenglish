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


def find_button(at: AppTest, text: str):
    """라벨에 text 가 들어가는 버튼. 없으면 None.

    버튼을 at.button[0] 처럼 순서로 집으면 화면에 버튼 하나만 늘어도 테스트가
    엉뚱한 것을 누릅니다(실제로 '관리자 페이지' 버튼이 생기면서 그랬습니다).
    그래서 항상 라벨로 찾습니다."""
    return next((b for b in at.button if text in b.label), None)


def click(at: AppTest, text: str, label: str | None = None) -> bool:
    """라벨로 버튼을 찾아 누릅니다. 못 찾으면 FAIL 로 남기고 False."""
    button = find_button(at, text)
    check(label or f"'{text}' 버튼 있음", button is not None,
          "있는 버튼: " + ", ".join(repr(b.label) for b in at.button))
    if button is None:
        return False
    button.click().run()
    return True


def field(at: AppTest, text: str):
    """라벨에 text 가 들어가는 입력칸."""
    return next((t for t in at.text_input if text in t.label), None)


def main() -> int:
    print("\n[1] 첫 화면 (프로필)")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    no_exception(at, "오류 없이 렌더링")
    # 화면 문구는 자주 바뀌므로, 문구 대신 "할 수 있는 일"이 있는지 봅니다.
    check("이름 입력칸 있음", field(at, "이름") is not None)
    check("비밀번호 입력칸 있음", field(at, "비밀번호") is not None)
    check("관리자 페이지로 가는 길 있음", find_button(at, "관리자") is not None)

    print("\n[2] 프로필 생성 (이름 + 비밀번호)")
    field(at, "이름").set_value("민준")
    field(at, "비밀번호").set_value("1234")
    if click(at, "추가하기", "추가하기 눌림"):
        no_exception(at, "오류 없이 생성")
        check("캐릭터 화면으로 이동", at.session_state["screen"] == "characters")
        check("프로필이 세션에 저장됨",
              (at.session_state["profile"] or {}).get("name") == "민준")

    print("\n[3] 캐릭터 화면")
    # 캐릭터 이름은 data/packs/ 에서 읽어, 팩을 바꿔도 테스트가 따라가게 합니다.
    from core import packs, store
    profile = at.session_state["profile"]
    level = store.effective_level(profile) if profile else "kids"
    expected = [c["name"] for c in packs.characters_for_level(level)]
    check("캐릭터가 하나 이상 있음", bool(expected), str(expected))
    body = " ".join(m.value for m in at.markdown)
    for name in expected:
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
    card = (find_button(at, "민준") or type("x", (), {"label": ""})).label
    check("카드에 이름만 표시",
          "민준" in card and "대화" not in card and "기억" not in card, repr(card))
    check("잠금 표시", "비밀번호 필요" in card, repr(card))
    if click(at, "민준", "카드 눌림"):
        check("비밀번호 화면으로 감", at.session_state["screen"] == "unlock")
        check("아직 입장 안 됨", at.session_state["profile"] is None)
        box = field(at, "비밀번호")
        check("비밀번호 칸 있음", box is not None)
        if box is not None:
            box.set_value("0000")
            click(at, "들어가기", "틀린 비밀번호 제출")
            check("틀린 비밀번호 거부", at.session_state["profile"] is None)
            field(at, "비밀번호").set_value("1234")
            click(at, "들어가기", "맞는 비밀번호 제출")
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

    print("\n[7-2] 관리자 화면은 비밀번호 없이 열리지 않는다")
    # 모든 아이의 대화가 보이는 화면이라, 비밀번호가 없으면 아예 닫혀야 합니다.
    os.environ.pop("ADMIN_PASSWORD", None)
    os.environ.pop("PARENT_PASSWORD", None)
    at4 = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at4.session_state["screen"] = "admin"
    at4.run()
    no_exception(at4, "오류 없이 렌더링")
    check("비밀번호 미설정이면 닫힘", not at4.session_state.filtered_state.get("admin_ok")
          and len(at4.error) > 0)

    os.environ["ADMIN_PASSWORD"] = "admin1234"
    at5 = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at5.session_state["screen"] = "admin"
    at5.run()
    no_exception(at5, "비밀번호 설정 후 렌더링")
    check("아직 안 열림", not at5.session_state.filtered_state.get("admin_ok"))
    box = field(at5, "관리자 비밀번호")
    check("관리자 비밀번호 칸 있음", box is not None)
    if box is not None:
        box.set_value("틀린값")
        click(at5, "들어가기", "틀린 비밀번호 제출")
        check("틀린 비밀번호 거부", not at5.session_state.filtered_state.get("admin_ok"))
        field(at5, "관리자 비밀번호").set_value("admin1234")
        click(at5, "들어가기", "맞는 비밀번호 제출")
        check("맞는 비밀번호로 열림", bool(at5.session_state.filtered_state.get("admin_ok")))
        no_exception(at5, "관리자 화면 오류 없음")
    os.environ.pop("ADMIN_PASSWORD", None)

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
