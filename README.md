# OnEnglish

어린이의 **일상 영어 대화 친구**. 수업이 아니라 친구입니다.

아이가 말을 걸면 캐릭터가 영어로 답하고, 대화가 끝나면 그날의 이야기를 기억해
둡니다. 다음에 만났을 때 캐릭터가 먼저 그 얘기를 꺼냅니다.

---

## 1. 처음 한 번만 하면 되는 설정

### ① 파이썬 패키지 설치

```bash
pip install -r requirements.txt
```

### ② 키 넣기

`.streamlit/secrets.toml.example` 을 복사해서 이름을 **`secrets.toml`** 로 바꾸고
아래 둘 중 하나를 채웁니다.

**Google (권장 — 카드 없이 무료 한도)**

```toml
AI_PROVIDER = "google"
GOOGLE_API_KEY = "AIza..."
```

키 발급: https://aistudio.google.com/apikey → Create API key
음성합성까지 쓰려면 같은 프로젝트에서
[Cloud Text-to-Speech API](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
도 사용 설정하세요. **서비스 계정 JSON 파일은 필요 없습니다.**

확인: `python tools/check_google.py`

**OpenAI (선불 충전 필요)**

```toml
AI_PROVIDER = "openai"
OPENAI_API_KEY = "sk-..."
```

키 발급: https://platform.openai.com/api-keys
크레딧이 0 이면 키가 있어도 동작하지 않습니다.

> `secrets.toml` 은 `.gitignore` 에 등록되어 있어 **깃허브에 올라가지 않습니다.**
> 예전 버전에서 `config.json` 에 키가 그대로 노출되어 있던 문제를 막기 위한 장치입니다.

### ③ 실행

**윈도우라면 `run.bat` 을 더블클릭**하면 됩니다. 패키지 설치와 설정 확인까지
알아서 해줍니다.

직접 명령으로 실행할 때는:

```bash
streamlit run app.py
```

> **`python app.py` 가 아닙니다.** 스트림릿 앱은 반드시 `streamlit run` 으로
> 띄워야 합니다. 잘못 실행하면 안내 문구가 뜨니 그대로 따라 하면 됩니다.

브라우저가 열리고 `http://localhost:8501` 로 접속됩니다.

> **음성 입력은 Chrome 또는 Edge 에서 가장 잘 동작합니다.**
> 마이크 권한을 물어보면 허용해 주세요.

---

## 2. 비밀번호 구조

| | 누가 | 어디서 정하나 |
|---|---|---|
| **사람별 비밀번호** | 각자 본인 | 앱에서 이름을 만들 때 각자 입력 (기본 동작) |
| 앱 비밀번호 `APP_PASSWORD` | 들어오는 모든 사람 | `secrets.toml` (보통 불필요) |
| 부모 비밀번호 `PARENT_PASSWORD` | 기록을 볼 사람 | `secrets.toml` |

기본 동작은 **사람별 비밀번호 하나뿐**입니다. 첫 화면에는 이름 목록만 보이고,
이름을 고르면 그 사람의 비밀번호를 묻습니다. 비밀번호를 넣기 전에는 그 사람의
대화 내용은 물론 대화 횟수와 기억 개수도 보이지 않습니다.

비밀번호는 pbkdf2 해시로 저장되어 원래 값을 알 수 없습니다. 그래서 잊어버리면
복구가 아니라 재설정만 가능합니다.

## 3. 쓰는 법

```
이름 고르기  →  캐릭터 고르기  →  대화  →  (왼쪽 메뉴) 대화 끝내기
```

- **마이크 버튼**을 누르고 말한 다음, 다시 눌러서 멈추면 인식됩니다.
- 말하기가 어려우면 아래 입력칸에 **타이핑**해도 됩니다.
- 왼쪽 메뉴(`>` 버튼)에서 **말하는 속도**를 조절할 수 있습니다.
- **대화 끝내기**를 눌러야 그날의 기억이 저장됩니다. 그냥 창을 닫으면 저장되지 않습니다.

### 기록 보기 (부모용)

- **기억하고 있는 것** — 캐릭터가 기억 중인 아이의 일상. 필요 없는 건 삭제할 수 있습니다.
- **자주 틀리는 표현** — 반복되는 실수와 올바른 표현.
- **지난 대화** — 전체 대화 내용.

> 캐릭터는 아이의 실수를 **절대 지적하지 않습니다.** 대신 올바른 표현을 자기 말에
> 자연스럽게 섞어서 들려줍니다. 지적은 부모용 화면에만 기록됩니다.

---

## 4. 바꾸고 싶을 때

거의 모든 것이 **코드 수정 없이** 파일만 고쳐서 됩니다.

| 바꾸고 싶은 것 | 고칠 파일 |
|---|---|
| 캐릭터 성격·말투·목소리·인사말 | `data/packs/kids/characters.json` |
| 캐릭터 그림 | `assets/luna.png` 등을 같은 이름으로 덮어쓰기 |
| 대화 규칙 (문장 길이, 교정 방식 등) | `data/levels.json` 의 `rules` |
| 모델, 기억 개수, 답변 길이 | `.streamlit/secrets.toml` |
| 화면 색상 | `.streamlit/config.toml` |

고친 뒤에는 브라우저에서 **`R` 키**를 누르거나 앱을 다시 실행하면 반영됩니다.

### 목소리가 밋밋할 때

목소리는 세 가지가 함께 결정합니다.

1. **`voice`** — 어떤 성대를 쓸지. 표현력 차이가 꽤 큽니다.
   대체로 `fable` > `verse` > `ballad` > `coral` > `nova` > `sage` > `shimmer`
   > `alloy` > `ash` > `echo` > `onyx` 순입니다.
   **`echo`, `ash`, `onyx` 는 평탄한 편이라 활발한 캐릭터에 쓰지 마세요.**
2. **`voice_instruction`** — 어떻게 연기할지. **길고 구체적일수록 잘 합니다.**
   성격·톤·감정·속도·쉼을 나눠서 쓰세요. 한 줄로 쓰면 거의 안 먹힙니다.
3. **그 순간의 감정** — 코드가 자동으로 넣습니다. 대화할 때마다 캐릭터가
   지금 어떤 기분인지(신남·다정함·장난기 등) 함께 판단해서 음성 연출에
   반영하므로, 같은 캐릭터라도 상황에 따라 톤이 달라집니다.

직접 들어보고 고르려면:

```bash
python tools/voice_test.py                     # 캐릭터 4종 × 감정 3가지
python tools/voice_test.py --character rocky --voices verse,fable,ballad,nova
python tools/voice_test.py --list              # 목소리 목록
```

`voice_samples/` 폴더에 mp3 가 생깁니다. 들어보고 마음에 드는 것으로
`characters.json` 의 `voice` 값을 바꾸면 됩니다.

### Google ↔ OpenAI 통째로 바꾸기

`secrets.toml` 한 줄이면 **대화·음성인식·음성합성이 모두** 바뀝니다.

```toml
AI_PROVIDER = "google"   # 또는 "openai"
```

| | `google` | `openai` |
|---|---|---|
| 대화 | Gemini | GPT-4o mini |
| 음성인식 | Gemini (오디오 직접 처리) | Whisper |
| 음성합성 | Cloud TTS (Chirp3-HD 등) | gpt-4o-mini-tts |
| 필요한 키 | `GOOGLE_API_KEY` 하나 | `OPENAI_API_KEY` 하나 |
| 비용 | 카드 없이 무료 한도 있음 | 선불 충전 필요 |

기능별로 섞어 쓸 수도 있습니다. 비워두면 `AI_PROVIDER` 를 따릅니다.

```toml
CHAT_PROVIDER = "google"
TTS_PROVIDER  = "openai"
```

> Google 모델 이름은 바뀔 수 있습니다. "모델을 찾을 수 없어요" 가 나오면
> `python tools/check_google.py --models` 로 목록을 보고
> `GEMINI_CHAT_MODEL` 을 바꾸세요.

### 음성만 따로 바꾸기

음성합성은 두 쪽 성격이 정반대라, 대화와 별개로 고를 수 있습니다.

| | `openai` | `google` |
|---|---|---|
| 모델이 받는 것 | 텍스트 + **연기 지시문** | 텍스트 + 속도 숫자 |
| 상황별 톤 변화 | **있음** (신남·위로 등) | 없음 |
| 음색 일관성 | 미세하게 흔들림 | **절대 안 흔들림** |
| 쓰는 목소리 | `voice` | `voice_google` |
| 필요한 키 | `OPENAI_API_KEY` | `GOOGLE_TTS_KEY` |

```toml
TTS_PROVIDER = "google"
GOOGLE_TTS_KEY = "AIza..."
```

> Google 은 **API 키만** 씁니다. 서비스 계정 JSON 파일은 필요 없습니다.
> 예전 버전에 들어있던 그 자격증명 파일은 데이터베이스 전체 권한을 가지고
> 있어서 위험했습니다. TTS 에는 제한된 API 키 하나면 충분합니다.
> 키를 만들 때 **"API 제한"에서 Text-to-Speech 만 허용**하도록 꼭 제한하세요.

**캐릭터마다 다르게 쓸 수도 있습니다.** `characters.json` 에서:

```json
"tts_provider": "google"
```

차분한 캐릭터는 Google, 활발한 캐릭터는 OpenAI — 이렇게 섞어도 됩니다.

들어보고 고르려면:

```bash
python tools/voice_test.py --provider google
python tools/voice_test.py --google-voices     # 쓸 수 있는 목소리 목록
```

**프로바이더를 새로 추가하려면** `core/tts_providers/` 에 파일 하나 만들고
`__init__.py` 의 레지스트리에 한 줄 추가하면 됩니다. `core/tts.py` 와 `app.py`
는 수정하지 않습니다.

### 목소리가 문장마다 미세하게 달라질 때 (OpenAI 전용)

`gpt-4o-mini-tts` 는 지시문을 **매번 다시 해석해서 연기하는** 모델입니다.
그래서 상황에 따라 연출을 바꾸면 생기는 살지만 음색이 조금씩 흔들립니다.
정답이 없는 맞바꿈이라 `secrets.toml` 의 `VOICE_MODE` 로 고르게 해두었습니다.

| 값 | 지시문에 넣는 것 | 결과 |
|---|---|---|
| `stable` | 캐릭터 연출만 (매번 **완전히 동일**) | 음색이 가장 일정. 톤 변화 없음 |
| `balanced` | + 그 순간의 기분 (8종 중 하나) | 기본값. 감정은 살고 흔들림은 적음 |
| `expressive` | + 아이가 방금 한 말 | 가장 생생. 가장 많이 흔들림 |

모드별로 직접 비교해 들어보려면:

```bash
python tools/voice_test.py --drift
```

같은 캐릭터가 연속으로 말하는 대사 4개를 세 모드 각각으로 만들어 줍니다.
한 모드 안에서 1→2→3→4 를 이어서 들어보고, 같은 사람 목소리로 들리는지
확인하세요.

> **음색이 완벽하게 일정해야 한다면** `TTS_MODEL` 을 `tts-1-hd` 로 바꾸세요.
> 이 모델은 연기 지시를 아예 받지 않고 읽기만 해서 음색이 흔들릴 수가
> 없습니다. 대신 `voice_instruction` 이 통째로 무시되어 많이 밋밋해집니다.
> (예전 tkinter 버전이 Google `Chirp3-HD` 로 이 상태였습니다. 음색은
> 일정했지만 생기가 없던 이유입니다.)

### 캐릭터 그림을 Flow 로 만든 것으로 바꾸기

1. `data/packs/kids/characters.json` 에서 캐릭터의 `flow_prompt` 를 복사합니다.
2. Flow 에서 그 프롬프트로 이미지를 만듭니다.
3. **마음에 드는 1장을 먼저 확정하세요.** 추가 이미지나 영상은 반드시 그 1장에서
   파생시켜야 캐릭터가 똑같이 유지됩니다. 텍스트만으로 여러 장 만들면 매번 다른
   얼굴이 나옵니다.
4. `assets/luna.png` 처럼 **기존과 같은 파일명으로 덮어쓰기** 합니다.

임시 그림을 다시 만들고 싶으면:

```bash
python tools/make_placeholder_avatars.py
```

### 나중에 캐릭터 영상 넣기

`characters.json` 의 `stage` 에 영상 파일명을 채우면 **자동으로 영상 모드가 됩니다.**
앱 코드는 수정하지 않습니다.

```json
"stage": {
  "image": "luna.png",
  "idle": "luna_idle.mp4",
  "talking": "luna_talking.mp4"
}
```

영상을 만들 때 주의할 점:

- **2~3초로 짧게.** 길면 반복 시 이음새가 더 눈에 띕니다.
- **첫 프레임과 끝 프레임을 비슷하게.** 그래야 반복 재생이 자연스럽습니다.
- 입모양은 말하는 내용과 맞지 않습니다(립싱크 불가). "말하는 느낌"만 주면 됩니다.
- 영상을 안 넣은 캐릭터는 그냥 이미지로 나옵니다. **섞여 있어도 괜찮습니다.**

---

## 5. 나중에 어른용 추가하기

폴더 하나만 더 만들면 됩니다. **코드는 수정하지 않습니다.**

```
data/packs/adults/
├── pack.json          {"id":"adults", "audience":"adults", "levels":["basic"], "enabled":true}
└── characters.json    (kids 것과 같은 형식)
```

그리고 `data/levels.json` 에 `basic` 레벨을 추가하면 끝입니다.
`core/packs.py` 가 `data/packs/` 폴더를 스캔해서 자동으로 인식합니다.

---

## 6. 깃허브 + 인터넷 공개

### 깃허브에 올리기

```bash
git init
git add .
git commit -m "OnEnglish 첫 커밋"
git remote add origin https://github.com/<아이디>/onenglish.git
git push -u origin main
```

`secrets.toml` 과 `data/*.db` 는 `.gitignore` 에 있어 **올라가지 않습니다.**
올라가면 안 되는 것들이니 꼭 확인하세요.

### Streamlit Community Cloud 에 올리기

1. https://share.streamlit.io 에서 깃허브 저장소를 연결합니다.
2. 메인 파일로 `app.py` 를 지정합니다.
3. **Settings → Secrets** 칸에 `secrets.toml` 의 내용을 그대로 붙여넣습니다.
4. 공개 주소라 모르는 사람이 들어올 수 있다면 **`APP_PASSWORD` 를 채우세요.**
   새 프로필을 만들어 API 비용을 쓰는 것을 막습니다.

코드는 한 줄도 바꾸지 않아도 됩니다. `st.secrets` 가 양쪽에서 똑같이 동작합니다.

> **주의:** Streamlit Community Cloud 는 앱이 재시작되면 파일이 초기화됩니다.
> `data/onenglish.db` 에 쌓인 대화와 기억이 사라질 수 있습니다. 클라우드에서
> 계속 쓸 거라면 아래 **Firestore 연결(무료)** 을 따라 하세요.

### Firestore 연결 (무료)

Google 의 Firestore 는 **매일 읽기 5만 번 · 쓰기 2만 번 · 저장 1GB 까지 무료**입니다.
가족 몇 명이 매일 대화해도 한도의 몇 % 수준이라 비용이 0 원입니다.
설정만 채우면 되고, 코드는 `DB_BACKEND = "firestore"` 일 때 Firestore 를 씁니다.

**① Firestore 만들기** — https://console.cloud.google.com
1. 위쪽에서 프로젝트(예: `onenglish-chat`)를 고릅니다.
2. 검색창에 **Firestore** → **데이터베이스 만들기**
3. 데이터베이스 ID 는 **`(default)` 그대로** 둡니다. (무료 한도는 기본 DB 에만 적용)
4. 모드는 **네이티브 모드(Native)**, 에디션을 묻는다면 **Standard**
5. 위치: 앱이 도는 곳과 가깝게. **Streamlit Cloud 면 `nam5`(미국)**, 집 컴퓨터면
   `asia-northeast3`(서울). **위치는 나중에 바꿀 수 없습니다.**
6. 보안 규칙은 **프로덕션 모드**(외부 접근 차단). 앱은 서비스 계정으로 들어가서
   규칙과 상관없이 동작합니다.

**② 서비스 계정 (앱이 접속할 때 쓰는 열쇠)**
1. **IAM 및 관리자 → 서비스 계정 → 서비스 계정 만들기**: 이름 `onenglish-db`
2. 역할: **Cloud Datastore 사용자** 하나만 (Firestore 읽기·쓰기 권한)
3. 만든 계정 → **키 → 키 추가 → 새 키 만들기 → JSON** 으로 키 파일을 받습니다.
   이 파일은 **절대 깃허브에 올리지 마세요.** 이 폴더 밖에 두는 게 안전합니다.

**③ secrets.toml 채우기**
```toml
DB_BACKEND = "firestore"

# 파일 맨 끝에: 키 파일(JSON)의 각 항목을 옮겨 적기
[gcp_service_account]
type = "service_account"
project_id = "onenglish-chat"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "onenglish-db@onenglish-chat.iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
# (나머지 항목도 키 파일에 있는 그대로)
```
Streamlit Cloud 라면 같은 내용을 **Settings → Secrets** 에 붙여넣습니다.

**④ 패키지 설치**
```bash
pip install -r requirements.txt
```

**⑤ (선택) 지금까지의 기록 옮기기** — 새 사람을 만들기 **전에**
```bash
python tools/migrate_to_firestore.py
```
`data/onenglish.db` 의 프로필·대화·기억·학습기록을 그대로 옮깁니다. 원본은
건드리지 않고, Firestore 에 이미 프로필이 있으면 섞이지 않게 멈춥니다.

**⑥ 실행** — `streamlit run app.py` (또는 `run.bat`). 연결이 안 되면 첫 화면에
이유가 뜹니다. 콘솔에서 색인(index)을 따로 만들 필요는 없습니다.

### (유료) Google Cloud SQL 연결

Firestore 대신 PostgreSQL 이 꼭 필요할 때만. `CLOUD_SQL_INSTANCE` 가 있으면
Cloud SQL 을 씁니다. `requirements.txt` 아래쪽 Cloud SQL 두 줄의 `#` 을 지우고
설치해야 합니다.

> **비용:** Cloud SQL 은 무료 등급이 없습니다. 가장 작은 인스턴스도 켜져 있는 동안
> 한 달에 대략 1~2만 원 정도 나옵니다. 시작 전에 콘솔의 가격 계산기로 확인하세요.

**① 프로젝트 준비** — https://console.cloud.google.com
1. 프로젝트를 고르거나 새로 만들고, **결제 계정**을 연결합니다.
2. **API 및 서비스 → 라이브러리**에서 **Cloud SQL Admin API** 를 사용 설정합니다.

**② 인스턴스 만들기** — **SQL → 인스턴스 만들기 → PostgreSQL**
- 버전: **Enterprise**, 프리셋: **샌드박스/개발**, 머신: 가장 작은 공유 코어
- 리전: 앱이 도는 곳과 가깝게. **Streamlit Cloud 면 `us-central1`**,
  집 컴퓨터에서만 쓰면 `asia-northeast3`(서울). 멀면 화면이 눈에 띄게 느려집니다.
- `postgres` 비밀번호를 정해 두고, 만들어질 때까지 몇 분 기다립니다.

**③ DB 와 사용자** — 만든 인스턴스 안에서
1. **데이터베이스 → 만들기**: 이름 `onenglish`
2. **사용자 → 사용자 계정 추가**: 이름 `onenglish`, 비밀번호 정하기 (기본 제공 인증)
3. **개요** 화면의 **연결 이름**(`프로젝트:리전:인스턴스`)을 복사해 둡니다.

**④ 서비스 계정 (앱이 접속할 때 쓰는 열쇠)**
1. **IAM 및 관리자 → 서비스 계정 → 만들기**: 이름 `onenglish-db`
2. 역할: **Cloud SQL 클라이언트** 하나만
3. 만든 계정 → **키 → 키 추가 → JSON** 으로 키 파일을 받습니다.
   이 파일은 **절대 깃허브에 올리지 마세요.** 이 폴더 밖에 두는 게 안전합니다.

**⑤ secrets.toml 채우기** — `secrets.toml.example` 의 "데이터베이스" 부분 참고
```toml
CLOUD_SQL_INSTANCE = "my-project:us-central1:onenglish-db"
DB_USER = "onenglish"
DB_PASSWORD = "③에서 정한 비밀번호"
DB_NAME = "onenglish"

# 파일 맨 끝에: 키 파일(JSON)의 각 항목을 옮겨 적기
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "onenglish-db@....iam.gserviceaccount.com"
token_uri = "https://oauth2.googleapis.com/token"
# (나머지 항목도 키 파일에 있는 그대로)
```
Streamlit Cloud 라면 같은 내용을 **Settings → Secrets** 에 붙여넣습니다.

**⑥ 패키지 설치 후 실행**
```bash
pip install -r requirements.txt
streamlit run app.py
```
처음 연결될 때 테이블이 자동으로 만들어집니다. 연결이 안 되면 화면에 이유가 뜹니다.

**⑦ (선택) 지금까지의 기록 옮기기**
```bash
python tools/migrate_to_cloudsql.py
```
`data/onenglish.db` 의 프로필·대화·기억·학습기록을 그대로 옮깁니다. 원본은
건드리지 않고, Cloud SQL 에 이미 프로필이 있으면 섞이지 않게 멈춥니다.
그래서 **Cloud SQL 로 연결한 앱에서 새 사람을 만들기 전에** 해야 합니다.

---

## 7. 구조

```
onenglish/
├── app.py                  화면 (스트림릿). 여기만 streamlit 을 압니다
├── mcp_server.py           MCP 서버 (선택. 안 써도 됩니다)
├── core/                   로직. streamlit 을 전혀 모릅니다
│   ├── config.py           설정 (환경변수만 읽음)
│   ├── packs.py            캐릭터 팩 로더 (플러그인)
│   ├── store.py            DB (SQLite · Cloud SQL) — 다른 모듈은 여기 함수만 부름
│   ├── store_firestore.py  DB (Firestore 판). DB_BACKEND="firestore" 면 store.py 가 이쪽으로 넘김
│   ├── llm.py              대화 생성 + 프롬프트 조립
│   ├── clients.py          OpenAI / Google 호출 공통 바닥
│   ├── stt.py              음성 → 텍스트 (Whisper / Gemini)
│   ├── llm_providers/      대화 프로바이더 — 파일 추가로 확장
│   │   ├── base.py         공통 규격
│   │   ├── openai_chat.py  GPT
│   │   └── gemini_chat.py  Gemini
│   ├── tts.py              텍스트 → 음성 (프로바이더 고르기만)
│   ├── tts_providers/      음성 프로바이더 — 파일 추가로 확장
│   │   ├── base.py         공통 규격
│   │   ├── openai_tts.py   OpenAI (연기 지시 반영)
│   │   └── google_tts.py   Google (음색 일정)
│   └── memory.py           기억 추출 / 주입
├── data/
│   ├── levels.json         레벨별 대화 규칙
│   ├── packs/kids/         어린이 캐릭터 팩
│   └── onenglish.db        대화·기억 (깃에 안 올라감)
├── assets/                 캐릭터 그림
├── tools/
    ├── make_placeholder_avatars.py   임시 그림 생성
    ├── check_google.py               Google 연결 확인 / 모델 목록
    ├── voice_test.py                 목소리 들어보기 / 비교
    └── smoke_test.py                 화면 점검 (API 호출 없음)
```

`core/` 가 `streamlit` 을 import 하지 않는 것이 이 구조의 핵심입니다.
그래서 같은 로직을 MCP 서버(`mcp_server.py`)나 다른 화면에 그대로 얹을 수 있습니다.

점검:

```bash
python tools/smoke_test.py
```

---

## 8. 비용

실제로 쓰는 것은 OpenAI 세 가지입니다.

| 기능 | 모델 | 언제 |
|---|---|---|
| 음성 인식 | `whisper-1` | 아이가 말할 때마다 |
| 대화 | `gpt-4o-mini` | 아이가 말할 때마다 |
| 음성 합성 | `gpt-4o-mini-tts` 또는 Google | 캐릭터가 답할 때마다 |
| 기억 추출 | `gpt-4o-mini` | 대화를 끝낼 때 **1회만** |

단가는 수시로 바뀌므로 여기에 적지 않았습니다. OpenAI 대시보드의 Usage 화면에서
며칠 써보고 실제 금액을 확인하는 걸 권합니다. 답변 길이를 줄이려면
`secrets.toml` 의 `MAX_REPLY_TOKENS` 를, 기억 주입량을 줄이려면
`MEMORY_RECALL_COUNT` 를 낮추면 됩니다.

---

## 9. 잘 안 될 때

| 증상 | 해결 |
|---|---|
| `Incorrect API key` | 키가 폐기됐거나 틀림. 새로 발급 후 **앱 재시작**(Save만으론 부족할 수 있음) |
| `모델을 찾을 수 없어요` | `python tools/check_google.py --models` 로 목록 확인 후 `GEMINI_CHAT_MODEL` 변경 |
| Google 키가 거부됨 | Generative Language API / Cloud Text-to-Speech API 사용 설정 확인 |
| 마이크 버튼이 안 보임 | Chrome / Edge 로 접속. 마이크 권한 허용 |
| "설정이 필요해요" 화면 | `.streamlit/secrets.toml` 에 키가 없거나 예시 문구 그대로임 |
| 목소리가 안 나옴 | 대화는 계속됩니다. 키 사용량 한도 또는 `TTS_MODEL` 값을 확인 |
| 캐릭터가 안 보임 | `data/packs/kids/` 에 `pack.json` 과 `characters.json` 이 있는지 확인 |
| 기억이 안 쌓임 | **대화 끝내기**를 눌렀는지 확인. 아이가 2번 이상 말해야 저장됩니다 |
| 그림이 안 나옴 | `python tools/make_placeholder_avatars.py` 실행 |

---

## 이전 버전에서 고친 것

2년 전 tkinter 버전에서 넘어오며 고친 주요 문제들입니다.

- **AI 응답을 `system` 역할로 저장**하던 버그 → `assistant` 로 수정. DB 에 CHECK 제약을 걸어 재발을 막았습니다. 대화가 길어질수록 캐릭터가 무너지던 원인이었습니다.
- **말풍선이 이중으로 출력**되고 줄바꿈이 없던 문제 → `st.chat_message` 로 대체
- **배경 이미지가 채팅 글씨를 덮던** 문제 → 레이아웃 분리로 구조적으로 해소
- **exe 에서 채팅 화면이 안 열리던** 문제 (`subprocess` 로 `python` 실행) → 단일 앱으로 통합
- **TTS 재생 중 화면이 멈추던** 문제 → 브라우저가 재생
- **백그라운드 스레드에서 UI 를 조작**하던 문제 → 스레드 자체를 없앰
- **음성인식 5분 제한** → Whisper 로 교체하며 제거
- **`instruction` 오타**로 목소리 연출이 무시되던 문제 → `instructions` 로 수정
- **API 키와 비밀번호가 평문 노출** → `secrets.toml` + `.gitignore`
- **Firebase Admin SDK 키가 클라이언트에 포함**되던 문제 → Firebase 자체를 제거
- **아이 음성이 공개 URL 로 업로드**되던 코드 → 제거
- **저작권 캐릭터 사용** → 자체 캐릭터로 교체
- 의존성 9개(`pyaudio` 포함) → **2개**
