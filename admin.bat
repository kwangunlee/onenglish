@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo   OnEnglish 관리자 화면을 시작합니다...
echo   (아이들 화면과 따로 뜹니다. 주소: http://localhost:8502)
echo.

if not exist ".streamlit\secrets.toml" (
    echo   [안내] .streamlit\secrets.toml 이 없습니다.
    echo          ADMIN_PASSWORD 를 넣은 secrets.toml 을 먼저 만들어 주세요.
    echo.
    pause
    exit /b 1
)

python -m streamlit run admin.py --server.port 8502

echo.
echo   관리자 화면이 종료되었습니다.
pause
