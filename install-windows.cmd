@echo off
setlocal
cd /d "%~dp0"
py -3.12 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install torch==2.6.0+cpu --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe prepare_models.py --languages en es ar
if errorlevel 1 goto failed
echo Installation complete. Run launch-windows.cmd to start GLTS.
pause
exit /b 0
:failed
echo Installation did not finish. Review the error above. Python 3.12 and internet access are required.
pause
exit /b 1
