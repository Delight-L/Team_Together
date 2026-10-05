@echo off
cd /d "%~dp0"
"C:\Users\user\Documents\Codex\2026-10-02\https-github-com-delight-l-team\work\dashboard-venv\Scripts\python.exe" -m streamlit run main.py --server.address=127.0.0.1 --server.port=8501
