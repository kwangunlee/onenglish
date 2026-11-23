"""
GitHub 의 최신 내용으로 이 폴더를 맞춥니다.

    python tools/update_from_github.py
    (또는 update.bat 더블클릭)

안전장치
  - .streamlit/secrets.toml 과 data/*.db 는 건드리지 않습니다.
    .gitignore 에 있어서 git 이 추적하지 않기 때문입니다.
  - 네가 직접 고친 파일이 있으면 지우지 않고 따로 보관(stash)한 뒤 알려줍니다.
  - 무엇이 바뀌는지 먼저 보여주고 물어봅니다.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REMOTE = "https://github.com/kwangunlee/onenglish.git"
BRANCH = "main"

KEEP = [".streamlit/secrets.toml", "data/onenglish.db"]


def git(*args, check=False):
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=check
    )


def fail(message: str) -> int:
    print(f"\n  [중단] {message}\n")
    return 1


def main() -> int:
    print("\n  OnEnglish — GitHub 최신 내용 받기")
    print(f"  폴더: {ROOT}\n")

    try:
        git("--version", check=True)
    except (OSError, subprocess.CalledProcessError):
        return fail("git 이 설치되어 있지 않습니다.")

    if not (ROOT / ".git").exists():
        return fail(
            "이 폴더가 git 저장소가 아닙니다.\n"
            "         push_to_github.bat 을 한 번 실행하면 만들어집니다."
        )

    # 원격 주소 맞추기
    if "origin" in git("remote").stdout.split():
        git("remote", "set-url", "origin", REMOTE)
    else:
        git("remote", "add", "origin", REMOTE)

    print("  최신 내용을 확인합니다...")
    fetched = git("fetch", "origin", BRANCH)
    if fetched.returncode != 0:
        return fail(f"받아오지 못했습니다:\n{fetched.stderr.strip()}")

    behind = git("rev-list", "--count", f"HEAD..origin/{BRANCH}").stdout.strip()
    changed = git("diff", "--name-only", "HEAD", f"origin/{BRANCH}").stdout.split()

    if not changed:
        print("\n  이미 최신입니다. 바꿀 게 없어요.\n")
        return 0

    print(f"\n  새 커밋 {behind or '?'}개, 바뀌는 파일 {len(changed)}개:\n")
    for name in changed[:40]:
        print(f"    {name}")
    if len(changed) > 40:
        print(f"    ... 외 {len(changed) - 40}개")

    # 내가 고친 파일이 있는지
    dirty = [
        line[3:] for line in git("status", "--porcelain").stdout.splitlines()
        if line and not line.startswith("??")
    ]
    if dirty:
        print("\n  직접 고친 파일이 있습니다:")
        for name in dirty[:10]:
            print(f"    {name}")
        print("\n  지우지 않고 따로 보관합니다. 나중에 'git stash pop' 으로 꺼낼 수 있어요.")

    print("\n  건드리지 않는 것:")
    for name in KEEP:
        mark = "있음" if (ROOT / name).exists() else "없음"
        print(f"    {name}  ({mark})")

    answer = input("\n  업데이트할까요? (y / 엔터=취소): ").strip().lower()
    if answer != "y":
        print("\n  취소했습니다.\n")
        return 0

    if dirty:
        git("stash", "push", "-m", "update_from_github 전 자동 보관")

    result = git("reset", "--hard", f"origin/{BRANCH}")
    if result.returncode != 0:
        return fail(f"업데이트 실패:\n{result.stderr.strip()}")

    print("\n  ─────────────────────────────────────────────")
    print("   업데이트 완료")
    print("  ─────────────────────────────────────────────")
    print(f"\n   {git('log', '--oneline', '-1').stdout.strip()}")
    print("\n   앱이 켜져 있으면 껐다 켜 주세요.")
    print("   (새 파일이 생겼을 수 있어서 새로고침만으로는 부족합니다)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
