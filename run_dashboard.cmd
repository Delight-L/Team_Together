@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -X utf8 main.py %*
) else (
  python -X utf8 main.py %*
)
if errorlevel 1 (
  echo 실행 실패: 루트 requirements.txt의 패키지 설치와 README.md를 확인하세요.
  pause
)
