"""
학습 목표 — 지금 어떤 목표가 걸려 있고, 대화가 그 목표를 얼마나 이뤘는지.

흐름
  - 목표가 없으면: 예전처럼 일상 대화.
  - 목표가 있고 아직 못 이뤘으면: 캐릭터가 친구처럼 자연스럽게 그 주제로 이끌고,
    핵심 단어를 자기 말에 섞어 들려주고, 아이가 그 단어를 말할 기회를 만든다.
  - 이루고 나면: 그 대화의 남은 부분과 그 뒤의 대화는 다시 일상 대화.

"이뤘다" =  아이가 핵심 단어를 (전부, 또는 관리자가 정한 개수만큼) 직접 말했고
            과제가 있으면 과제도 했다.
  - 단어는 아이가 한 말에서 코드로 셉니다 (돈이 들지 않고, 결과가 늘 같음).
  - 과제는 캐릭터가 대답할 때 같이 판단합니다 (대답 JSON 의 task_done).
    별도 호출이 없어서 추가 비용이 없습니다.

목표 고르기: 오늘 날짜가 기간 안에 있는 목표 중에서
  학생 개인 목표가 반 목표보다 먼저, 같은 종류면 가장 최근에 시작한 것.
"""

import re

from . import store


# ── 지금 걸린 목표 ───────────────────────────────────────────────

def active_goal(profile: dict, day: str | None = None) -> dict | None:
    day = day or store.today()
    current = [g for g in store.list_goals()
               if (g.get("start_on") or "") <= day <= (g.get("end_on") or "")]
    current.sort(key=lambda g: (g.get("start_on") or "", g.get("id") or 0), reverse=True)
    mine = [g for g in current
            if g["target_type"] == "profile" and g["target_id"] == profile["id"]]
    if mine:
        return mine[0]
    class_id = profile.get("class_id")
    if class_id in (None, ""):
        return None
    theirs = [g for g in current
              if g["target_type"] == "class" and g["target_id"] == int(class_id)]
    return theirs[0] if theirs else None


def already_achieved(profile_id: int, goal: dict) -> bool:
    return any(r["achieved"] and r["goal_id"] == goal["id"]
               for r in store.goal_results_for_profile(profile_id))


def goal_for_new_chat(profile: dict) -> dict | None:
    """새 대화가 목표로 삼을 것. 걸린 목표가 없거나 이미 이뤘으면 None(일상 대화)."""
    goal = active_goal(profile)
    if goal and not already_achieved(profile["id"], goal):
        return goal
    return None


def required_words(goal: dict) -> int:
    words = goal.get("words") or []
    return min(goal.get("min_words") or len(words), len(words))


# ── 단어 세기 ────────────────────────────────────────────────────
# "lion" 은 lions, "jump" 는 jumped/jumping 도 인정합니다. go → went 같은
# 불규칙 변화까지는 세지 않습니다 (필요하면 단어 칸에 둘 다 적으면 됩니다).

def _pattern(word: str) -> re.Pattern:
    parts = [re.escape(p) for p in re.findall(r"[a-z0-9']+", word.lower())]
    if not parts:
        return re.compile(r"(?!x)x")  # 아무것도 안 맞는 패턴
    body = r"\s+".join(p + r"(?:s|es|ed|d|ing)?" for p in parts)
    return re.compile(rf"(?<![a-z0-9']){body}(?![a-z0-9'])")


def words_said(goal: dict, messages: list[dict], role: str) -> list[str]:
    text = " ".join((m.get("content") or "").lower().replace("’", "'")
                    for m in messages if m.get("role") == role)
    return [w for w in (goal.get("words") or []) if _pattern(w).search(text)]


def progress(goal: dict, messages: list[dict], task_done: bool = False) -> dict:
    used = words_said(goal, messages, "user")
    heard = words_said(goal, messages, "assistant")
    words_ok = len(used) >= required_words(goal)
    task_ok = (not goal.get("task")) or bool(task_done)
    return {
        "used": used,
        "heard": heard,
        "remaining": [w for w in goal.get("words") or [] if w not in used],
        "need": required_words(goal),
        "task_done": (bool(task_done) if goal.get("task") else None),
        "achieved": words_ok and task_ok,
    }


def save(session_id: str, profile_id: int, goal: dict, prog: dict) -> None:
    store.save_goal_result(
        session_id, goal["id"], profile_id, prog["used"], prog["heard"],
        prog["task_done"], prog["achieved"],
    )


# ── 캐릭터에게 주는 지시 ─────────────────────────────────────────

def prompt_block(goal: dict, prog: dict) -> str:
    """대화 프롬프트에 붙일 목표 안내. 아이에게는 '수업'이 보이면 안 됩니다."""
    if prog["achieved"]:
        return (
            "\n\n[Today's plan is finished]\n"
            f"Your friend already talked about \"{goal['topic']}\" and said the words you "
            "hoped for. Now just chat freely about everyday things, whatever your friend "
            "likes. Do NOT steer back to that topic and do NOT push those words anymore."
        )
    lines = [
        "\n\n[Today's chat plan — a secret plan from your friend's teacher]",
        f"- Topic: {goal['topic']}. If you are not talking about it yet, bring it up "
        "naturally as your own idea within your next reply (something you did, saw or "
        "like that is about this topic).",
    ]
    if prog["remaining"]:
        lines.append(
            "- Words your friend has NOT said yet: " + ", ".join(prog["remaining"]) + ". "
            "Use one of them in your own sentence so your friend hears it, then ask a "
            "question that makes it easy for your friend to SAY it — for example a choice "
            "with the word inside ('Did you see a lion or a tiger?')."
        )
    if prog["used"]:
        lines.append("- Words your friend already said (great, move on): "
                     + ", ".join(prog["used"]) + ".")
    if goal.get("expressions"):
        lines.append("- Expressions to use in your own sentences now and then: "
                     + " / ".join(goal["expressions"]) + ".")
    if goal.get("task") and not prog["task_done"]:
        lines.append(f"- Little task for your friend: {goal['task']}. Lead them to it "
                     "gently, one small step at a time, as part of the chat.")
    lines.append(
        "- Never say 'today we will learn', never quiz, never list the words, never "
        "mention a plan or a teacher. You are still just a friend chatting. "
        "Keep following your length and question rules."
    )
    return "\n".join(lines)


def task_note(goal: dict) -> str | None:
    """대답 JSON 의 task_done 칸을 어떻게 채울지 (과제가 있을 때만)."""
    if not goal.get("task"):
        return None
    return (f"task_done: true only if, in this chat so far, your friend has actually "
            f"done this: {goal['task']}. Otherwise false.")


def opener_hint(goal: dict) -> str:
    """첫 인사에서 목표 주제로 시작하게 하는 안내."""
    words = ", ".join((goal.get("words") or [])[:3])
    hint = (
        "[What to say]\n"
        f"Today you want to chat about: {goal['topic']}. Bring it up as your own idea "
        "(something you did, saw or like about it), then ask one easy question about it."
    )
    if words:
        hint += f" Try to use one of these words: {words}."
    hint += " Do not mention a plan, a lesson, or past chats."
    return hint
