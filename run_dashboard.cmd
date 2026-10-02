@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m streamlit run main.py --server.address=127.0.0.1 --server.port=8501
) else (
  python -m streamlit run main.py --server.address=127.0.0.1 --server.port=8501
)
