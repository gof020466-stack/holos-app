@echo off
rem VOSK Transcriber v3: copy program + models for another computer (31.10.2026)
rem Usage: pack_for_transfer.bat E:\        - work set, ~1.1 GB:
rem            Russian GigaAM v3 + Parakeet v3 (Ukrainian, English) + 2 service models + speaker separation
rem        pack_for_transfer.bat E:\ full   - plus Russian 0.54 and test tools (+0.3 GB)
rem Personal data (history, log, voice recordings) is not copied. ASCII only: cmd breaks on UTF-8.

set "SRC=%~dp0.."
set "MODELS=D:\Apps\VOSK_BASE\models"
rem Double click without argument: ask where to copy
set "ROOT=%~1"
if "%ROOT%"=="" set /p "ROOT=Where to copy (flash drive letter, e.g. E:\): "
if "%ROOT%"=="" exit /b 1
set "DST=%ROOT%\vosk-transcriber-v3"

rem Service models: streaming 0.54 - phrase boundaries for GigaAM and Parakeet; small 0.22 - voice commands
set "LIST=sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16 parakeet-ultra-onnx vosk-model-small-streaming-ru-0.54 vosk-model-small-ru-0.22 diarization"
set "SKIP=tools"
if /I "%~2"=="full" (
    set "LIST=%LIST% vosk-model-ru-0.54"
    set "SKIP="
)

echo Program to %DST%
robocopy "%SRC%" "%DST%" /E /XD data __pycache__ models %SKIP% /NFL /NDL /NJH /NJS /NP
if not exist "%DST%\data" mkdir "%DST%\data"
copy /Y "%SRC%\data\settings.ini" "%DST%\data\" >nul
copy /Y "%SRC%\data\hotwords.txt" "%DST%\data\" >nul

for %%M in (%LIST%) do (
    echo Model %%M
    robocopy "%MODELS%\%%M" "%DST%\models\%%M" /E /NFL /NDL /NJH /NJS /NP
)

echo.
echo DONE: %DST%
echo On the new computer: open this folder and run install.bat
pause
