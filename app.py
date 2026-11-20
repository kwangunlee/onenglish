"""
OnEnglish — 어린이 일상 영어 대화 친구.

실행:
    streamlit run app.py

화면 흐름: 프로필 선택 → 캐릭터 선택 → 대화 → (부모용) 기록

이 파일은 "화면"만 담당합니다. 실제 로직은 core/ 안에 있고, core/ 는 streamlit 을
전혀 모릅니다. 그래서 나중에 같은 core/ 를 MCP 서버나 다른 프론트엔드에 그대로
얹을 수 있습니다.
"""

import hashlib
import os
import sys

import streamlit as st


# ── 잘못된 실행 방법 막기 ─────────────────────────────────────────
# 스트림릿 앱은 "python app.py" 가 아니라 "streamlit run app.py" 로 띄워야 합니다.
# 그냥 두면 경고가 수십 줄 쏟아지고 브라우저도 안 열려서 뭐가 문제인지 알기
# 어렵기 때문에, 여기서 바로 잡고 안내문을 띄웁니다.
def _running_under_streamlit() -> bool:
    for module_path in (
        "streamlit.runtime.scriptrunner",
        "streamlit.runtime.scriptrunner_utils.script_run_context",
    ):
        try:
            module = __import__(module_path, fromlist=["get_script_run_ctx"])
            return module.get_script_run_ctx() is not None
        except Exception:
            continue
    return True  # 확인할 수 없으면 그냥 진행합니다.


if not _running_under_streamlit():
    print(
        "\n"
        "  ─────────────────────────────────────────────────\n"
        "   실행 방법이 올바르지 않습니다.\n"
        "  ─────────────────────────────────────────────────\n"
        "\n"
        "   ✗  python app.py\n"
        "   ✓  streamlit run app.py\n"
        "\n"
        "   아래 명령으로 다시 실행해 주세요.\n"
        "\n"
        "       streamlit run app.py\n"
        "\n"
        "   (윈도우에서는 run.bat 을 더블클릭해도 됩니다)\n",
        file=sys.stderr,
    )
    sys.exit(1)


st.set_page_config(
    page_title="OnEnglish",
    page_icon="🌙",
    layout="centered",
    initial_sidebar_state="collapsed",
)


# ── secrets → 환경변수 다리 ───────────────────────────────────────
# core/ 는 환경변수만 읽습니다. 여기서 한 번 옮겨줍니다.
# Streamlit Cloud 에 올려도 st.secrets 가 똑같이 동작하므로 코드 변경이 없습니다.
_SECRET_KEYS = (
    "OPENAI_API_KEY", "CHAT_MODEL", "STT_MODEL", "TTS_MODEL",
    "MAX_HISTORY_TURNS", "MAX_REPLY_TOKENS", "MEMORY_RECALL_COUNT",
    "APP_PASSWORD", "PARENT_PASSWORD", "SIGNUP_CODE",
    "VOICE_MODE",
    # 프로바이더 선택: AI_PROVIDER 한 줄이면 대화·음성인식·음성합성이 모두 바뀝니다.
    "AI_PROVIDER", "CHAT_PROVIDER", "STT_PROVIDER", "TTS_PROVIDER",
    # 키
    "GOOGLE_API_KEY", "GOOGLE_TTS_KEY",
    # Google 모델 이름 (바뀔 수 있어 설정으로 뺐습니다)
    "GEMINI_CHAT_MODEL", "GEMINI_STT_MODEL",
)


def _bridge_secrets() -> None:
    """secrets 의 값을 환경변수로 옮깁니다.

    setdefault 가 아니라 덮어씁니다. 예전에는 setdefault 였는데, 그러면
    Streamlit Cloud 에서 Secrets 를 고쳐도 앱이 완전히 재시작되기 전까지
    예전 값이 계속 쓰여서 "키를 바꿨는데 안 바뀐다"는 상황이 생겼습니다.
    secrets 에 적힌 값이 항상 이깁니다."""
    try:
        secrets = st.secrets
    except Exception:
        return
    for key in _SECRET_KEYS:
        try:
            value = secrets[key]
        except Exception:
            continue
        if value is not None and str(value).strip():
            os.environ[key] = str(value).strip()


_bridge_secrets()

from core import config, llm, memory, packs, stt, store, tts  # noqa: E402

store.init_db()


# ── 공용 상태 ────────────────────────────────────────────────────

