@echo off
REM Igual que run_daily.bat pero guarda toda la salida en last_run.log
REM (util para revisar que paso cuando la ventana se cierra sola).
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
"%~dp0venv\Scripts\python.exe" "%~dp0main.py" "%~dp0config.yaml" > "%~dp0last_run.log" 2>&1
