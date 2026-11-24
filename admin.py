"""
OnEnglish — 관리자 화면.

실행:
    streamlit run admin.py --server.port 8502
    (윈도우: admin.bat 더블클릭)

app.py의 프로필 선택 화면에서도 관리자 화면을 열 수 있습니다.
같은 저장소를 사용하므로 변경 사항은 학생 화면에도 반영됩니다.

할 수 있는 것
  - 학생 전체 현황 (반, 수준, 대화 수, 말한 횟수, 기억, 마지막 접속)
  - 학생별 대화 기록 보기 · 대화 삭제
  - 기억 · 학습 기록 보기 · 삭제
  - 학생 추가 · 이름/레벨/반 수정 · 비밀번호 재설정 · 학생 삭제
  - 반 관리: 반 만들기 · 반마다 수준(입문/초급/중급) · 학생 배정 · 반 삭제
    (반에 넣은 학생은 반의 수준으로 대화합니다. 수준은 data/levels.json)

비밀번호는 원래 값을 알 수 없게(해시) 저장하므로 "보기"는 안 되고 "재설정"만
됩니다. 관리자도 아이 비밀번호를 볼 수 없는 게 안전한 구조입니다.

들어가는 비밀번호: secrets 의 ADMIN_PASSWORD (없으면 PARENT_PASSWORD).
둘 다 없으면 화면이 열리지 않습니다. 모든 아이의 대화가 보이는 화면이기 때문입니다.
"""

import hmac
from datetime import date
import json
import os

import streamlit as st



# ── secrets → 환경변수 (app.py 와 같은 방식) ──────────────────────
def _bridge_secrets() -> None:
    try:
        secrets = st.secrets
        keys = list(secrets.keys())
    except Exception:
        return
    for key in keys:
        try:
            value = secrets[key]
        except Exception:
            continue
        if key == "gcp_service_account":
            os.environ["GCP_SERVICE_ACCOUNT_JSON"] = json.dumps(dict(value))
        elif isinstance(value, (str, int, float)) and str(value).strip():
            os.environ[key] = str(value).strip()


if __name__ == "__main__":
    st.set_page_config(page_title="OnEnglish 관리자", page_icon="🗂️", layout="wide")
    _bridge_secrets()

from core import config, goals, packs, store  # noqa: E402

KIND_LABEL = {
    "activity": "활동", "person": "사람", "favorite": "좋아하는 것",
    "event": "사건", "other": "기타",
}


def short_time(value: str | None) -> str:
    return (value or "")[:16].replace("T", " ") or "-"


def flash(message: str, kind: str = "success") -> None:
    st.session_state.admin_flash = (kind, message)


def show_flash() -> None:
    item = st.session_state.pop("admin_flash", None)
    if item:
        kind, message = item
        getattr(st, kind, st.info)(message)


# ── 들어가기 ─────────────────────────────────────────────────────

def gate() -> bool:
    required = config.admin_password()
    if not required:
        st.title("관리자 화면")
        st.error(
            "관리자 비밀번호가 설정되어 있지 않아 열 수 없어요.\n\n"
            "`.streamlit/secrets.toml` 에 `ADMIN_PASSWORD = \"...\"` 를 넣고 "
            "다시 실행해 주세요. (모든 아이의 대화가 보이는 화면이라 비밀번호가 꼭 필요합니다)"
        )
        return False
    if st.session_state.get("admin_ok"):
        return True

    st.title("관리자 화면")
    with st.form("admin_gate"):
        value = st.text_input("관리자 비밀번호", type="password")
        if st.form_submit_button("들어가기", type="primary"):
            if hmac.compare_digest(value.encode(), required.encode()):
                st.session_state.admin_ok = True
                st.rerun()
            st.error("비밀번호가 맞지 않아요.")
    return False


# ── 왼쪽: 학생 고르기 · 추가 ─────────────────────────────────────

