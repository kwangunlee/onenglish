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

### ② OpenAI 키 넣기

1. `.streamlit/secrets.toml.example` 파일을 복사해서 이름을 **`secrets.toml`** 로 바꿉니다.
2. https://platform.openai.com/api-keys 에서 키를 발급받습니다.
3. `OPENAI_API_KEY` 줄에 붙여넣습니다.

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

## 2. 쓰는 법

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

## 3. 바꾸고 싶을 때

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

### 음성 프로바이더 바꾸기 (OpenAI ↔ Google)

성격이 정반대라 취향대로 고르면 됩니다. `secrets.toml` 한 줄입니다.

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

## 4. 나중에 어른용 추가하기

폴더 하나만 더 만들면 됩니다. **코드는 수정하지 않습니다.**

```
data/packs/adults/
├── pack.json          {"id":"adults", "audience":"adults", "levels":["basic"], "enabled":true}
└── characters.json    (kids 것과 같은 형식)
```

그리고 `data/levels.json` 에 `basic` 레벨을 추가하면 끝입니다.
`core/packs.py` 가 `data/packs/` 폴더를 스캔해서 자동으로 인식합니다.

---

## 5. 깃허브 + 인터넷 공개

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
4. **`APP_PASSWORD` 를 반드시 채우세요.** 아이들의 대화 기록이 들어있습니다.

코드는 한 줄도 바꾸지 않아도 됩니다. `st.secrets` 가 양쪽에서 똑같이 동작합니다.

> **주의:** Streamlit Community Cloud 는 앱이 재시작되면 파일이 초기화됩니다.
> `data/onenglish.db` 에 쌓인 대화와 기억이 사라질 수 있습니다. 클라우드에서
> 계속 쓸 거라면 `core/store.py` 를 외부 DB(Supabase, Neon 등)로 바꿔야 합니다.
> **이 파일 하나만 바꾸면 됩니다** — 다른 모듈은 `store.py` 의 함수만 호출하고
> SQL 을 직접 쓰지 않습니다.

---

## 6. 구조

```
onenglish/
├── app.py                  화면 (스트림릿). 여기만 streamlit 을 압니다
├── mcp_server.py           MCP 서버 (선택. 안 써도 됩니다)
├── core/                   로직. streamlit 을 전혀 모릅니다
│   ├── config.py           설정 (환경변수만 읽음)
│   ├── packs.py            캐릭터 팩 로더 (플러그인)
│   ├── store.py            DB — 클라우드 전환 시 여기만 교체
│   ├── llm.py              대화 생성 + 프롬프트 조립
│   ├── stt.py              음성 → 텍스트 (Whisper)
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

## 7. 비용

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

## 8. 잘 안 될 때

| 증상 | 해결 |
|---|---|
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
