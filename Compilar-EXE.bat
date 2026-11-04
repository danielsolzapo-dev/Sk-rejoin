@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .build
if errorlevel 1 goto fail
.build\Scripts\python.exe -m pip install pyinstaller==6.16.0 -r requirements.txt
if errorlevel 1 goto fail
.build\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --hidden-import pystray._win32 --name RejoinDesk --icon artwork/sk.ico --add-data "artwork;artwork" --add-data "heartbeat.luau;." --add-data "distribution.json;." app.py
if errorlevel 1 goto fail
echo Executavel autonomo em dist\RejoinDesk.exe
pause
exit /b 0
:fail
echo Falha ao compilar. Confira a instalacao de Python 3 e a conexao.
pause
exit /b 1