def sidebar(profiles: list[dict]) -> int | None:
    with st.sidebar:
        st.markdown("### 학생")
        labels = ["📋 전체 현황", "🏫 반 관리", "🎯 학습 목표"] + [p["name"] for p in profiles]
        ids = [None, "classes", "goals"] + [p["id"] for p in profiles]
        current = st.session_state.get("admin_selected")
        index = ids.index(current) if current in ids else 0
        choice = st.radio("학생", labels, index=index, label_visibility="collapsed")
        selected = ids[labels.index(choice)]
        st.session_state.admin_selected = selected

        st.divider()
        with st.expander("➕ 새 학생 추가"):
            with st.form("add_student", clear_on_submit=True):
                name = st.text_input("이름")
                password = st.text_input("비밀번호", type="password")
                level = level_select("레벨", packs.default_level_id(), key="new_level")
                if st.form_submit_button("추가", type="primary"):
                    try:
                        created = store.create_profile(name, level, password)
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        st.session_state.admin_selected = created["id"]
                        flash(f"'{created['name']}' 학생을 추가했어요.")
                        st.rerun()

        st.divider()
        st.caption(f"저장소: **{config.db_backend()}**")
        if st.button("로그아웃", width="stretch"):
            st.session_state.admin_ok = False
            st.rerun()
    return selected


def level_name(level_id: str | None) -> str:
    level = packs.get_level(level_id or "") or {}
    return level.get("name") or (level_id or "-")


def class_name(class_id, classes: list[dict]) -> str:
    found = next((c for c in classes if c["id"] == class_id), None)
    return found["name"] if found else "-"


def level_select(label: str, current: str, key: str) -> str:
    levels = packs.load_levels()
    ids = list(levels) or [current]
    if current not in ids:
        ids.append(current)
    return st.selectbox(
        label, ids, index=ids.index(current), key=key,
        format_func=lambda i: (f"{levels.get(i, {}).get('name', i)} — "
                               f"{levels.get(i, {}).get('description', '')}"),
    )


# ── 전체 현황 ────────────────────────────────────────────────────

def overview(profiles: list[dict], classes: list[dict]) -> None:
    st.title("전체 현황")
    show_flash()
    if not profiles:
        st.info("아직 학생이 없어요. 왼쪽 '새 학생 추가'로 만들어 주세요.")
        return
    rows = []
    for p in profiles:
        stats = store.profile_stats(p["id"])
        rows.append({
            "이름": p["name"],
            "반": class_name(p.get("class_id"), classes),
            "수준": level_name(store.effective_level(p)),
            "비밀번호": "있음" if store.profile_has_password(p) else "없음 ⚠️",
            "대화": stats["sessions"],
            "아이가 말한 횟수": stats["child_turns"],
            "기억": stats["memories"],
            "학습 기록": stats["learning"],
            "마지막 접속": short_time(p.get("last_seen_at")),
        })
    st.dataframe(rows, hide_index=True, width="stretch")
    if any(not store.profile_has_password(p) for p in profiles):
        st.warning("비밀번호가 없는 학생은 첫 화면에서 누구나 들어갈 수 있어요. "
                   "학생을 고른 뒤 '비밀번호' 탭에서 정해 주세요.")
    st.caption("왼쪽에서 학생 이름을 누르면 대화 기록과 관리 메뉴가 나옵니다.")


# ── 학생 한 명 ───────────────────────────────────────────────────

def student(profile: dict, classes: list[dict], profiles: list[dict]) -> None:
    pid = profile["id"]
    stats = store.profile_stats(pid)
    st.title(profile["name"])
    st.caption(
        f"반 {class_name(profile.get('class_id'), classes)} · "
        f"수준 {level_name(store.effective_level(profile))} · 대화 {stats['sessions']}번 · "
        f"말한 횟수 {stats['child_turns']} · 기억 {stats['memories']} · "
        f"학습 기록 {stats['learning']} · 마지막 접속 {short_time(profile.get('last_seen_at'))}"
    )
    show_flash()

    tabs = st.tabs(["💬 대화 기록", "🎯 학습 목표", "🧠 기억", "📝 학습 기록",
                    "✏️ 학생 정보", "🔑 비밀번호", "🗑️ 학생 삭제"])
    with tabs[0]:
        conversations(profile)
    with tabs[1]:
        student_goals(profile, profiles, classes)
    with tabs[2]:
        memories(pid)
    with tabs[3]:
        learning(pid)
    with tabs[4]:
        edit_info(profile, classes)
    with tabs[5]:
        reset_password(profile)
    with tabs[6]:
        delete_student(profile)


