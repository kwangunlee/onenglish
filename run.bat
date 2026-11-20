@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo   OnEnglish 를 시작합니다...
echo.

where streamlit >nul 2>nul
if errorlevel 1 (
    echo   [안내] 필요한 패키지를 먼저 설치할게요. 잠시 걸립니다.
    echo.
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo   [오류] 설치에 실패했습니다.
        echo          파이썬이 설치되어 있는지 확인해 주세요.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist ".streamlit\secrets.toml" (
    echo   ─────────────────────────────────────────────────
    echo    설정 파일이 없습니다.
    echo   ─────────────────────────────────────────────────
    echo.
    echo    .streamlit 폴더 안의
    echo        secrets.toml.example
    echo    파일을 복사해서 이름을
    echo        secrets.toml
    echo    로 바꾸고, OpenAI 키를 넣어 주세요.
    echo.
    echo    키 발급: https://platform.openai.com/api-keys
    echo.
    pause
    exit /b 1
)

python -m streamlit run app.py

echo.
echo   앱이 종료되었습니다.
pause
