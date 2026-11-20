import os
import json
import logging
from typing import List, Dict, Any, Optional
import numpy as np
import sherpa_onnx

from core.dictionary import hotwords_options

logger = logging.getLogger("SherpaEngine")

# [v3] Модели Vosk 0.54 (Zipformer2, k2/icefall) работают на движке sherpa-onnx, а не на Kaldi.
# Сравнение на голосе автора 29.10.2026 (tools/compare_models.py): ошибок 8,1% у большой 0.54,
# 9,7% у потоковой 0.54, 11,3% у Kaldi 0.42, 17,7% у лёгкой 0.22.
STREAMING_MODEL_ID = "vosk-model-small-streaming-ru-0.54"
NUM_THREADS = 4
TOKEN_SPAN = 0.12  # конец слова ≈ время последнего слога + эта добавка (движок даёт только начала слогов)
# Большой модели нужен контекст: по фразам 0,8–3 с ошибок было 16,1%, кусками от 12 с — 6,5% (голос автора).
# 29.10.2026: куски от 6 с — расхождение с лучшим текстом 5,3%, от 12 с — 6,4% (та же запись 75 с);
# итоговый текст появляется вдвое быстрее
MIN_OFFLINE_SECONDS = 6.0
MIN_OFFLINE_SECONDS_MULTI = 15.0
# [v3, 12.11.2026] «В куске есть речь»: доля 50-мс кадров громче порога (шкала -1…1)
VOICE_RMS = 0.02
VOICE_MIN_SECONDS = 0.5


def _nemo_files(path: str) -> Optional[dict]:
    """
    [v3] Модели NeMo в сборке sherpa-onnx — файлы прямо в папке модели:
    Parakeet TDT v3 (NVIDIA) и [31.10.2026] GigaAM v3 (Сбер). Берём int8, если есть.
    """
    out = {"tokens": os.path.join(path, "tokens.txt")}
    for part in ("encoder", "decoder", "joiner"):
        for name in (f"{part}.int8.onnx", f"{part}.onnx"):
            if os.path.isfile(os.path.join(path, name)):
                out[part] = os.path.join(path, name)
                break
    return out if len(out) == 4 and os.path.isfile(out["tokens"]) else None


def is_parakeet_model(path: str) -> bool:
    return _nemo_files(path) is not None


def is_onnx_asr_model(path: str) -> bool:
    """
    [v3, 12.11.2026] Parakeet Ultra (moondream, дообученная Parakeet TDT v3) — экспорт ONNX
    в формате onnx-asr (mrfakename/parakeet-ultra-ONNX): config.json + encoder-model.onnx + decoder_joint.
    Повод — тест 12.11.2026: на украинском Ultra в Handy почти без ошибок, Parakeet v3 в VOSK — много.
    """
    try:
        with open(os.path.join(path, "config.json"), encoding="utf-8") as f:
            kind = json.load(f).get("model_type", "")
    except Exception:
        return False
    return kind == "nemo-conformer-tdt" and os.path.isfile(os.path.join(path, "encoder-model.onnx"))


class _OnnxAsrOffline:
    """Офлайн-проход моделью onnx-asr: звук фразы → токены со временем (как у sherpa-onnx)."""
    def __init__(self, model_dir: str):
        import onnx_asr
        self.model = onnx_asr.load_model("nemo-conformer-tdt", model_dir).with_timestamps()

    def tokens(self, audio: np.ndarray, sample_rate: int):
        r = self.model.recognize(audio, sample_rate=sample_rate)
        return list(r.tokens or []), list(r.timestamps or [])


def is_sherpa_model(path: str) -> bool:
    return is_parakeet_model(path) or is_onnx_asr_model(path) or (
        os.path.isdir(os.path.join(path, "am-onnx")) and os.path.isfile(os.path.join(path, "lang", "tokens.txt")))


def _files(model_dir: str, int8: bool) -> dict:
    sfx = ".int8.onnx" if int8 else ".onnx"
    am = os.path.join(model_dir, "am-onnx")
    return dict(encoder=os.path.join(am, "encoder" + sfx), decoder=os.path.join(am, "decoder" + sfx),
                joiner=os.path.join(am, "joiner" + sfx), tokens=os.path.join(model_dir, "lang", "tokens.txt"))


