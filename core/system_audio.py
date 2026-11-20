"""
[v3.2, 18.11.2026] Ф1: звук компьютера (то, что играет в динамиках или наушниках) — для записи созвонов.

Библиотека выбрана пробой 18.11.2026:
PyAudioWPatch — WASAPI loopback, тот же PortAudio, что у sounddevice, приём звука в своём потоке.
У WASAPI loopback одна особенность: пока компьютер молчит, звука нет совсем (0 блоков за 3 с).
Поэтому на время записи в устройство вывода идёт «тишина» — нули; loopback тогда отдаёт звук
ровно, без провалов, а текст и звук не расходятся по времени. Тишину человек не слышит.

Звук не уходит с компьютера: только чтение из системного микшера на этом ПК.
"""
import logging
import threading
from typing import Optional

import numpy as np

logger = logging.getLogger("SystemAudio")

TARGET_RATE = 16000
MAX_BUFFER_S = 2.0   # больше — значит, микрофон отстал; старое выбрасываем, чтобы не копить задержку


def available() -> bool:
    try:
        import pyaudiowpatch  # noqa: F401
        return True
    except Exception:
        return False


def speaker_name() -> str:
    """Имя устройства вывода, звук которого будет записан; "" — не найдено."""
    try:
        import pyaudiowpatch as pa
        p = pa.PyAudio()
        try:
            return p.get_default_wasapi_loopback()["name"].replace(" [Loopback]", "")
        finally:
            p.terminate()
    except Exception as e:
        logger.warning(f"Устройство вывода не найдено: {e}")
        return ""


def _to_16k_mono(data: bytes, rate: int, channels: int) -> np.ndarray:
    audio = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    if channels > 1:
        usable = len(audio) - len(audio) % channels
        audio = audio[:usable].reshape(-1, channels).mean(axis=1)
    if rate == TARGET_RATE:
        return audio
    if rate % TARGET_RATE == 0:
        f = rate // TARGET_RATE
        usable = len(audio) - len(audio) % f
        return audio[:usable].reshape(-1, f).mean(axis=1)
    n = max(1, int(len(audio) * TARGET_RATE / rate))
    return np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio)


class SystemAudioCapture:
    """Звук компьютера → 16 кГц, моно, float32 в буфере; read(n) отдаёт ровно n сэмплов."""

    def __init__(self):
        self._pa = None
        self._stream = None
        self._keep_alive = None
        self._buf = np.zeros(0, dtype=np.float32)
        self._lock = threading.Lock()
        self.rate = 0
        self.channels = 0
        self.name = ""

    def start(self):
        import pyaudiowpatch as pa
        import sounddevice as sd
        self._pa = pa.PyAudio()
        lb = self._pa.get_default_wasapi_loopback()
        self.name = lb["name"].replace(" [Loopback]", "")
        self.rate = int(lb["defaultSampleRate"])
        self.channels = int(lb["maxInputChannels"]) or 2
        # «Тишина» в тот же вывод: без неё loopback молчит, пока не играет звук
        try:
            self._keep_alive = sd.OutputStream(samplerate=self.rate, channels=self.channels, dtype="int16",
                                               callback=lambda out, frames, t, status: out.fill(0))
            self._keep_alive.start()
        except Exception as e:
            self._keep_alive = None
            logger.warning(f"Тихий вывод не открыт — в тишине звук компьютера будет с провалами: {e}")
        self._stream = self._pa.open(format=pa.paInt16, channels=self.channels, rate=self.rate, input=True,
                                     input_device_index=lb["index"], frames_per_buffer=int(self.rate * 0.05),
                                     stream_callback=self._callback)
        logger.info(f"Звук компьютера: {self.name}, {self.rate} Гц, {self.channels} кан.")

    def _callback(self, data, frames, time_info, status):
        import pyaudiowpatch as pa
        chunk = _to_16k_mono(data, self.rate, self.channels)
        with self._lock:
            self._buf = np.concatenate((self._buf, chunk))
            limit = int(TARGET_RATE * MAX_BUFFER_S)
            if len(self._buf) > limit:
                self._buf = self._buf[-limit:]
        return (None, pa.paContinue)

    def available_samples(self) -> int:
        with self._lock:
            return len(self._buf)

    def read(self, n: int) -> np.ndarray:
        """n сэмплов; не хватает — дополняется тишиной (микрофон задаёт ход времени)."""
        with self._lock:
            out, self._buf = self._buf[:n], self._buf[n:]
        if len(out) < n:
            out = np.concatenate((out, np.zeros(n - len(out), dtype=np.float32)))
        return out

    def stop(self):
        for closer in (lambda: self._stream.stop_stream(), lambda: self._stream.close(),
                       lambda: self._keep_alive.stop(), lambda: self._keep_alive.close(),
                       lambda: self._pa.terminate()):
            try:
                closer()
            except Exception:
                pass
        self._stream = self._keep_alive = self._pa = None
