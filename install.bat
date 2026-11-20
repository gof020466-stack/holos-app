@echo off
rem VOSK Transcriber v3: install on another computer (31.10.2026)
rem Installs Python 3.13 and ffmpeg via winget (needs internet) and the program libraries.
rem ASCII only: cmd breaks on UTF-8.
cd /d "%~dp0"

rem "where python" is not enough: Windows has a Microsoft Store stub named python
python -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo Installing Python 3.13...
    winget install -e --id Python.Python.3.13 --accept-package-agreements --accept-source-agreements
    echo.
    echo Python installed. Close this window and run install.bat again.
    pause
    exit /b 0
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo Installing ffmpeg...
    winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
)

echo Installing program libraries...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: libraries not installed. Show the message above to Claude.
    pause
    exit /b 1
)

echo.
echo DONE. Run start.bat. Shortcut: right click start.bat - Send to - Desktop.
echo If ffmpeg was installed just now - restart the computer, otherwise recordings are not saved.
pause
