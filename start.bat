@echo off
cd /d "%~dp0"
title QR Generator - no cierres esta ventana
if not exist .venv\Scripts\python.exe (
    echo Instalando dependencias, solo la primera vez...
    python -m venv .venv
    .venv\Scripts\python -m pip install -q -r requirements.txt
)
echo.
echo  Panel: http://127.0.0.1:5000
echo  Deja esta ventana abierta mientras uses el panel. Cierrala para apagarlo.
echo.
.venv\Scripts\python app.py --open
echo.
echo El servidor se ha detenido. Si ves un error arriba, copialo.
pause
