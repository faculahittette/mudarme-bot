@echo off
REM Wrapper para correr mudarme-bot siempre desde su propio directorio.
REM %~dp0 = carpeta donde vive este .bat (mudarme-bot), con barra final.
REM Esto evita que se cree una base scrapdep.db nueva en otra carpeta.
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" "%~dp0main.py" "%~dp0config.yaml"
