"""
OnEnglish — 관리자 화면.

실행:
    streamlit run admin.py --server.port 8502
    (윈도우: admin.bat 더블클릭)

아이들이 쓰는 app.py 와 완전히 분리된 화면입니다. 아이들 화면에는 여기로 오는
버튼이 없습니다. 같은 저장소(Firestore 또는 SQLite)를 보기 때문에, 여기서 고친
것은 아이들 화면에 바로 반영됩니다.

할 수 있는 것 (1단계)
  - 학생 전체 현황 (대화 수, 말한 횟수, 기억, 마지막 접속)
  - 학생별 대화 기록 보기 · 대화 삭제
  - 기억 · 학습 기록 보기 · 삭제
  - 학생 추가 · 이름/레벨 수정 · 비밀번호 재설정 · 학생 삭제

비밀번호는 원래 값을 알 수 없게(해시) 저장하므로 "보기"는 안 되고 "재설정"만
됩니다. 관리자도 아이 비밀번호를 볼 수 없는 게 안전한 구조입니다.

들어가는 비밀번호: secrets 의 ADMIN_PASSWORD (없으면 PARENT_PASSWORD).
둘 다 없으면 화면이 열리지 않습니다. 모든 아이의 대화가 보이는 화면이기 때문입니다.
"""

import hmac
import json
import os

import streamlit as st

st.set_page_config(page_title="OnEnglish 관리자", page_icon="🗂️", layout="wide")


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


_bridge_secrets()

from core import config, packs, store  # noqa: E402

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
        labels = ["📋 전체 현황"] + [p["name"] for p in profiles]
        ids = [None] + [p["id"] for p in profiles]
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


def level_select(label: str, current: str, key: str) -> str:
    levels = packs.load_levels()
    ids = list(levels) or [current]
    if current not in ids:
        ids.append(current)
    return st.selectbox(
        label, ids, index=ids.index(current), key=key,
        format_func=lambda i: f"{levels.get(i, {}).get('name', i)} ({i})",
    )


# ── 전체 현황 ────────────────────────────────────────────────────

def overview(profiles: list[dict]) -> None:
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
            "레벨": p.get("level") or "",
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

def student(profile: dict) -> None:
    pid = profile["id"]
    stats = store.profile_stats(pid)
    st.title(profile["name"])
    st.caption(
        f"레벨 {profile.get('level')} · 대화 {stats['sessions']}번 · "
        f"말한 횟수 {stats['child_turns']} · 기억 {stats['memories']} · "
        f"학습 기록 {stats['learning']} · 마지막 접속 {short_time(profile.get('last_seen_at'))}"
    )
    show_flash()

    tabs = st.tabs(["💬 대화 기록", "🧠 기억", "📝 학습 기록",
                    "✏️ 학생 정보", "🔑 비밀번호", "🗑️ 학생 삭제"])
    with tabs[0]:
        conversations(profile)
    with tabs[1]:
        memories(pid)
    with tabs[2]:
        learning(pid)
    with tabs[3]:
        edit_info(profile)
    with tabs[4]:
        reset_password(profile)
    with tabs[5]:
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


def edit_info(profile: dict) -> None:
    with st.form(f"edit_{profile['id']}"):
        name = st.text_input("이름", value=profile["name"])
        level = level_select("레벨", profile.get("level") or packs.default_level_id(),
                             key=f"level_{profile['id']}")
        if st.form_submit_button("저장", type="primary"):
            try:
                store.update_profile(profile["id"], name=name, level=level)
            except ValueError as e:
                st.error(str(e))
            else:
                flash("저장했어요.")
                st.rerun()
    st.caption("이름을 바꾸면 아이들 첫 화면의 이름도 바로 바뀝니다.")


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


# ── 실행 ─────────────────────────────────────────────────────────

def main() -> None:
    if not gate():
        return
    try:
        store.init_db()
        profiles = store.list_profiles()
    except Exception as e:
        st.error(f"저장소에 연결하지 못했어요: {type(e).__name__}: {e}")
        return
    selected = sidebar(profiles)
    profile = next((p for p in profiles if p["id"] == selected), None)
    if profile is None:
        overview(profiles)
    else:
        student(profile)


main()
