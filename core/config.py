"""
설정.

중요: 이 모듈(그리고 core/ 안의 모든 모듈)은 streamlit 을 import 하지 않습니다.
설정값은 전부 환경변수에서만 읽습니다. app.py 가 시작할 때 st.secrets 의 값을
환경변수로 옮겨주고, core/ 는 그걸 읽습니다.

이렇게 분리해두면 나중에 같은 core/ 를 MCP 서버나 다른 프론트엔드(CLI, API)에
그대로 얹을 수 있습니다. core/ 가 streamlit 에 의존하면 그게 불가능해집니다.
"""

import os
from pathlib import Path

# ── 경로 (실행 위치와 무관하게 항상 동일) ─────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PACKS_DIR = DATA_DIR / "packs"
ASSETS_DIR = BASE_DIR / "assets"
LEVELS_PATH = DATA_DIR / "levels.json"
DB_PATH = DATA_DIR / "onenglish.db"


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


# ── 비밀 ─────────────────────────────────────────────────────────
def openai_api_key() -> str:
    """함수로 둔 이유: app.py 가 환경변수를 넣기 전에 import 될 수 있으므로,
    모듈 로드 시점이 아니라 실제 호출 시점에 읽어야 합니다."""
    return _get("OPENAI_API_KEY")


def google_api_key() -> str:
    """Google API 키 (Gemini + Text-to-Speech 공용).

    서비스 계정 JSON 이 아니라 API 키입니다. 같은 키 하나로 대화·음성인식·
    음성합성을 모두 쓸 수 있습니다 (해당 API 들을 사용 설정해 두면).
    예전 이름인 GOOGLE_TTS_KEY 도 계속 인식합니다."""
    for name in ("GOOGLE_API_KEY", "GOOGLE_GEMINI_KEY", "GOOGLE_TTS_KEY"):
        key = _get(name)
        if key and not any(m in key for m in TEMPLATE_MARKERS):
            return key
    return ""


def google_tts_key() -> str:
    """Cloud Text-to-Speech 전용 키.

    Gemini 와 분리해 둡니다. Google 이 Gemini 키를 AQ. 형식으로 옮기는 중인데,
    그 형식은 권한이 Gemini 로 한정되어 Cloud TTS 에서는 거부됩니다. 그래서
    목소리에는 GCP 콘솔에서 만든 AIza 키가 따로 필요할 수 있습니다.

    GOOGLE_TTS_KEY 가 있으면 그것을, 없으면 GOOGLE_API_KEY 를 씁니다."""
    key = _get("GOOGLE_TTS_KEY")
    if key and not any(m in key for m in TEMPLATE_MARKERS):
        return key
    return google_api_key()


def app_password() -> str:
    """앱에 들어올 때 묻는 비밀번호. 비워두면 묻지 않습니다."""
    return _get("APP_PASSWORD")


# ── 데이터베이스 ─────────────────────────────────────────────────
# 기본은 이 폴더 안의 SQLite 파일(data/onenglish.db)입니다.
# CLOUD_SQL_INSTANCE 를 채우면 Google Cloud SQL(PostgreSQL)을 씁니다.
# Streamlit Cloud 처럼 재시작 때 파일이 지워지는 곳에서는 Cloud SQL 이 필요합니다.

def cloud_sql_instance() -> str:
    """Cloud SQL 인스턴스 연결 이름. 예: my-project:asia-northeast3:onenglish-db"""
    return _get("CLOUD_SQL_INSTANCE")


def db_host() -> str:
    """PostgreSQL 에 주소로 직접 붙을 때만. (Cloud SQL Auth Proxy 를 띄웠거나
    다른 PostgreSQL 을 쓸 때) 보통은 비워두고 CLOUD_SQL_INSTANCE 를 씁니다."""
    return _get("DB_HOST")


def db_port() -> int:
    return _get_int("DB_PORT", 5432)


def firestore_project() -> str:
    """Firestore 가 있는 Google Cloud 프로젝트 ID. 비워두면 서비스 계정 키에
    적힌 project_id 를 씁니다."""
    return _get("FIRESTORE_PROJECT")


def firestore_database() -> str:
    """Firestore 데이터베이스 ID. 무료 한도는 기본 DB '(default)' 에만 적용됩니다."""
    return _get("FIRESTORE_DATABASE", "(default)")


DB_BACKENDS = ("sqlite", "firestore", "cloudsql", "postgres")


def db_backend() -> str:
    """'firestore', 'cloudsql', 'postgres'(주소로 직접), 'sqlite' 중 하나.

    DB_BACKEND 로 직접 고를 수 있습니다. 비워두면 채워진 설정을 보고 정합니다."""
    chosen = _get("DB_BACKEND").lower()
    if chosen in DB_BACKENDS:
        return chosen
    if cloud_sql_instance():
        return "cloudsql"
    if db_host():
        return "postgres"
    return "sqlite"


def db_user() -> str:
    return _get("DB_USER", "onenglish")


def db_password() -> str:
    return _get("DB_PASSWORD")


def db_name() -> str:
    return _get("DB_NAME", "onenglish")


def cloud_sql_ip_type() -> str:
    """PUBLIC(기본) 또는 PRIVATE. 같은 VPC 안(Cloud Run 등)에서만 PRIVATE."""
    value = _get("CLOUD_SQL_IP_TYPE", "PUBLIC").upper()
    return value if value in ("PUBLIC", "PRIVATE") else "PUBLIC"


