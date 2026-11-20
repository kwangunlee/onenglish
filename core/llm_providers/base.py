"""
대화 프로바이더의 공통 규격.

두 가지만 할 줄 알면 됩니다.
  chat()       — 캐릭터로서 한 마디 (평문)
  structured() — 정해진 형식의 JSON (답변+기분, 기억 추출에 사용)

새 프로바이더를 추가하려면 Provider 를 상속해서 만들고 __init__.py 의
레지스트리에 한 줄 더하면 됩니다.
"""

from typing import Any


class Provider:
    id: str = ""
    name: str = ""

    def is_available(self) -> bool:
        raise NotImplementedError

    def unavailable_reason(self) -> str:
        return f"{self.name} 을(를) 사용할 수 없습니다."

    def model_label(self) -> str:
        """설정 화면·진단 도구에 보여줄 모델 이름."""
        return ""

    def chat(
        self,
        system_prompt: str,
        history: list[dict],
        user_text: str,
        max_tokens: int = 160,
        temperature: float = 0.85,
    ) -> str:
        raise NotImplementedError

    def structured(
        self,
        system_prompt: str,
        user_text: str,
        schema: dict[str, Any],
        temperature: float = 0.2,
        max_tokens: int = 600,
        history: list[dict] | None = None,
    ) -> dict:
        """schema 에 맞는 JSON 객체를 돌려줍니다.

        schema 는 JSON Schema 형식으로 적습니다. 프로바이더마다 요구하는
        형식이 달라서 각자 알아서 변환합니다."""
        raise NotImplementedError


def clean_history(history: list[dict] | None, max_turns: int) -> list[dict]:
    """최근 max_turns 쌍만 남기고, role 이 이상한 항목은 버립니다."""
    clean = [
        {"role": m["role"], "content": m["content"]}
        for m in (history or [])
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    keep = max_turns * 2
    return clean[-keep:] if keep > 0 else clean
