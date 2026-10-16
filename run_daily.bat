@echo off
REM Corre mudarme-bot siempre desde su propio directorio (%~dp0 = carpeta de este .bat),
REM asi usa siempre la misma base scrapdep.db. La salida se ve en la ventana y
REM ademas queda guardada en last_run.log.
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
"%~dp0venv\Scripts\python.exe" "%~dp0main.py" "%~dp0config.yaml"
