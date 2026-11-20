"""
Запись образца голоса с микрофона по умолчанию в WAV 16 кГц (29.10.2026, Claude Code).
Запуск:  python tools\\record_sample.py <файл.wav> [секунды]
"""
import sys
import wave
import sounddevice as sd

SR = 16000

def main():
    out = sys.argv[1]
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"Запись {seconds} с началась. Читайте текст из Блокнота обычным темпом.", flush=True)
    data = sd.rec(seconds * SR, samplerate=SR, channels=1, dtype="int16")
    sd.wait()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print(f"Готово: {out}", flush=True)

if __name__ == "__main__":
    main()