def conversations(profile: dict) -> None:
    sessions = store.list_sessions(profile["id"], 100)
    if not sessions:
        st.caption("아직 대화가 없어요.")
        return
    for s in sessions:
        character = packs.get_character(s["character_id"])
        who = character["name"] if character else s["character_id"]
        state = "끝남" if s.get("ended_at") else "진행 중/창 닫음"
        title = f"{short_time(s['started_at'])} · {who} · 메시지 {s['message_count']}개 · {state}"
        with st.expander(title):
            for m in store.get_messages(s["id"]):
                is_child = m["role"] == "user"
                with st.chat_message("user" if is_child else "assistant",
                                     avatar="🙂" if is_child else "⭐"):
                    st.markdown(f"**{profile['name'] if is_child else who}** "
                                f"<span style='color:#999;font-size:.8em'>"
                                f"{short_time(m.get('created_at'))[11:]}</span>",
                                unsafe_allow_html=True)
                    st.text(m["content"])
            st.divider()
            sure = st.checkbox("이 대화를 지울게요 (되돌릴 수 없음)", key=f"sure_s_{s['id']}")
            if st.button("대화 삭제", key=f"del_s_{s['id']}", disabled=not sure):
                store.delete_session(s["id"])
                flash("대화를 지웠어요.")
                st.rerun()


def memories(pid: int) -> None:
    rows = store.all_memories(pid)
    if not rows:
        st.caption("아직 기억이 없어요. 아이가 '대화 끝내기'를 누르면 정리돼서 쌓입니다.")
        return
    for m in rows:
        left, right = st.columns([8, 1])
        with left:
            meta = " · ".join(x for x in (
                m.get("occurred_on"), KIND_LABEL.get(m.get("kind"), m.get("kind")),
                ", ".join(m.get("people") or []),
            ) if x)
            st.markdown(f"**{m.get('summary_ko') or ''}**  \n{m.get('summary_en') or ''}")
            extra = meta
            if m.get("followup"):
                asked = "물어봄" if m.get("opener_used_at") else "아직 안 물어봄"
                extra += (f"  \n다음에 물어볼 것: {m['followup']} "
                          f"({m.get('ask_after') or '-'} ~ {m.get('expires_on') or '-'}, {asked})")
            st.caption(extra)
        with right:
            if st.button("삭제", key=f"del_m_{m['id']}"):
                store.delete_memory(m["id"])
                flash("기억을 지웠어요.")
                st.rerun()
        st.divider()


def learning(pid: int) -> None:
    rows = store.recent_learning(pid, 200)
    if not rows:
        st.caption("아직 학습 기록이 없어요.")
        return
    for e in rows:
        left, right = st.columns([8, 1])
        with left:
            kind = "실수" if e.get("kind") == "mistake" else "새 표현"
            said = e.get("child_said") or ""
            better = e.get("better_form") or ""
            line = f"**[{kind}]** "
            line += f"{said} → **{better}**" if said else f"**{better}**"
            st.markdown(line)
            st.caption(" · ".join(x for x in (e.get("note_ko"), short_time(e.get("created_at"))) if x))
        with right:
            if st.button("삭제", key=f"del_l_{e['id']}"):
                store.delete_learning_entry(e["id"])
                flash("학습 기록을 지웠어요.")
                st.rerun()


def edit_info(profile: dict, classes: list[dict]) -> None:
    class_ids = [None] + [c["id"] for c in classes]
    current_class = profile.get("class_id") if profile.get("class_id") in class_ids else None
    with st.form(f"edit_{profile['id']}"):
        name = st.text_input("이름", value=profile["name"])
        chosen_class = st.selectbox(
            "반", class_ids, index=class_ids.index(current_class),
            key=f"class_{profile['id']}",
            format_func=lambda i: "반 없음" if i is None else
            f"{class_name(i, classes)} ({level_name(next(c['level'] for c in classes if c['id'] == i))})",
        )
        level = level_select("개인 레벨 (반이 없을 때만 쓰임)",
                             profile.get("level") or packs.default_level_id(),
                             key=f"level_{profile['id']}")
        if st.form_submit_button("저장", type="primary"):
            try:
                store.update_profile(profile["id"], name=name, level=level)
                store.set_profile_class(profile["id"], chosen_class)
            except ValueError as e:
                st.error(str(e))
            else:
                flash("저장했어요.")
                st.rerun()
    st.caption("반에 넣으면 반의 수준으로 대화합니다. 이름을 바꾸면 아이들 첫 화면의 "
               "이름도 바로 바뀝니다. 바뀐 반·수준은 아이가 다음 대화를 시작할 때부터 적용됩니다.")


