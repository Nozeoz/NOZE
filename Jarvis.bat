@echo off
title Jarvis HQ
cd /d "%~dp0"
echo Menyalakan Jarvis... tutup jendela ini untuk mematikan.
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:3000"
call npm.cmd start
pause