def gcp_service_account_json() -> str:
    """Firestore 나 Cloud SQL 에 접속할 서비스 계정 키(JSON 문자열).

    비워두면 그 컴퓨터의 기본 인증(gcloud auth application-default login)을
    씁니다. Streamlit Cloud 에서는 반드시 채워야 합니다."""
    return _get("GCP_SERVICE_ACCOUNT_JSON")


def parent_password() -> str:
    """기록 보기(대화 로그·기억·학습기록)를 열 때 묻는 비밀번호.

    앱 비밀번호와 다릅니다. 아이는 앱 비밀번호만 알면 되고, 기록은 이 비밀번호를
    아는 사람만 볼 수 있습니다. 비워두면 누구나 기록을 볼 수 있습니다."""
    return _get("PARENT_PASSWORD")


# ── 모델 ─────────────────────────────────────────────────────────
def chat_model() -> str:
    return _get("CHAT_MODEL", "gpt-4o-mini")


def stt_model() -> str:
    return _get("STT_MODEL", "whisper-1")


def tts_model() -> str:
    return _get("TTS_MODEL", "gpt-4o-mini-tts")


# ── 동작 파라미터 ────────────────────────────────────────────────
def max_history_turns() -> int:
    return _get_int("MAX_HISTORY_TURNS", 12)


def max_reply_tokens() -> int:
    return _get_int("MAX_REPLY_TOKENS", 120)


def memory_recall_count() -> int:
    return _get_int("MEMORY_RECALL_COUNT", 6)


# ── 목소리 일관성 ↔ 생기 ─────────────────────────────────────────
# gpt-4o-mini-tts 는 지시문을 매번 다시 해석해서 연기합니다. 그래서 지시문이
# 매 호출마다 달라지면 생기는 살지만 음색이 미세하게 흔들립니다. 반대로 지시문을
# 고정하면 음색은 일정하지만 어떤 얘기를 들어도 같은 톤이 됩니다.
# 정답이 없는 맞바꿈이라 설정으로 뺐습니다.
#
#   stable     : 지시문 고정. 음색이 가장 일정하고, 톤 변화는 없음
#   balanced   : 기분(8종 중 하나)만 반영. 기본값
#   expressive : 기분 + 아이가 방금 한 말까지 반영. 가장 생생하지만 가장 흔들림
VOICE_MODES = ("stable", "balanced", "expressive")


def voice_mode() -> str:
    value = _get("VOICE_MODE", "balanced").lower()
    return value if value in VOICE_MODES else "balanced"


# ── 음성 프로바이더 ──────────────────────────────────────────────
# openai : 연기 지시를 반영 → 생기 있음, 음색이 미세하게 흔들림
# google : 텍스트와 속도만  → 음색이 일정함, 톤 변화 없음
# 캐릭터 정의의 "tts_provider" 로 캐릭터마다 따로 지정할 수도 있습니다.
def ai_provider() -> str:
    """전체 기본 프로바이더. openai 또는 google.

    이 한 줄로 대화·음성인식·음성합성이 모두 바뀝니다. 개별로 다르게 쓰고
    싶으면 아래 세 개를 따로 지정하면 됩니다."""
    return _get("AI_PROVIDER", "openai").lower()


def chat_provider() -> str:
    return _get("CHAT_PROVIDER", ai_provider()).lower()


def stt_provider() -> str:
    return _get("STT_PROVIDER", ai_provider()).lower()


def tts_provider() -> str:
    return _get("TTS_PROVIDER", ai_provider()).lower()


# ── Google 모델 이름 ─────────────────────────────────────────────
# 모델 이름은 바뀔 수 있습니다. 안 되면 tools/check_google.py --models 로
# 지금 쓸 수 있는 목록을 확인하고 여기 값을 바꾸세요.
def gemini_chat_model() -> str:
    return _get("GEMINI_CHAT_MODEL", "gemini-3.8-flash")


def gemini_stt_model() -> str:
    return _get("GEMINI_STT_MODEL", "gemini-3.8-flash")


MISSING_GOOGLE_KEY_MESSAGE = """Google 을 쓰려면 GOOGLE_API_KEY 가 필요합니다.

1. https://aistudio.google.com/apikey 에서 "Create API key" (가장 쉬움)
   또는 https://console.cloud.google.com 에서 API 키 만들기
2. 쓰려는 기능에 따라 아래 API 를 사용 설정하세요.
   · 대화 / 음성인식 : Generative Language API
   · 음성합성       : Cloud Text-to-Speech API
3. .streamlit/secrets.toml 의 GOOGLE_API_KEY 에 넣고 앱을 다시 실행하세요.

서비스 계정 JSON 파일은 필요하지 않습니다. API 키 하나면 됩니다.
확인: python tools/check_google.py
"""


# ── 키 확인 ──────────────────────────────────────────────────────
TEMPLATE_MARKERS = ("여기에", "붙여넣기", "YOUR_", "sk-xxx")


def key_is_configured() -> bool:
    key = openai_api_key()
    if not key:
        return False
    return not any(m in key for m in TEMPLATE_MARKERS)


MISSING_KEY_MESSAGE = """OpenAI API 키가 설정되지 않았습니다.

1. `.streamlit/secrets.toml.example` 파일을 복사해서 `.streamlit/secrets.toml` 로 이름을 바꾸세요.
2. https://platform.openai.com/api-keys 에서 키를 발급받아 `OPENAI_API_KEY` 에 붙여넣으세요.
3. 앱을 다시 실행하세요.
"""