def reset_password(profile: dict) -> None:
    has = store.profile_has_password(profile)
    st.write(f"지금 비밀번호: **{'있음' if has else '없음'}**")
    st.caption("비밀번호는 원래 값을 알 수 없게 저장돼서 볼 수는 없어요. "
               "잊었다면 여기서 새로 정해 주세요.")
    with st.form(f"pw_{profile['id']}", clear_on_submit=True):
        first = st.text_input("새 비밀번호", type="password")
        second = st.text_input("한 번 더", type="password")
        if st.form_submit_button("비밀번호 저장", type="primary"):
            if first != second:
                st.error("두 비밀번호가 달라요.")
            else:
                try:
                    store.set_profile_password(profile["id"], first)
                except ValueError as e:
                    st.error(str(e))
                else:
                    flash("비밀번호를 새로 정했어요.")
                    st.rerun()


def delete_student(profile: dict) -> None:
    st.warning(f"'{profile['name']}' 학생과 모든 대화·기억·학습 기록을 지웁니다. "
               "되돌릴 수 없어요.")
    typed = st.text_input("확인을 위해 학생 이름을 그대로 입력하세요",
                          key=f"confirm_{profile['id']}")
    if st.button("학생 삭제", type="primary", disabled=typed.strip() != profile["name"],
                 key=f"del_p_{profile['id']}"):
        store.delete_profile(profile["id"])
        st.session_state.admin_selected = None
        flash(f"'{profile['name']}' 학생을 지웠어요.")
        st.rerun()


# ── 반 관리 ──────────────────────────────────────────────────────

def classes_page(profiles: list[dict], classes: list[dict]) -> None:
    st.title("반 관리")
    show_flash()
    st.caption("반마다 수준을 정하면, 그 반 학생들은 그 수준에 맞는 말투와 질문으로 "
               "대화합니다. 학생은 한 반에만 들어갈 수 있어요.")

    with st.expander("➕ 새 반 만들기", expanded=not classes):
        with st.form("add_class", clear_on_submit=True):
            name = st.text_input("반 이름", placeholder="예: 월수 4시반")
            level = level_select("수준", packs.default_level_id(), key="new_class_level")
            memo = st.text_input("메모 (선택)", placeholder="예: 7세 3명, 영어 처음")
            if st.form_submit_button("만들기", type="primary"):
                try:
                    created = store.create_class(name, level, memo)
                except ValueError as e:
                    st.error(str(e))
                else:
                    flash(f"'{created['name']}' 반을 만들었어요.")
                    st.rerun()

    if not classes:
        st.info("아직 반이 없어요.")
        return

    st.dataframe([
        {"반": c["name"], "수준": level_name(c["level"]),
         "학생 수": sum(1 for p in profiles if p.get("class_id") == c["id"]),
         "학생": ", ".join(p["name"] for p in profiles if p.get("class_id") == c["id"]),
         "메모": c.get("memo") or ""}
        for c in classes
    ], hide_index=True, width="stretch")

    for c in classes:
        members = [p for p in profiles if p.get("class_id") == c["id"]]
        with st.expander(f"🏫 {c['name']} · {level_name(c['level'])} · 학생 {len(members)}명"):
            with st.form(f"class_{c['id']}"):
                new_name = st.text_input("반 이름", value=c["name"])
                new_level = level_select("수준", c["level"], key=f"class_level_{c['id']}")
                new_memo = st.text_input("메모", value=c.get("memo") or "")
                picked = st.multiselect(
                    "이 반 학생", [p["id"] for p in profiles],
                    default=[p["id"] for p in members],
                    format_func=lambda pid: next(
                        (f"{p['name']}" + (f"  (지금: {class_name(p.get('class_id'), classes)})"
                                           if p.get("class_id") not in (None, c["id"]) else "")
                         for p in profiles if p["id"] == pid), str(pid)),
                    help="다른 반 학생을 고르면 이 반으로 옮겨집니다.",
                )
                if st.form_submit_button("저장", type="primary"):
                    try:
                        store.update_class(c["id"], name=new_name, level=new_level, memo=new_memo)
                        for p in profiles:
                            was_in = p.get("class_id") == c["id"]
                            now_in = p["id"] in picked
                            if now_in and not was_in:
                                store.set_profile_class(p["id"], c["id"])
                            elif was_in and not now_in:
                                store.set_profile_class(p["id"], None)
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        flash(f"'{new_name.strip()}' 반을 저장했어요.")
                        st.rerun()
            sure = st.checkbox("이 반을 지울게요 (학생은 지워지지 않고 '반 없음'이 됩니다)",
                               key=f"sure_c_{c['id']}")
            if st.button("반 삭제", key=f"del_c_{c['id']}", disabled=not sure):
                store.delete_class(c["id"])
                flash(f"'{c['name']}' 반을 지웠어요.")
                st.rerun()


