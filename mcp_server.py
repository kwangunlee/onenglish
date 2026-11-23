"""
MCP 서버 (선택 기능 — 지금 당장은 안 써도 됩니다).

core/ 가 streamlit 을 전혀 모르는 순수 Python 이기 때문에, 같은 엔진을 이렇게
MCP 서버로도 노출할 수 있습니다. 그러면 Claude Desktop 같은 MCP 클라이언트에서
같은 캐릭터·같은 기억을 그대로 쓸 수 있습니다.

쓰려면 먼저 설치하세요 (requirements.txt 에는 일부러 넣지 않았습니다):
    pip install mcp

실행:
    python mcp_server.py

Claude Desktop 설정 예시 (claude_desktop_config.json):
    {
      "mcpServers": {
        "onenglish": {
          "command": "python",
          "args": ["C:/전체/경로/onenglish/mcp_server.py"],
          "env": { "OPENAI_API_KEY": "sk-..." }
        }
      }
    }

이 파일은 스트림릿 앱과 완전히 독립적입니다. 지우거나 무시해도 앱은 잘 돌아갑니다.
"""

import json
import sys

from core import llm, memory, packs, store


def _require_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        sys.exit(
            "mcp 패키지가 필요합니다.\n"
            "    pip install mcp\n"
            "설치 후 다시 실행해 주세요."
        )
    return FastMCP


FastMCP = _require_mcp()
mcp = FastMCP("onenglish")

store.init_db()


def _find_profile(name: str) -> dict | None:
    for p in store.list_profiles():
        if p["name"] == name:
            return p
    return None


@mcp.tool()
def list_profiles() -> str:
    """등록된 사람 목록과 각자의 대화·기억 개수를 반환합니다."""
    out = []
    for p in store.list_profiles():
        stats = store.profile_stats(p["id"])
        out.append({"name": p["name"], "level": p["level"], **stats})
    return json.dumps(out, ensure_ascii=False, indent=2)


@mcp.tool()
def list_characters(level: str = "kids") -> str:
    """해당 레벨에서 쓸 수 있는 캐릭터 목록을 반환합니다."""
    out = [
        {
            "id": c["id"],
            "name": c["name"],
            "tagline": c.get("tagline", ""),
            "voice": c.get("voice", ""),
        }
        for c in packs.characters_for_level(level)
    ]
    return json.dumps(out, ensure_ascii=False, indent=2)


@mcp.tool()
def get_memories(profile_name: str, limit: int = 20) -> str:
    """특정 사람에 대해 기억하고 있는 것들을 반환합니다."""
    profile = _find_profile(profile_name)
    if not profile:
        return f"'{profile_name}' 을(를) 찾을 수 없습니다."
    rows = store.recent_memories(profile["id"], limit)
    out = [
        {
            "date": r.get("occurred_on"),
            "kind": r["kind"],
            "ko": r["summary_ko"],
            "en": r["summary_en"],
            "people": r["people"],
        }
        for r in rows
    ]
    return json.dumps(out, ensure_ascii=False, indent=2)


@mcp.tool()
def get_learning_log(profile_name: str, limit: int = 30) -> str:
    """특정 사람의 학습 기록(자주 틀리는 표현 등)을 반환합니다."""
    profile = _find_profile(profile_name)
    if not profile:
        return f"'{profile_name}' 을(를) 찾을 수 없습니다."
    return json.dumps(
        store.frequent_mistakes(profile["id"], limit), ensure_ascii=False, indent=2
    )


@mcp.tool()
def chat(profile_name: str, character_id: str, message: str) -> str:
    """캐릭터로서 한 번 대답합니다. 지난 기억이 반영됩니다.

    주의: 이 도구는 대화를 저장하지 않습니다. 저장이 필요하면 스트림릿 앱을
    쓰거나 여기에 store.add_message 호출을 추가하세요."""
    profile = _find_profile(profile_name)
    if not profile:
        return f"'{profile_name}' 을(를) 찾을 수 없습니다."

    character = packs.get_character(character_id)
    if not character:
        return f"'{character_id}' 캐릭터를 찾을 수 없습니다."

    level = packs.get_level(store.effective_level(profile)) or {}
    memories, learning = memory.recall(profile["id"])

    try:
        answer = llm.reply(
            character=character,
            level=level,
            history=[],
            user_text=message,
            memories=memories,
            learning=learning,
            child_name=profile["name"],
        )
        return json.dumps(
            {"reply": answer.text, "mood": answer.mood},
            ensure_ascii=False, indent=2,
        )
    except llm.LLMError as e:
        return str(e)


if __name__ == "__main__":
    mcp.run()
