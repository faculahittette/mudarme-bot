@echo off
REM Doble clic: programa mudarme-bot todos los dias a las 12:00 y 20:00.
REM Se puede correr de nuevo sin problema (actualiza la tarea existente).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\programar_tarea_diaria.ps1"
echo.
pause
