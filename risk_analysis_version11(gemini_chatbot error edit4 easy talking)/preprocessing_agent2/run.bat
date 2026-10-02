@echo off
chcp 65001 >nul
cd /d "%~dp0"
python main.py %*
if errorlevel 1 echo 전처리 실패: outputs\validation_report.json을 확인하세요.
pause