class SherpaModel:
    """
    Загруженная модель 0.54. Два прохода:
    потоковая модель — живой текст и границы фраз по паузам;
    большая офлайн-модель (если это не сама потоковая) — итоговый текст каждой фразы.
    """
    def __init__(self, model_dir: str):
        name = os.path.basename(model_dir.rstrip("\\/"))
        streaming_dir = model_dir if "streaming" in name else os.path.join(os.path.dirname(model_dir), STREAMING_MODEL_ID)
        if not is_sherpa_model(streaming_dir):
            raise FileNotFoundError(f"Нужна потоковая модель {STREAMING_MODEL_ID} рядом с {name}")

        # Потоковая — полная точность: на голосе автора int8 давала 16,1% ошибок против 9,7%
        self.online = sherpa_onnx.OnlineRecognizer.from_transducer(
            **_files(streaming_dir, int8=False), num_threads=NUM_THREADS, sample_rate=16000,
            decoding_method="modified_beam_search", max_active_paths=10,
            enable_endpoint_detection=True,
            rule1_min_trailing_silence=2.4,   # тишина без речи
            rule2_min_trailing_silence=0.8,   # пауза после речи — конец фразы
            rule3_min_utterance_length=20,    # фраза не длиннее 20 с
            **hotwords_options(streaming_dir))
        # [v3, 12.11.2026] Многоязычная модель: русская потоковая на украинском может не дать черновика —
        # такой кусок не выбрасывать, если в нём есть звук (иначе 12.11 терялся конец украинской речи)
        self.multilingual = False
        if is_onnx_asr_model(model_dir):
            self.offline = _OnnxAsrOffline(model_dir)
            self.multilingual = True
            return
        if is_parakeet_model(model_dir):
            self.multilingual = "parakeet" in name
            # [v3] Parakeet TDT v3: 25 языков (uk, ru, en…), знаки и заглавные ставит сам.
            # Потоковая русская 0.54 нужна только для границ фраз и серого черновика
            # GigaAM v3 punct — тоже сам ставит знаки; только русский
            self.offline = sherpa_onnx.OfflineRecognizer.from_transducer(
                **_nemo_files(model_dir), num_threads=NUM_THREADS, sample_rate=16000, model_type="nemo_transducer",
                decoding_method="greedy_search")
            return
        # Большая — int8: точность та же, что у полной, быстрее и меньше памяти
        self.offline = None if streaming_dir == model_dir else sherpa_onnx.OfflineRecognizer.from_transducer(
            **_files(model_dir, int8=True), num_threads=NUM_THREADS, sample_rate=16000,
            decoding_method="modified_beam_search", max_active_paths=10,
            **hotwords_options(model_dir))


def _tokens_to_words(tokens: List[str], timestamps: List[float], offset: float) -> List[Dict[str, Any]]:
    words = []
    for tok, ts in zip(tokens, timestamps):
        if tok.startswith(" ") or not words:
            words.append({"word": tok.strip(), "start": offset + ts, "end": offset + ts + TOKEN_SPAN, "conf": 1.0})
        else:
            words[-1]["word"] += tok
            words[-1]["end"] = offset + ts + TOKEN_SPAN
    return [w for w in words if w["word"]]


