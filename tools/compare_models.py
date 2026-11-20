"""
Сравнение моделей распознавания на одном аудиофайле (29.10.2026, Claude Code).

Запуск:  python tools\\compare_models.py <аудио> [эталон.txt] [--seconds N]
- аудио — любой формат, который читает ffmpeg; берутся первые N секунд (по умолчанию весь файл);
- эталон — точный текст сказанного; если есть, считается WER (доля ошибочных слов).
Результаты каждой модели — в <аудио>.<модель>.txt рядом с аудио.
"""
import os
import re
import sys
import json
import time
import subprocess
import numpy as np

MODELS_DIR = r"D:\Apps\VOSK_BASE\models"
SR = 16000


def load_audio(path: str, seconds: float = 0) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", path]
    if seconds:
        cmd += ["-t", str(seconds)]
    cmd += ["-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16)


def split_on_silence(pcm: np.ndarray, min_s: float = 12, max_s: float = 25) -> list:
    """Куски для офлайн-модели: режем в самом тихом месте между min_s и max_s секундами."""
    frame = int(SR * 0.03)
    chunks, start = [], 0
    while len(pcm) - start > max_s * SR:
        lo, hi = start + int(min_s * SR), start + int(max_s * SR)
        seg = pcm[lo:hi].astype(np.float32)
        n = len(seg) // frame
        energy = (seg[:n * frame].reshape(n, frame) ** 2).mean(axis=1)
        cut = lo + int(np.argmin(energy)) * frame + frame // 2
        chunks.append(pcm[start:cut])
        start = cut
    chunks.append(pcm[start:])
    return chunks


def run_kaldi(model_id: str, pcm: np.ndarray) -> str:
    from vosk import Model, KaldiRecognizer, SetLogLevel
    SetLogLevel(-1)
    rec = KaldiRecognizer(Model(os.path.join(MODELS_DIR, model_id)), SR)
    out = []
    data = pcm.tobytes()
    for i in range(0, len(data), 8000):
        if rec.AcceptWaveform(data[i:i + 8000]):
            out.append(json.loads(rec.Result())["text"])
    out.append(json.loads(rec.FinalResult())["text"])
    return " ".join(t for t in out if t)


def _onnx_paths(model_id: str, int8: bool) -> dict:
    d = os.path.join(MODELS_DIR, model_id)
    sfx = ".int8.onnx" if int8 else ".onnx"
    return dict(encoder=os.path.join(d, "am-onnx", "encoder" + sfx),
                decoder=os.path.join(d, "am-onnx", "decoder" + sfx),
                joiner=os.path.join(d, "am-onnx", "joiner" + sfx),
                tokens=os.path.join(d, "lang", "tokens.txt"))


def run_offline_054(model_id: str, pcm: np.ndarray, int8: bool) -> str:
    import sherpa_onnx
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        **_onnx_paths(model_id, int8), num_threads=4, provider="cpu", sample_rate=SR,
        dither=3e-5, max_active_paths=10, decoding_method="modified_beam_search")
    out = []
    for chunk in split_on_silence(pcm):
        s = rec.create_stream()
        s.accept_waveform(SR, chunk.astype(np.float32) / 32768)
        rec.decode_stream(s)
        out.append(s.result.text)
    return " ".join(t for t in out if t)


def run_streaming_054(model_id: str, pcm: np.ndarray, int8: bool) -> str:
    import sherpa_onnx
    rec = sherpa_onnx.OnlineRecognizer.from_transducer(
        **_onnx_paths(model_id, int8), num_threads=4, sample_rate=SR, dither=3e-5,
        decoding_method="modified_beam_search", max_active_paths=10, enable_endpoint_detection=True)
    s = rec.create_stream()
    out = []
    samples = pcm.astype(np.float32) / 32768
    step = SR // 10  # по 100 мс, как с микрофона
    for i in range(0, len(samples), step):
        s.accept_waveform(SR, samples[i:i + step])
        while rec.is_ready(s):
            rec.decode_stream(s)
        if rec.is_endpoint(s):
            out.append(rec.get_result(s))
            rec.reset(s)
    s.accept_waveform(SR, np.zeros(int(SR * 0.6), dtype=np.float32))
    s.input_finished()
    while rec.is_ready(s):
        rec.decode_stream(s)
    out.append(rec.get_result(s))
    return " ".join(t.strip() for t in out if t.strip())


