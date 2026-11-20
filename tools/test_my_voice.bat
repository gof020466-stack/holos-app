@echo off
chcp 65001 >nul
cd /d D:\Apps\vosk-transcriber-v3
start "" notepad.exe "D:\Apps\vosk-transcriber-v3\tools\test_text.txt"
echo.
type tools\test_text.txt
echo.
echo.
timeout /t 5
python tools\record_sample.py data\my_voice.wav 75
python tools\compare_models.py data\my_voice.wav tools\test_text.txt 2>nul > data\my_voice_result.txt
type data\my_voice_result.txt
echo.
echo Result saved: D:\Apps\vosk-transcriber-v3\data\my_voice_result.txt
pause