# ── 학습 목표 ────────────────────────────────────────────────────

def _targets(profiles: list[dict], classes: list[dict]) -> list[tuple[str, int]]:
    return ([("class", c["id"]) for c in classes]
            + [("profile", p["id"]) for p in profiles])


def target_label(target: tuple, profiles: list[dict], classes: list[dict]) -> str:
    kind, tid = target
    if kind == "class":
        return f"🏫 반: {class_name(tid, classes)}"
    found = next((p["name"] for p in profiles if p["id"] == tid), str(tid))
    return f"🙂 학생: {found}"


def goal_form(key: str, profiles, classes, goal: dict | None = None) -> dict | None:
    """목표 입력 칸. 저장 버튼을 누르면 값(dict), 아니면 None."""
    g = goal or {}
    targets = _targets(profiles, classes)
    if not targets:
        st.info("먼저 반이나 학생을 만들어 주세요.")
        return None
    current = (g.get("target_type"), g.get("target_id"))
    with st.form(key, clear_on_submit=goal is None):
        target = st.selectbox(
            "누구에게", targets, index=targets.index(current) if current in targets else 0,
            format_func=lambda t: target_label(t, profiles, classes),
            help="학생 개인 목표가 반 목표보다 먼저 적용됩니다.",
        )
        left, right = st.columns(2)
        start = left.date_input("시작하는 날",
                                value=date.fromisoformat(g["start_on"]) if g.get("start_on") else date.today())
        end = right.date_input("끝나는 날",
                               value=date.fromisoformat(g["end_on"]) if g.get("end_on") else date.today())
        topic = st.text_input("주제", value=g.get("topic") or "",
                              placeholder="예: 동물원에서 본 동물")
        words = st.text_input("핵심 단어 (쉼표로 구분)", value=", ".join(g.get("words") or []),
                              placeholder="예: lion, tiger, elephant")
        expressions = st.text_area("표현 (한 줄에 하나, 선택)",
                                   value="\n".join(g.get("expressions") or []),
                                   placeholder="예: I like ___.\nIt is big.")
        task = st.text_input("과제 (선택)", value=g.get("task") or "",
                             placeholder="예: 좋아하는 동물 2가지를 영어로 말하기")
        min_words = st.number_input(
            "달성 기준: 아이가 직접 말해야 하는 단어 수 (0 = 전부)",
            min_value=0, max_value=50, value=int(g.get("min_words") or 0), step=1)
        memo = st.text_input("메모 (선택)", value=g.get("memo") or "")
        if st.form_submit_button("저장" if goal else "목표 만들기", type="primary"):
            return {
                "target_type": target[0], "target_id": target[1],
                "start_on": start.isoformat(), "end_on": end.isoformat(),
                "topic": topic,
                "words": [w.strip() for w in words.replace("\n", ",").split(",")],
                "expressions": expressions.splitlines(),
                "task": task, "min_words": min_words or None, "memo": memo,
            }
    return None


def goal_members(goal: dict, profiles: list[dict]) -> list[dict]:
    if goal["target_type"] == "profile":
        return [p for p in profiles if p["id"] == goal["target_id"]]
    return [p for p in profiles if p.get("class_id") == goal["target_id"]]


def goal_result_rows(goal: dict, profiles: list[dict]) -> list[dict]:
    results = store.goal_results_for_goal(goal["id"])
    rows = []
    for p in goal_members(goal, profiles):
        mine = [r for r in results if r["profile_id"] == p["id"]]
        used = sorted({w for r in mine for w in r["words_used"]})
        heard = sorted({w for r in mine for w in r["words_heard"]})
        task = ("✅" if any(r["task_done"] for r in mine) else "아직") if goal.get("task") else "-"
        rows.append({
            "학생": p["name"],
            "달성": "✅ 달성" if any(r["achieved"] for r in mine) else ("진행 중" if mine else "아직 대화 없음"),
            "대화": len(mine),
            f"아이가 말한 단어 (기준 {goals.required_words(goal)}개)":
                f"{len(used)}/{len(goal.get('words') or [])} · " + ", ".join(used),
            "캐릭터가 들려준 단어": ", ".join(heard),
            "과제": task,
        })
    return rows