def run_gigaam(model_id: str, pcm: np.ndarray) -> str:
    """[31.10.2026] GigaAM v3 (Сбер), сборка sherpa-onnx: NeMo-трансдьюсер, куски по тишине."""
    import sherpa_onnx
    d = os.path.join(MODELS_DIR, model_id)
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=os.path.join(d, "encoder.int8.onnx"), decoder=os.path.join(d, "decoder.onnx"),
        joiner=os.path.join(d, "joiner.onnx"), tokens=os.path.join(d, "tokens.txt"),
        num_threads=4, sample_rate=SR, model_type="nemo_transducer", decoding_method="greedy_search")
    out = []
    for chunk in split_on_silence(pcm):
        s = rec.create_stream()
        s.accept_waveform(SR, chunk.astype(np.float32) / 32768)
        rec.decode_stream(s)
        out.append(s.result.text)
    return " ".join(t for t in out if t)


def norm(text: str) -> list:
    text = text.lower().replace("ё", "е")
    # Дефис не считаем ошибкой: старые модели пишут «что то» вместо «что-то»
    return re.sub(r"[^\w\s]", " ", text).split()


def wer(ref: list, hyp: list) -> float:
    d = list(range(len(hyp) + 1))
    for i in range(1, len(ref) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(hyp) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (ref[i - 1] != hyp[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(hyp)] / max(1, len(ref))


MODELS = [
    ("vosk-0.42", lambda p: run_kaldi("vosk-model-ru-0.42", p)),
    ("vosk-small-0.22", lambda p: run_kaldi("vosk-model-small-ru-0.22", p)),
    ("0.54-big", lambda p: run_offline_054("vosk-model-ru-0.54", p, int8=False)),
    ("0.54-big-int8", lambda p: run_offline_054("vosk-model-ru-0.54", p, int8=True)),
    ("0.54-stream", lambda p: run_streaming_054("vosk-model-small-streaming-ru-0.54", p, int8=False)),
    ("0.54-stream-int8", lambda p: run_streaming_054("vosk-model-small-streaming-ru-0.54", p, int8=True)),
    ("gigaam-v3", lambda p: run_gigaam("sherpa-onnx-nemo-transducer-giga-am-v3-russian-2025-12-16", p)),
    ("gigaam-v3-punct", lambda p: run_gigaam("sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16", p)),
]
# --models a,b — только эти модели (например: --models 0.54-big-int8,gigaam-v3)
if "--models" in sys.argv:
    _only = sys.argv[sys.argv.index("--models") + 1].split(",")
    MODELS = [m for m in MODELS if m[0] in _only]


def _skip_values() -> list:
    """Значения ключей --seconds и --models — не имена файлов."""
    return [sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a in ("--seconds", "--models")]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--") and a not in _skip_values()]
    seconds = float(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else 0
    if seconds:
        args = [a for a in args if a != str(sys.argv[sys.argv.index("--seconds") + 1])]
    audio = args[0]
    ref = norm(open(args[1], encoding="utf-8").read()) if len(args) > 1 else None
    pcm = load_audio(audio, seconds)
    dur = len(pcm) / SR
    print(f"Файл: {os.path.basename(audio)}, {dur:.0f} с" + (f", эталон {len(ref)} слов" if ref else ""))
    results = {}
    for name, fn in MODELS:
        t = time.time()
        text = fn(pcm)
        el = time.time() - t
        results[name] = text
        with open(f"{audio}.{name}.txt", "w", encoding="utf-8") as f:
            f.write(text)
        line = f"{name:<17} {el:6.1f} с  (x{dur / max(el, 1e-6):4.1f} быстрее реального)  слов {len(norm(text)):5d}"
        if ref:
            line += f"  WER {wer(ref, norm(text)) * 100:5.1f}%"
        print(line, flush=True)
    if not ref and len(results) > 1:
        first = next(iter(results))
        base = norm(results[first])
        for name in results:
            if name != first:
                print(f"расхождение {name} с {first}: {wer(base, norm(results[name])) * 100:.1f}%")


if __name__ == "__main__":
    main()
