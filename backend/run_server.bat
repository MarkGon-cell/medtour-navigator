@echo off
cd /d E:\VSCODE\medtour-navigator\backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

