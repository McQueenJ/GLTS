@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Run install-windows.cmd first.
 pause
 exit /b 1
)
echo Open http://127.0.0.1:5000 in your browser after the server starts.
echo Keep this window open while using GLTS. Press Ctrl+C to stop.
.venv\Scripts\python.exe app.py
pause
