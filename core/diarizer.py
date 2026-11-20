"""
[v3] Диаризация — кто говорит (29.10.2026).
sherpa-onnx: сегментация pyannote 3.0 + отпечаток голоса 3D-Speaker ERes2Net, модели — models\\diarization.
Проверка на записи звонка, 3 мин: при «говорящих 2» — 2 говорящих, реплики разделены верно; авто при пороге 0.5 — 10,
при 1.1 — 2. Скорость — ~5× быстрее реального времени (3 мин за 34 с).
"""
import os
import sys
import json
import logging
import subprocess
import tempfile
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger("Diarizer")

# Как в vosk_manager: на другом компьютере — «models» рядом с программой (файл запускается и отдельным процессом)
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "diarization")
if not os.path.isdir(MODELS_DIR):  # [12.11.2026] рядом с программой (установщик) главнее домашней папки
    MODELS_DIR = r"D:\Apps\VOSK_BASE\models\diarization"
SEGMENTATION = os.path.join(MODELS_DIR, "sherpa-onnx-pyannote-segmentation-3-0", "model.onnx")
EMBEDDING = os.path.join(MODELS_DIR, "speaker-embedding.onnx")
AUTO_THRESHOLD = 1.1  # число говорящих неизвестно: меньше порог — больше «говорящих»


def available() -> bool:
    return os.path.isfile(SEGMENTATION) and os.path.isfile(EMBEDDING)


def diarize(pcm: np.ndarray, num_speakers: int = 0) -> List[tuple]:
    """
    pcm — int16, 16 кГц. num_speakers 0 — определить самому. Возвращает [(начало, конец, говорящий)].
    Считается в отдельном процессе: sherpa-onnx не отпускает GIL, и окно «не отвечало»
    (запись 12 мин — 149 с без единого шага интерфейса; 29.10.2026).
    """
    fd, raw_path = tempfile.mkstemp(suffix=".pcm")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(pcm.astype(np.int16).tobytes())
        # Программа идёт под pythonw (без консоли); дочернему процессу нужен обычный python для вывода
        exe = sys.executable
        console_exe = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.basename(exe).lower() == "pythonw.exe" and os.path.isfile(console_exe):
            exe = console_exe
        res = subprocess.run([exe, os.path.abspath(__file__), raw_path, str(num_speakers)],
                             capture_output=True, text=True, encoding="utf-8", check=True,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        segs = [tuple(s) for s in json.loads(res.stdout.strip().splitlines()[-1])]
    finally:
        os.remove(raw_path)
    logger.info(f"Диаризация: {len(pcm) / 16000:.0f} с, говорящих {len({s[2] for s in segs})}")
    return segs


def _merge_small(segs: List[tuple], keep: int = 0) -> List[tuple]:
    """
    Мелкие группы (шум, короткие «да» — до 15 с или 3% речи) отдаём ближайшей по времени реплике крупного говорящего.
    keep > 0 — оставить не больше keep самых длинных говорящих. Номера — по порядку появления.
    Звонок 12 мин, «говорящих 2»: было {562 с, 13 с} — второй собеседник терялся; с запасом и склейкой — {147, 423}.
    """
    if not segs:
        return segs
    dur: Dict[int, float] = {}
    for s, e, sp in segs:
        dur[sp] = dur.get(sp, 0.0) + e - s
    total = sum(dur.values())
    big = [sp for sp, d in sorted(dur.items(), key=lambda x: -x[1]) if d >= min(15.0, 0.03 * total)] or [max(dur, key=dur.get)]
    if keep > 0:
        big = big[:keep]
    out = []
    for i, (s, e, sp) in enumerate(segs):
        if sp not in big:
            near = [(min(abs(s - e2), abs(s2 - e)), sp2) for j, (s2, e2, sp2) in enumerate(segs) if j != i and sp2 in big]
            sp = min(near)[1] if near else big[0]
        out.append((s, e, sp))
    order = {}
    for _, _, sp in out:
        order.setdefault(sp, len(order))
    return [(s, e, order[sp]) for s, e, sp in out]


def _diarize_here(pcm: np.ndarray, num_speakers: int) -> List[tuple]:
    if num_speakers > 0:
        # С запасом: лишние группы — шум, их склеит _merge_small
        return _merge_small(_cluster(pcm, num_speakers + 1), keep=num_speakers)
    return _merge_small(_cluster(pcm, 0))


def _cluster(pcm: np.ndarray, num_speakers: int) -> List[tuple]:
    import sherpa_onnx
    cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=SEGMENTATION), num_threads=4),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=EMBEDDING, num_threads=4),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=num_speakers if num_speakers > 0 else -1,
                                                    threshold=AUTO_THRESHOLD),
        min_duration_on=0.3, min_duration_off=0.5)
    audio = pcm.astype(np.float32) / 32768
    segs = sherpa_onnx.OfflineSpeakerDiarization(cfg).process(audio).sort_by_start_time()
    return [(s.start, s.end, s.speaker) for s in segs]


def label_words(words: List[Dict[str, Any]], segments: List[tuple]):
    """Каждому слову — номер говорящего (поле "speaker", с 1) по середине слова; вне отрезков — ближайший."""
    for w in words:
        t = (float(w.get("start", 0)) + float(w.get("end", 0))) / 2
        best, dist = None, 1e9
        for start, end, sp in segments:
            if start <= t <= end:
                best = sp
                break
            d = min(abs(t - start), abs(t - end))
            if d < dist:
                best, dist = sp, d
        if best is not None:
            w["speaker"] = best + 1


def format_dialog(words: List[Dict[str, Any]], punctuate) -> Optional[str]:
    """Текст по репликам: «[м:сс] Говорящий N: …», реплика — абзац. punctuate(слова) → текст реплики."""
    if not any("speaker" in w for w in words):
        return None
    turns, cur = [], None
    for w in words:
        sp = w.get("speaker", cur)
        if sp != cur or not turns:
            turns.append((sp, float(w.get("start", 0)), []))
            cur = sp
        turns[-1][2].append(w)
    out = []
    for sp, start, ws in turns:
        out.append(f"[{int(start) // 60}:{int(start) % 60:02d}] Говорящий {sp}: {punctuate(ws)}")
    return "\n\n".join(out)


if __name__ == "__main__":
    # Отдельный процесс для diarize(): <файл PCM int16 16 кГц> <число говорящих>; ответ — JSON последней строкой
    data = np.fromfile(sys.argv[1], dtype=np.int16)
    print(json.dumps(_diarize_here(data, int(sys.argv[2]))))
