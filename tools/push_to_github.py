"""
GitHub 에 올리기.

    python tools/push_to_github.py
    (또는 push_to_github.bat 더블클릭)

올리기 전에 비밀정보가 섞여 있지 않은지 먼저 검사합니다. 하나라도 걸리면
올리지 않고 멈춥니다. secrets.toml 과 대화 기록 DB 는 .gitignore 때문에
처음부터 대상이 아닙니다.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REMOTE = "https://github.com/kwangunlee/onenglish.git"
BRANCH = "main"

COMMIT_MESSAGE = """OnEnglish: 어린이 일상 영어 대화 친구

2년 전 tkinter 버전을 스트림릿 기반으로 다시 만들었습니다.

주요 변경
- 화면: tkinter + subprocess 다중 프로세스 -> 스트림릿 단일 앱
- 음성인식: Google STT 스트리밍 -> OpenAI Whisper (5분 제한 제거)
- 음성합성: 프로바이더 교체 구조 (OpenAI / Google)
- 저장: Firebase -> 로컬 SQLite
- 의존성 9개(pyaudio 포함) -> 2개

새 기능
- 기억: 대화에서 날짜/활동/대상을 뽑아 저장하고 다음 대화에 주입
- 학습 기록: 반복되는 실수를 모아 부모용 리포트
- 프로필별 비밀번호 (pbkdf2 해시, 입장 전 기록 비공개)
- 캐릭터 팩 플러그인 구조 (폴더 추가로 확장)

보안
- API 키를 코드에서 분리 (secrets.toml, gitignore)
- Firebase Admin SDK 자격증명 제거
- 아이 음성 공개 URL 업로드 코드 제거
- 저작권 캐릭터 -> 자체 캐릭터

고친 버그
- AI 응답을 system 역할로 저장하던 문제 (DB CHECK 제약으로 재발 방지)
- TTS instruction 오타로 말투 연출이 무시되던 문제
- 말풍선 이중 출력, 배경이 글씨를 덮던 문제
- TTS 재생 중 UI 정지, 백그라운드 스레드의 UI 조작
"""

# 실제 키처럼 생긴 것들
PATTERNS = {
    "OpenAI API 키": re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    "Google API 키": re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    "서비스 계정 비밀키": re.compile(r'"private_key"\s*:\s*"-----BEGIN'),
}
# 예시/테스트용이라 괜찮은 것들
SAFE_HINTS = ("여기에", "붙여넣기", "sk-test-", "YOUR_", "example")

BINARY = {".png", ".jpg", ".jpeg", ".svg", ".mp3", ".mp4", ".zip", ".db"}


def run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=check)


def fail(message: str) -> int:
    print(f"\n  [중단] {message}\n")
    return 1


def main() -> int:
    print("\n  OnEnglish — GitHub 에 올리기")
    print(f"  폴더: {ROOT}")
    print(f"  대상: {REMOTE}\n")

    # 1. git 확인
    try:
        run(["git", "--version"])
    except (OSError, subprocess.CalledProcessError):
        return fail(
            "git 이 설치되어 있지 않습니다.\n"
            "         https://git-scm.com/download/win 에서 설치한 뒤\n"
            "         다시 실행해 주세요."
        )

    # 2. 저장소 준비
    if not (ROOT / ".git").exists():
        print("  저장소를 새로 만듭니다...")
        run(["git", "init", "-q", "-b", BRANCH])
    run(["git", "add", "-A"])

    staged = run(["git", "diff", "--cached", "--name-only"]).stdout.split()
    if not staged:
        tracked = run(["git", "ls-files"]).stdout.split()
        if not tracked:
            return fail("올릴 파일이 없습니다.")
        print("  바뀐 파일이 없습니다. 올라가 있는 내용 그대로 밀어넣습니다.\n")

    # 3. 비밀정보 검사
    print("  비밀정보를 검사합니다...")
    problems = []
    for name in staged:
        path = ROOT / name
        if path.suffix.lower() in BINARY or not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pattern in PATTERNS.items():
            for hit in pattern.findall(text):
                around = text[max(0, text.find(hit) - 60): text.find(hit) + 60]
                if any(h in around or h in hit for h in SAFE_HINTS):
                    continue
                problems.append(f"{name} — {label} ({hit[:14]}...)")

    for must_block in ("data/onenglish.db", ".streamlit/secrets.toml"):
        if must_block in staged:
            problems.append(f"{must_block} — 올라가면 안 되는 파일입니다")

    if problems:
        print()
        for p in problems:
            print(f"    ✗ {p}")
        return fail(
            "비밀정보로 보이는 내용이 있어 올리지 않았습니다.\n"
            "         위 파일에서 키를 지우고 다시 실행해 주세요."
        )

    print(f"    ✓ 이상 없음 ({len(staged) or len(run(['git','ls-files']).stdout.split())}개 파일)\n")

    # 4. 커밋
    if staged:
        msg_file = ROOT / ".git" / "COMMIT_MSG_TMP"
        msg_file.write_text(COMMIT_MESSAGE, encoding="utf-8")
        if not run(["git", "config", "user.name"], check=False).stdout.strip():
            run(["git", "config", "user.name", "kwangunlee"])
            run(["git", "config", "user.email",
                 "kwangunlee@users.noreply.github.com"])
        result = run(["git", "commit", "-F", str(msg_file)], check=False)
        msg_file.unlink(missing_ok=True)
        if result.returncode != 0 and "nothing to commit" not in result.stdout:
            return fail(f"커밋 실패:\n{result.stdout}{result.stderr}")
        print("  커밋했습니다.")

    run(["git", "branch", "-M", BRANCH], check=False)

    # 5. 원격 연결
    remotes = run(["git", "remote"], check=False).stdout.split()
    if "origin" in remotes:
        run(["git", "remote", "set-url", "origin", REMOTE])
    else:
        run(["git", "remote", "add", "origin", REMOTE])

    # 6. 올리기
    print("\n  GitHub 로 올립니다...")
    print("  (로그인 창이 뜨면 GitHub 계정으로 로그인해 주세요)\n")
    result = subprocess.run(
        ["git", "push", "-u", "origin", BRANCH], cwd=ROOT, text=True
    )
    if result.returncode != 0:
        return fail(
            "올리지 못했습니다.\n"
            "         · GitHub 로그인이 취소되지 않았는지\n"
            "         · 저장소 주소가 맞는지 확인해 주세요:\n"
            f"           {REMOTE}"
        )

    print("\n  ─────────────────────────────────────────────")
    print("   올렸습니다.")
    print("  ─────────────────────────────────────────────")
    print("\n   https://github.com/kwangunlee/onenglish")
    print("\n   다음 단계: https://share.streamlit.io 에서")
    print("   Create app → onenglish → Main file path 를 app.py 로\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
