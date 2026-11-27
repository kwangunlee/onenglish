"""Word Trails lessons, completion grading and Streamlit views."""
import json
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import streamlit as st
from streamlit.components.v1 import declare_component

from core import store


ROOT = Path(__file__).resolve().parent
game = declare_component("word_trails", path=str(ROOT / "word_trails"))


@lru_cache(maxsize=1)
def courses():
    return json.loads((ROOT / "data" / "word_trails.json").read_text(encoding="utf-8"))


def grade(event, session):
    if not isinstance(event, dict) or event.get("session") != session:
        raise ValueError("다시 입장한 뒤 새 게임을 시작해 주세요.")
    index = event.get("course")
    if type(index) is not int or not 0 <= index < len(courses()):
        raise ValueError("알 수 없는 코스예요.")
    try:
        round_id = UUID(str(event.get("round")))
    except ValueError:
        raise ValueError("게임 번호를 확인할 수 없어요.") from None
    attempts = event.get("attempts")
    vocabulary = {entry[0] for entry in courses()[index]["entries"]}
    if not isinstance(attempts, dict) or len(attempts) != 6 or not vocabulary.issuperset(attempts):
        raise ValueError("완주한 단어 목록을 확인할 수 없어요.")
    words = list(attempts)
    review = []
    for word, choices in attempts.items():
        if (not isinstance(choices, list) or not 1 <= len(choices) <= 3
                or not all(isinstance(c, str) and c in attempts for c in choices)
                or choices[-1] != word or len(set(choices)) != len(choices)):
            raise ValueError("문장 풀이 기록이 완성되지 않았어요.")
        if len(choices) > 1:
            review.append(word)
    return {
        "id": str(uuid5(UUID(session), str(round_id))), "course": index,
        "words": words, "review": review, "score": 2 * len(words) - len(review),
    }


def history(rows):
    if not rows:
        st.caption("첫 코스를 완주하면 여기에 점수가 쌓여요.")
        return
    st.caption(f"완주 {len(rows)}회 · 누적 {sum(r['score'] for r in rows)}점 · 최고 {max(r['score'] for r in rows)} / 12점")
    st.dataframe([{
        "완주 시각 (한국)": datetime.fromisoformat(r["created_at"]).astimezone(
            timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"),
        "코스": courses()[r["course"]]["ko"], "점수 (12점 만점)": r["score"],
        "첫 시도 정답": len(r["words"]) - len(r["review"]),
        "찾은 단어": ", ".join(r["words"]), "다시 연습할 단어": ", ".join(r["review"]) or "모두 맞혔어요",
    } for r in rows], hide_index=True, width="stretch")


def screen(profile):
    pid = profile["id"]
    state = st.session_state
    if state.get("trail_player") != pid or "trail_session" not in state:
        state.trail_player, state.trail_session, state.trail_saved = pid, str(uuid4()), None
    rows = store.trail_results(pid)
    event = game(courses=courses(), profile=pid, session=state.trail_session,
                 stamps=sorted({r["course"] for r in rows}), saved=state.trail_saved,
                 key="word_trails_" + state.trail_session, default=None)
    already_saved = isinstance(event, dict) and state.trail_saved and state.trail_saved == event.get("round")
    if event is not None and not already_saved:
        try:
            result = grade(event, state.trail_session)
        except ValueError as exc:
            st.error(str(exc))
        else:
            try:
                store.save_trail_result(pid, result)
            except Exception:
                st.error("점수를 저장하지 못했어요. 이 화면에서 다시 시도해 주세요.")
                st.button("점수 저장 다시 시도")
            else:
                state.trail_saved = event["round"]
                st.rerun()
    st.subheader(f"{profile['name']}의 점수판")
    st.caption("찾은 단어마다 1점, 첫 시도에 맞힌 문장마다 1점이에요. 한 판에 최대 12점이에요.")
    history(rows)


def leaderboard(profiles, classes):
    st.title("Word Trails 점수판")
    names = {c["id"]: c["name"] for c in classes}
    selected = st.selectbox("반", [None, *names], format_func=lambda c: names.get(c, "전체 반"))
    ranking = []
    for profile in profiles:
        cid = profile.get("class_id")
        if selected is not None and cid != selected:
            continue
        rows = store.trail_results(profile["id"])
        if rows:
            ranking.append({"학생": profile["name"], "반": names.get(cid, "미배정"),
                            "누적 점수": sum(r["score"] for r in rows), "완주 횟수": len(rows),
                            "한 판 최고점": max(r["score"] for r in rows)})
    if ranking:
        ranking.sort(key=lambda r: (-r["누적 점수"], -r["한 판 최고점"], r["학생"]))
        st.dataframe(ranking, hide_index=True, width="stretch")
    else:
        st.info("아직 이 반에 완주 기록이 없어요.")