def goals_page(profiles: list[dict], classes: list[dict]) -> None:
    st.title("학습 목표")
    show_flash()
    st.caption(
        "반이나 학생에게 기간을 정해 오늘의 주제·핵심 단어·표현·과제를 겁니다. "
        "목표가 있으면 캐릭터가 친구처럼 자연스럽게 그 주제로 이끌고, 아이가 단어를 "
        "직접 말하고 과제를 하면 '달성'으로 보고 일상 대화로 돌아갑니다. "
        "아이에게는 수업처럼 보이지 않습니다."
    )
    with st.expander("➕ 새 목표 만들기", expanded=False):
        values = goal_form("new_goal", profiles, classes)
        if values:
            try:
                store.create_goal(**values)
            except ValueError as e:
                st.error(str(e))
            else:
                flash("목표를 만들었어요.")
                st.rerun()

    all_goals = store.list_goals()
    if not all_goals:
        st.info("아직 목표가 없어요.")
        return
    day = date.today().isoformat()
    groups = (
        ("진행 중", [g for g in all_goals if g["start_on"] <= day <= g["end_on"]]),
        ("예정", [g for g in all_goals if g["start_on"] > day]),
        ("지난 목표", [g for g in all_goals if g["end_on"] < day]),
    )
    for title, items in groups:
        if not items:
            continue
        st.subheader(f"{title} ({len(items)})")
        for g in items:
            period = g["start_on"] if g["start_on"] == g["end_on"] else f"{g['start_on']} ~ {g['end_on']}"
            header = (f"{period} · {target_label((g['target_type'], g['target_id']), profiles, classes)}"
                      f" · {g['topic']}")
            with st.expander(header):
                st.markdown(
                    f"**핵심 단어:** {', '.join(g['words']) or '-'}  \n"
                    f"**표현:** {' / '.join(g['expressions']) or '-'}  \n"
                    f"**과제:** {g.get('task') or '-'}  \n"
                    f"**달성 기준:** 단어 {goals.required_words(g)}개"
                    + (" + 과제" if g.get("task") else "")
                )
                rows = goal_result_rows(g, profiles)
                if rows:
                    st.dataframe(rows, hide_index=True, width="stretch")
                else:
                    st.caption("이 목표를 받을 학생이 없어요. 반에 학생을 넣어 주세요.")
                st.markdown("**수정**")
                values = goal_form(f"edit_goal_{g['id']}", profiles, classes, g)
                if values:
                    try:
                        store.update_goal(g["id"], **values)
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        flash("목표를 저장했어요.")
                        st.rerun()
                sure = st.checkbox("이 목표를 지울게요 (결과 기록도 함께 지워짐)",
                                   key=f"sure_g_{g['id']}")
                if st.button("목표 삭제", key=f"del_g_{g['id']}", disabled=not sure):
                    store.delete_goal(g["id"])
                    flash("목표를 지웠어요.")
                    st.rerun()


def student_goals(profile: dict, profiles: list[dict], classes: list[dict]) -> None:
    current = goals.active_goal(profile)
    if current:
        done = goals.already_achieved(profile["id"], current)
        st.markdown(
            f"**지금 걸린 목표:** {current['topic']} "
            f"({target_label((current['target_type'], current['target_id']), profiles, classes)}) — "
            + ("✅ 달성, 이제 일상 대화" if done else "진행 중")
        )
    else:
        st.caption("지금 걸린 목표가 없어요. 일상 대화를 합니다.")
    results = store.goal_results_for_profile(profile["id"])
    if not results:
        return
    by_id = {g["id"]: g for g in store.list_goals()}
    st.dataframe([
        {
            "날짜": short_time(r.get("updated_at")),
            "목표": (by_id.get(r["goal_id"]) or {}).get("topic", "(지운 목표)"),
            "아이가 말한 단어": ", ".join(r["words_used"]),
            "들려준 단어": ", ".join(r["words_heard"]),
            "과제": "-" if r["task_done"] is None else ("✅" if r["task_done"] else "아직"),
            "달성": "✅" if r["achieved"] else "",
        }
        for r in results
    ], hide_index=True, width="stretch")


# ── 실행 ─────────────────────────────────────────────────────────

def main() -> None:
    if not gate():
        return
    try:
        store.init_db()
        profiles = store.list_profiles()
        classes = store.list_classes()
    except Exception as e:
        st.error(f"저장소에 연결하지 못했어요: {type(e).__name__}: {e}")
        return
    selected = sidebar(profiles)
    if selected == "classes":
        classes_page(profiles, classes)
        return
    if selected == "goals":
        goals_page(profiles, classes)
        return
    profile = next((p for p in profiles if p["id"] == selected), None)
    if profile is None:
        overview(profiles, classes)
    else:
        student(profile, classes, profiles)


if __name__ == "__main__":
    main()
