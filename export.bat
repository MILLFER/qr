@echo off
cd /d "%~dp0"
.venv\Scripts\python app.py --export
git add docs
git commit -m "Actualizar redirects QR"
git push
pause