class SherpaRecognizer:
    """
    Повторяет интерфейс vosk.KaldiRecognizer (AcceptWaveform / Result / PartialResult / FinalResult),
    чтобы запись, диктовка, дописывание и файлы работали без изменений.
    С большой моделью фразы копятся до MIN_OFFLINE_SECONDS; пока они не распознаны начисто,
    их черновой текст потоковой модели идёт в PartialResult.
    """
    def __init__(self, model: SherpaModel, sample_rate: int = 16000):
        self.model = model
        self.sample_rate = sample_rate
        self.stream = model.online.create_stream()
        self.segment: List[np.ndarray] = []
        self.draft: List[str] = []  # черновики накопленных фраз
        self.offset = 0.0  # секунды звука до начала накопленного куска
        self._ready: Optional[dict] = None

    def SetWords(self, enabled: bool):
        pass  # тайминги слов отдаются всегда

    def AcceptWaveform(self, data: bytes) -> bool:
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768
        self.stream.accept_waveform(self.sample_rate, samples)
        self.segment.append(samples)
        online = self.model.online
        while online.is_ready(self.stream):
            online.decode_stream(self.stream)
        if not online.is_endpoint(self.stream):
            return False
        if self.model.offline is None:
            self._ready = self._finish_segment()
            online.reset(self.stream)
            return True
        phrase = online.get_result(self.stream).strip()
        online.reset(self.stream)
        if phrase:
            self.draft.append(phrase)
        # [v3, 12.11.2026] Многоязычной — куски длиннее: на украинском 12.11 куски от 6 с рвали фразы
        # («повзали.», «штуч.», «Сума 12. двадцять»); кусками по тишине от 15 с — как в Handy
        min_seconds = MIN_OFFLINE_SECONDS_MULTI if getattr(self.model, "multilingual", False) else MIN_OFFLINE_SECONDS
        if sum(len(s) for s in self.segment) / self.sample_rate < min_seconds:
            return False
        if not self.draft and not self._has_voice():
            # [v3] Потоковая модель речи не слышала: большая на тишине выдумывает «афина»
            # (31.10.2026, 7 из 7 ложных — в кусках из одной тишины с щелчком или сигналом)
            self._skip_segment()
            return False
        self._ready = self._finish_segment()
        return True

    def Result(self) -> str:
        res, self._ready = self._ready or {"text": "", "result": []}, None
        return json.dumps(res, ensure_ascii=False)

    def PartialResult(self) -> str:
        current = self.model.online.get_result(self.stream).strip()
        return json.dumps({"partial": " ".join(self.draft + [current]).strip()}, ensure_ascii=False)

    def FinalResult(self) -> str:
        if self.model.offline is None:
            # Только потоковая модель: дочитываем хвост
            self.stream.accept_waveform(self.sample_rate, np.zeros(int(self.sample_rate * 0.6), dtype=np.float32))
            self.stream.input_finished()
            while self.model.online.is_ready(self.stream):
                self.model.online.decode_stream(self.stream)
        elif not self.draft and not self.model.online.get_result(self.stream).strip() and not self._has_voice():
            self._skip_segment()
            return json.dumps({"text": "", "result": []}, ensure_ascii=False)
        return json.dumps(self._finish_segment(), ensure_ascii=False)

    def _has_voice(self) -> bool:
        """[v3, 12.11.2026] Только для многоязычных моделей: есть ли в куске громкая речь (не тишина со щелчком)."""
        if not getattr(self.model, "multilingual", False) or not self.segment:
            return False
        audio = np.concatenate(self.segment)
        frame = int(self.sample_rate * 0.05)
        n = len(audio) // frame
        if n == 0:
            return False
        rms = np.sqrt(np.mean(audio[:n * frame].reshape(n, frame) ** 2, axis=1))
        return int((rms > VOICE_RMS).sum()) * 0.05 >= VOICE_MIN_SECONDS

    def _skip_segment(self) -> np.ndarray:
        """Сбрасывает накопленный кусок; время сдвигается — тайминги слов совпадают со звуком."""
        audio = np.concatenate(self.segment) if self.segment else np.zeros(0, dtype=np.float32)
        self.offset += len(audio) / self.sample_rate
        self.segment = []
        self.draft = []
        return audio

    def _finish_segment(self) -> dict:
        offset = self.offset
        audio = self._skip_segment()
        if len(audio) < self.sample_rate * 0.2:
            return {"text": "", "result": []}

        if isinstance(self.model.offline, _OnnxAsrOffline):
            tokens, timestamps = self.model.offline.tokens(audio, self.sample_rate)
        elif self.model.offline is not None:
            s = self.model.offline.create_stream()
            s.accept_waveform(self.sample_rate, audio)
            self.model.offline.decode_stream(s)
            tokens, timestamps = list(s.result.tokens), list(s.result.timestamps)
        else:
            r = json.loads(self.model.online.get_result_as_json_string(self.stream))
            tokens, timestamps = r.get("tokens", []), r.get("timestamps", [])

        words = _tokens_to_words(tokens, timestamps, offset)
        return {"text": " ".join(w["word"] for w in words), "result": words}
