@echo off
chcp 65001 >nul
cd /d "%~dp0"
python tools\push_to_github.py
echo.
pause