DEFAULTS = {
    "screen": "profiles",
    "profile": None,
    "character_id": None,
    "session_id": None,
    "messages": [],
    "audio_cache": {},
    "speak_index": None,
    "mic_round": 0,
    "last_audio_hash": None,
    "rate": 0.95,
    "authed": False,
    "parent_authed": False,
    "unlock_profile": None,
    "flash": None,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def go(screen: str) -> None:
    st.session_state.screen = screen
    st.rerun()


def flash(message: str, kind: str = "info") -> None:
    st.session_state.flash = (kind, message)


def show_flash() -> None:
    item = st.session_state.flash
    if not item:
        return
    kind, message = item
    st.session_state.flash = None
    {"info": st.info, "success": st.success,
     "warning": st.warning, "error": st.error}.get(kind, st.info)(message)


CSS = """
<style>
  .block-container { padding-top: 3rem; max-width: 760px; }
  div[data-testid="stChatMessage"] { padding: 0.35rem 0.2rem; }
  /* 한글은 글자 높이가 영문보다 커서 line-height 를 넉넉히 주지 않으면
     위아래가 잘립니다. 모든 커스텀 텍스트에 명시적으로 지정합니다. */
  .oe-title { font-size: 2rem; font-weight: 700; line-height: 1.45;
              margin: 0 0 .2rem 0; padding: .1rem 0; }
  .oe-sub { color: #6b6a66; line-height: 1.6; margin: 0 0 1.4rem 0; }
  .oe-stage-name { font-size: 1.45rem; font-weight: 700; line-height: 1.5;
                   margin: .5rem 0 0 0; }
  .oe-stage-state { color: #6b6a66; font-size: .95rem; line-height: 1.6;
                    margin: .1rem 0 .4rem 0; }
  .oe-card-name { font-size: 1.1rem; font-weight: 700; line-height: 1.5;
                  margin: .4rem 0 0 0; }
  .oe-card-tag { color: #6b6a66; font-size: .85rem; line-height: 1.6;
                 margin: 0 0 .3rem 0; }
  .oe-mem { padding: .45rem .7rem; border-left: 3px solid #AFA9EC;
            background: #F7F6FD; margin-bottom: .4rem; font-size: .93rem; }
  .oe-mem small { color: #6b6a66; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ── 비밀번호 게이트 (APP_PASSWORD 가 설정된 경우에만) ──────────────

def password_gate() -> bool:
    required = config.app_password()
    if not required:
        return True
    if st.session_state.authed:
        return True

    st.markdown('<p class="oe-title">OnEnglish</p>', unsafe_allow_html=True)
    st.markdown('<p class="oe-sub">비밀번호를 입력해 주세요.</p>',
                unsafe_allow_html=True)
    with st.form("gate"):
        value = st.text_input("비밀번호", type="password",
                              label_visibility="collapsed")
        if st.form_submit_button("들어가기", type="primary",
                                 width="stretch"):
            if value == required:
                st.session_state.authed = True
                st.rerun()
            else:
                st.error("비밀번호가 맞지 않아요.")
    return False


# ── 화면 1: 프로필 ───────────────────────────────────────────────

def screen_profiles() -> None:
    st.markdown('<p class="oe-title">누구세요?</p>', unsafe_allow_html=True)
    st.markdown('<p class="oe-sub">이름을 고르면 지난 이야기를 이어서 할 수 있어요.</p>',
                unsafe_allow_html=True)
    show_flash()

    profiles = store.list_profiles()

    if profiles:
        columns = st.columns(2)
        for i, profile in enumerate(profiles):
            with columns[i % 2]:
                # 비밀번호를 넣기 전에는 이름만 보여줍니다.
                # 대화 횟수나 기억 개수도 그 사람의 정보이기 때문입니다.
                locked = store.profile_has_password(profile)
                label = f"**{profile['name']}**"
                label += "  \n:gray[🔒 비밀번호 필요]" if locked else "  \n:gray[바로 입장]"
                if st.button(label, key=f"p{profile['id']}", width="stretch"):
                    if locked:
                        st.session_state.unlock_profile = profile
                        go("unlock")
                    st.session_state.profile = profile
                    go("characters")
    else:
        st.info("아직 등록된 사람이 없어요. 아래에서 이름을 추가해 주세요.")

    st.divider()

    with st.expander("새로운 사람 추가하기", expanded=not profiles):
        required_code = config.signup_code()
        with st.form("new_profile", clear_on_submit=True):
            name = st.text_input("이름", placeholder="예: 민준")
            password = st.text_input(
                "비밀번호", type="password",
                placeholder="숫자 4자리처럼 간단해도 괜찮아요",
                help="다음에 들어올 때 이 비밀번호를 물어봐요. "
                     "잊어버리면 되돌릴 수 없으니 꼭 기억해 주세요.",
            )
            # 공개 주소에서 모르는 사람이 프로필을 만드는 것을 막습니다.
            # SIGNUP_CODE 를 설정하지 않으면 이 칸은 아예 나오지 않습니다.
            code = ""
            if required_code:
                code = st.text_input(
                    "가입 코드", type="password",
                    placeholder="부모님께 받은 코드",
                    help="새 사람을 추가할 때만 필요해요. "
                         "한 번 만들고 나면 다시 묻지 않습니다.",
                )
            if st.form_submit_button("추가하기", type="primary"):
                if required_code and code != required_code:
                    st.error("가입 코드가 맞지 않아요.")
                else:
                    try:
                        created = store.create_profile(
                            name, packs.default_level_id(), password
                        )
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        st.session_state.profile = created
                        flash(f"{created['name']} 님, 반가워요!", "success")
                        go("characters")


def screen_unlock() -> None:
    """프로필 비밀번호 확인. 여기를 통과하기 전에는 그 사람의 대화 기록이
    화면에 전혀 나오지 않습니다."""
    profile = st.session_state.unlock_profile
    if not profile:
        go("profiles")

    st.markdown(f'<p class="oe-title">{profile["name"]}</p>',
                unsafe_allow_html=True)
    st.markdown('<p class="oe-sub">비밀번호를 입력해 주세요.</p>',
                unsafe_allow_html=True)

    with st.form("unlock"):
        value = st.text_input("비밀번호", type="password",
                              label_visibility="collapsed",
                              placeholder="비밀번호")
        if st.form_submit_button("들어가기", type="primary", width="stretch"):
            if store.verify_profile_password(profile["id"], value):
                st.session_state.profile = profile
                st.session_state.unlock_profile = None
                go("characters")
            else:
                st.error("비밀번호가 맞지 않아요.")

    if st.button("← 돌아가기", width="stretch"):
        st.session_state.unlock_profile = None
        go("profiles")


# ── 화면 2: 캐릭터 선택 ──────────────────────────────────────────

def screen_characters() -> None:
    profile = st.session_state.profile
    if not profile:
        go("profiles")

    st.markdown(f'<p class="oe-title">{profile["name"]} 님, 누구랑 얘기할까요?</p>',
                unsafe_allow_html=True)
    show_flash()

    characters = packs.characters_for_level(profile.get("level", "kids"))
    if not characters:
        st.error("사용할 수 있는 캐릭터가 없어요. data/packs/ 폴더를 확인해 주세요.")
        return

    columns = st.columns(2)
    for i, character in enumerate(characters):
        with columns[i % 2]:
            image = packs.image_path(character)
            if image:
                st.image(str(image), width="stretch")
            st.markdown(
                f'<p class="oe-card-name">{character["name"]} '
                f'<span style="color:{character["color"]}">●</span></p>'
                f'<p class="oe-card-tag">{character.get("tagline_ko", "")}</p>',
                unsafe_allow_html=True,
            )
            if st.button("이 친구와 이야기하기", key=f"c{character['id']}",
                         width="stretch", type="primary"):
                start_chat(character["id"])
            st.write("")

    st.divider()
    left, right = st.columns(2)
    if left.button("← 다른 사람으로", width="stretch"):
        st.session_state.profile = None
        go("profiles")
    if right.button("기록 보기", width="stretch"):
        open_records()


def start_chat(character_id: str) -> None:
    profile = st.session_state.profile
    character = packs.get_character(character_id)
    is_returning = store.profile_stats(profile["id"])["sessions"] > 0

    session_id = store.start_session(profile["id"], character_id)
    greeting = llm.greeting_for(character, is_returning)
    store.add_message(session_id, "assistant", greeting)

    st.session_state.character_id = character_id
    st.session_state.session_id = session_id
    st.session_state.messages = [{"role": "assistant", "content": greeting}]
    st.session_state.audio_cache = {}
    st.session_state.speak_index = None
    st.session_state.last_audio_hash = None
    st.session_state.mic_round += 1

    # 첫 인사도 목소리로 들려줍니다. 캐릭터가 말을 걸면서 시작해야
    # 아이가 바로 대화에 들어옵니다.
    with st.spinner(f"{character['name']} 이(가) 오고 있어요..."):
        try:
            audio = tts.synthesize(
                greeting,
                rate=float(st.session_state.rate),
                mood="happy",
                character=character,
            )
            if audio:
                st.session_state.audio_cache[0] = audio
                st.session_state.speak_index = 0
        except llm.LLMError:
            pass  # 목소리가 안 나와도 대화는 시작되어야 합니다.

    go("chat")


# ── 화면 3: 대화 ─────────────────────────────────────────────────

# 채팅 영역 높이(px). 이 영역만 스크롤되고 캐릭터 사진은 위에 고정됩니다.
CHAT_HEIGHT = 330

STATE_TEXT = {
    "idle": "듣고 있어요",
    "listening": "말하는 중...",
    "thinking": "생각하는 중...",
    "talking": "이야기하는 중...",
}


def render_stage(container, character: dict, state: str) -> None:
    """캐릭터 무대. 지금은 이미지지만, characters.json 의 stage.idle /
    stage.talking 에 영상 파일명을 넣으면 자동으로 영상으로 바뀝니다.

    대화가 길어져도 이 영역은 화면 위에 그대로 남습니다. 아래 채팅 영역이
    따로 스크롤되기 때문입니다."""
    with container.container():
        videos = packs.video_paths(character)
        clip = videos.get("talking") if state == "talking" else videos.get("idle")
        if clip is None:
            clip = videos.get("idle") or videos.get("talking")

        left, mid, right = st.columns([2, 3, 2])
        with mid:
            if clip is not None:
                st.video(str(clip), loop=True, autoplay=True, muted=True)
            else:
                image = packs.image_path(character)
                if image:
                    st.image(str(image), width="stretch")
            st.markdown(
                f'<p class="oe-stage-name" style="text-align:center">'
                f'{character["name"]}</p>'
                f'<p class="oe-stage-state" style="text-align:center">'
                f'{STATE_TEXT.get(state, "")}</p>',
                unsafe_allow_html=True,
            )


def chat_scroll_box():
    """채팅만 안쪽에서 스크롤되는 영역.

    예전에는 대화가 쌓일수록 페이지 전체가 늘어나서 캐릭터 사진이 위로 밀려
    사라졌습니다. 높이를 고정한 컨테이너에 넣으면 사진은 제자리에 남습니다.
    autoscroll 은 비교적 최근에 생긴 옵션이라, 없는 버전에서도 돌아가도록
    한 번 걸러서 씁니다."""
    try:
        return st.container(height=CHAT_HEIGHT, border=False, autoscroll=True)
    except TypeError:
        return st.container(height=CHAT_HEIGHT, border=False)


def screen_chat() -> None:
    profile = st.session_state.profile
    character = packs.get_character(st.session_state.character_id)
    if not profile or not character:
        go("profiles")

    with st.sidebar:
        st.markdown(f"**{profile['name']}** · {character['name']}")
        st.session_state.rate = st.slider(
            "말하는 속도", 0.75, 1.4, float(st.session_state.rate), 0.05,
            help="느리게 하면 또박또박 말해요.",
        )
        st.divider()
        if st.button("대화 끝내기", width="stretch", type="primary"):
            finish_session()
            go("characters")
        if st.button("기록 보기", width="stretch"):
            finish_session()
            open_records()

    stage = st.empty()
    render_stage(stage, character, "idle")

    # ── 대화 내용 (이 영역만 스크롤됩니다) ──
    avatar_image = packs.image_path(character)
    avatar = str(avatar_image) if avatar_image else "🙂"
    with chat_scroll_box():
        for index, message in enumerate(st.session_state.messages):
            who = avatar if message["role"] == "assistant" else "🙂"
            with st.chat_message(message["role"], avatar=who):
                st.markdown(message["content"])
                audio = st.session_state.audio_cache.get(index)
                if audio:
                    st.audio(
                        audio,
                        format="audio/mp3",
                        autoplay=(st.session_state.speak_index == index),
                    )
    st.session_state.speak_index = None

    st.caption("마이크 버튼을 누르고 말한 다음, 다시 눌러서 멈추면 돼요.")
    recording = st.audio_input(
        "말하기", key=f"mic_{st.session_state.mic_round}",
        label_visibility="collapsed",
    )

    typed = st.chat_input("아니면 여기에 써도 돼요")

    user_text = None

    if recording is not None:
        audio_bytes = recording.getvalue()
        digest = hashlib.sha1(audio_bytes).hexdigest()
        if audio_bytes and digest != st.session_state.last_audio_hash:
            st.session_state.last_audio_hash = digest
            render_stage(stage, character, "thinking")
            with st.spinner("듣고 있어요..."):
                try:
                    user_text = stt.transcribe(audio_bytes, "speech.wav")
                except llm.LLMError as e:
                    st.error(str(e))
                    user_text = None
            if not user_text:
                st.warning("잘 안 들렸어요. 한 번만 더 말해줄래요?")
                st.session_state.mic_round += 1
                st.rerun()

    if typed and typed.strip():
        user_text = typed.strip()

    if user_text:
        handle_turn(stage, character, profile, user_text)


def handle_turn(stage, character: dict, profile: dict, user_text: str) -> None:
    session_id = st.session_state.session_id

    st.session_state.messages.append({"role": "user", "content": user_text})
    store.add_message(session_id, "user", user_text)

    render_stage(stage, character, "thinking")

    level = packs.get_level(profile.get("level", "kids")) or {}
    memories, learning = memory.recall(profile["id"])

    with st.spinner(f"{character['name']} 이(가) 생각하고 있어요..."):
        try:
            answer = llm.reply(
                character=character,
                level=level,
                history=st.session_state.messages[:-1],
                user_text=user_text,
                memories=memories,
                learning=learning,
                child_name=profile["name"],
            )
        except llm.LLMError as e:
            st.error(str(e))
            return

    st.session_state.messages.append(
        {"role": "assistant", "content": answer.text}
    )
    store.add_message(session_id, "assistant", answer.text)
    index = len(st.session_state.messages) - 1

    render_stage(stage, character, "talking")
    try:
        audio = tts.synthesize(
            answer.text,
            rate=float(st.session_state.rate),
            mood=answer.mood,
            scene=user_text,
            character=character,
        )
        if audio:
            st.session_state.audio_cache[index] = audio
            st.session_state.speak_index = index
    except llm.LLMError:
        # 목소리가 안 나와도 대화는 계속되어야 합니다.
        pass

    st.session_state.mic_round += 1
    st.rerun()


def finish_session() -> None:
    """대화를 닫고 기억을 뽑아 저장합니다."""
    session_id = st.session_state.session_id
    profile = st.session_state.profile
    if not session_id or not profile:
        return

    messages = st.session_state.messages
    child_turns = sum(1 for m in messages if m["role"] == "user")

    if child_turns >= memory.MIN_CHILD_TURNS:
        with st.spinner("오늘 이야기를 기억해 둘게요..."):
            result = memory.extract_and_save(
                profile_id=profile["id"],
                session_id=session_id,
                messages=messages,
                child_name=profile["name"],
            )
        if result["error"]:
            flash("기억을 정리하지 못했어요. 대화는 저장되었어요.", "warning")
        elif result["memories"] or result["learning"]:
            flash(
                f"새로 기억한 것 {result['memories']}개, "
                f"학습 기록 {result['learning']}개를 저장했어요.",
                "success",
            )

    store.end_session(session_id)
    st.session_state.session_id = None
    st.session_state.messages = []
    st.session_state.audio_cache = {}
    st.session_state.character_id = None


# ── 부모 모드 ────────────────────────────────────────────────────
# 앱 비밀번호와 별개입니다. 아이는 앱 비밀번호만 알면 대화할 수 있고,
# 대화 로그·기억·학습기록은 부모 비밀번호를 아는 사람만 볼 수 있습니다.

def open_records() -> None:
    """기록 보기. 부모 비밀번호가 설정되어 있으면 먼저 확인합니다."""
    if not config.parent_password() or st.session_state.parent_authed:
        go("records")
    go("parent")


def screen_parent_gate() -> None:
    st.markdown('<p class="oe-title">부모 확인</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="oe-sub">대화 기록은 보호자만 볼 수 있어요.</p>',
        unsafe_allow_html=True,
    )

    with st.form("parent_gate"):
        value = st.text_input("부모 비밀번호", type="password",
                              label_visibility="collapsed",
                              placeholder="부모 비밀번호")
        ok = st.form_submit_button("확인", type="primary", width="stretch")
        if ok:
            if value == config.parent_password():
                st.session_state.parent_authed = True
                go("records")
            else:
                st.error("비밀번호가 맞지 않아요.")

    if st.button("← 돌아가기", width="stretch"):
        go("characters" if st.session_state.profile else "profiles")


# ── 화면 4: 기록 (부모용) ────────────────────────────────────────

KIND_LABEL = {
    "activity": "활동", "person": "사람", "favorite": "좋아하는 것",
    "event": "사건", "other": "기타",
}


def screen_records() -> None:
    profile = st.session_state.profile
    if not profile:
        go("profiles")

    st.markdown(f'<p class="oe-title">{profile["name"]} 님의 기록</p>',
                unsafe_allow_html=True)
    show_flash()

    stats = store.profile_stats(profile["id"])
    a, b, c, d = st.columns(4)
    a.metric("대화", f"{stats['sessions']}번")
    b.metric("말한 횟수", f"{stats['child_turns']}번")
    c.metric("기억", f"{stats['memories']}개")
    d.metric("학습 기록", f"{stats['learning']}개")

    tab_memory, tab_learning, tab_history = st.tabs(
        ["기억하고 있는 것", "자주 틀리는 표현", "지난 대화"]
    )

    with tab_memory:
        memories = store.all_memories(profile["id"])
        if not memories:
            st.caption("아직 기억이 없어요. 대화를 나누면 쌓여요.")
        for m in memories:
            people = ", ".join(m["people"]) if m["people"] else ""
            meta = " · ".join(
                x for x in (m.get("occurred_on"),
                            KIND_LABEL.get(m["kind"], m["kind"]),
                            people) if x
            )
            row, button = st.columns([6, 1])
            row.markdown(
                f'<div class="oe-mem">{m["summary_ko"]}<br>'
                f'<small>{m["summary_en"]}</small><br>'
                f'<small>{meta}</small></div>',
                unsafe_allow_html=True,
            )
            if button.button("삭제", key=f"dm{m['id']}"):
                store.delete_memory(m["id"])
                st.rerun()

    with tab_learning:
        mistakes = store.frequent_mistakes(profile["id"])
        if mistakes:
            st.markdown("**반복되는 표현**")
            st.dataframe(
                [
                    {
                        "올바른 표현": m["better_form"],
                        "설명": m["note_ko"] or "",
                        "횟수": m["times"],
                    }
                    for m in mistakes
                ],
                hide_index=True,
                width="stretch",
            )
        entries = store.recent_learning(profile["id"], 50)
        if not entries:
            st.caption("아직 학습 기록이 없어요.")
        else:
            st.markdown("**전체 기록**")
            st.dataframe(
                [
                    {
                        "종류": "실수" if e["kind"] == "mistake" else "새 표현",
                        "말한 것": e["child_said"] or "",
                        "올바른 표현": e["better_form"] or "",
                        "설명": e["note_ko"] or "",
                        "날짜": (e["created_at"] or "")[:10],
                    }
                    for e in entries
                ],
                hide_index=True,
                width="stretch",
            )

    with tab_history:
        sessions = store.list_sessions(profile["id"])
        if not sessions:
            st.caption("아직 대화가 없어요.")
        for s in sessions:
            character = packs.get_character(s["character_id"])
            name = character["name"] if character else s["character_id"]
            when = (s["started_at"] or "")[:16].replace("T", " ")
            with st.expander(f"{when} · {name} · {s['message_count']}개"):
                for m in store.get_messages(s["id"]):
                    who = profile["name"] if m["role"] == "user" else name
                    st.markdown(f"**{who}** — {m['content']}")

    st.divider()
    left, mid, right = st.columns(3)
    if left.button("← 캐릭터 고르기", width="stretch"):
        go("characters")
    if mid.button("다른 사람으로", width="stretch"):
        st.session_state.profile = None
        go("profiles")
    if config.parent_password():
        if right.button("🔒 부모 모드 끄기", width="stretch"):
            st.session_state.parent_authed = False
            flash("부모 모드를 껐어요.", "info")
            go("characters" if st.session_state.profile else "profiles")


# ── 라우팅 ───────────────────────────────────────────────────────

def main() -> None:
    if not password_gate():
        return

    if not config.key_is_configured():
        st.markdown('<p class="oe-title">설정이 필요해요</p>',
                    unsafe_allow_html=True)
        st.warning(config.MISSING_KEY_MESSAGE)
        st.stop()

    screens = {
        "profiles": screen_profiles,
        "characters": screen_characters,
        "chat": screen_chat,
        "records": screen_records,
        "parent": screen_parent_gate,
        "unlock": screen_unlock,
    }
    screens.get(st.session_state.screen, screen_profiles)()


main()
