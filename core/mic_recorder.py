import os
import time
import queue
import contextlib
import logging
import json
import subprocess
import numpy as np
import sounddevice as sd
from typing import List, Dict, Any, Optional
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger("MicRecorder")

TARGET_SAMPLE_RATE = 16000
FALLBACK_RATES = [16000, 44100, 48000, 22050, 32000]

def get_input_devices() -> List[Dict[str, Any]]:
    """
    Возвращает список доступных микрофонов.
    """
    devices = []
    try:
        device_list = sd.query_devices()
        default_device_info = sd.default.device
        default_input_idx = default_device_info[0] if default_device_info else -1
        
        for idx, dev in enumerate(device_list):
            if dev.get('max_input_channels', 0) > 0:
                is_default = (idx == default_input_idx)
                devices.append({
                    "id": idx,
                    "name": dev.get('name', f"Микрофон {idx}"),
                    "is_default": is_default,
                    "default_sr": int(dev.get('default_sample_rate', 16000))
                })
    except Exception as e:
        logger.error(f"Ошибка при получении списка устройств записи: {e}")
    return devices

class MicTranscriptionWorker(QThread):
    # Сигналы для связи с главным интерфейсом
    partial_result = Signal(str)    # Частичный распознанный текст (текущая фраза)
    final_chunk = Signal(str)       # Окончательно распознанный блок текста
    final_words = Signal(list)      # [v3] Слова этого блока с таймингами (для пунктуации по паузам)
    volume_changed = Signal(float)  # Уровень громкости (от 0.0 до 1.0) для визуализатора
    error = Signal(str)             # Сообщение об ошибке
    recording_finished = Signal()             # Поток завершил работу
    paused_changed = Signal(bool)   # [v3, 12.11.2026] Пауза включена (True) / снята (False) — после дочитки фразы

    def __init__(self, device_id: Optional[int], vosk_manager, sample_rate: int = 16000,
                 save_audio_path: Optional[str] = None, source: str = "mic"):
        super().__init__()
        # [v3.2, 18.11.2026] Ф1: источник звука — "mic" (микрофон), "system" (звук компьютера), "both" (оба в один)
        self.source = source if source in ("mic", "system", "both") else "mic"
        # [v3] Куда сохранить звук записи (.ogg, Opus); None — не сохранять.
        # После остановки здесь путь к файлу, если он записан
        self.save_audio_path = save_audio_path
        self.saved_audio_path: Optional[str] = None
        self._pcm: List[bytes] = []
        # Если device_id None или отрицательный (-1), передаем None в sounddevice для выбора системного микрофона по умолчанию
        self.device_id = None if (device_id is None or device_id < 0) else int(device_id)
        self.vosk_manager = vosk_manager
        self.sample_rate = sample_rate  # Желаемая частота (может быть скорректирована в run())
        self.actual_sample_rate = sample_rate  # Фактическая частота устройства
        self.audio_queue = queue.Queue()
        self.is_running = False
        self.stream: Optional[sd.RawInputStream] = None
        # [v3, 12.11.2026] Пауза внутри одной записи: звук не пишется и не распознаётся,
        # запись, текст и файл остаются одни: длинная диктовка с паузами — один файл
        self._pause_wanted = False
        self.paused = False

    def set_paused(self, paused: bool):
        """Просьба поставить или снять паузу; поток выполнит её в своём цикле."""
        self._pause_wanted = paused

    def stop(self):
        """
        Корректно останавливает запись и поток.
        """
        self.is_running = False

    def _audio_callback(self, indata, frames, time, status):
        """
        Callback-функция sounddevice, вызываемая в отдельном системном потоке при поступлении звука.
        """
        if status:
            logger.warning(f"Статус аудио-потока: {status}")
        self.audio_queue.put(bytes(indata))

    def _resample(self, data: bytes, from_rate: int) -> bytes:
        """
        Децимация PCM int16 с from_rate до TARGET_SAMPLE_RATE.
        Используется только если from_rate != TARGET_SAMPLE_RATE.
        """
        if from_rate == TARGET_SAMPLE_RATE:
            return data
        audio = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        # Кратная частота (32/48 кГц): усреднение блоков — заодно простой ФНЧ против наложения спектра
        if from_rate % TARGET_SAMPLE_RATE == 0:
            factor = from_rate // TARGET_SAMPLE_RATE
            usable = len(audio) - (len(audio) % factor)
            return audio[:usable].reshape(-1, factor).mean(axis=1).astype(np.int16).tobytes()
        # Коэффициент изменения количества самплов
        ratio = TARGET_SAMPLE_RATE / from_rate
        new_length = max(1, int(len(audio) * ratio))
        # Линейная интерполяция — быстро и достаточно для речи
        resampled = np.interp(
            np.linspace(0, len(audio) - 1, new_length),
            np.arange(len(audio)),
            audio
        ).astype(np.int16)
        return resampled.tobytes()

    def run(self):
        self.is_running = True
        
        # Получаем распознаватель Vosk (всегда 16 кГц — звук другой частоты ресемплируется ниже)
        rec = self.vosk_manager.get_recognizer(TARGET_SAMPLE_RATE)
        if not rec:
            self.error.emit("Модель распознавания не загружена. Выберите её: «Настройки → Распознавание».")
            self.recording_finished.emit()
            return

        # [v3] Тайминги слов нужны: по длине пауз ставятся точки, запятые и абзацы
        rec.SetWords(True)

        # [v3.2] Звук компьютера — отдельный приёмник; микрофон (если он есть) задаёт ход времени
        system = None
        if self.source in ("system", "both"):
            from core.system_audio import SystemAudioCapture
            system = SystemAudioCapture()
            try:
                system.start()
            except Exception as e:
                logger.error(f"Звук компьютера не открыт: {e}")
                system.stop()
                self.error.emit(f"Звук компьютера не удалось записать: {e}\nПроверьте, что динамики или наушники подключены.")
                self.recording_finished.emit()
                return

        # Пытаемся открыть аудиопоток — перебираем частоты до успеха
        stream_opened = self.source == "system"
        last_error = None
        for rate in ([] if stream_opened else FALLBACK_RATES):
            try:
                self.stream = sd.RawInputStream(
                    samplerate=rate,
                    blocksize=int(rate * 0.05),  # 50 мс буфер для любой частоты
                    device=self.device_id,
                    dtype='int16',
                    channels=1,
                    callback=self._audio_callback
                )
                self.actual_sample_rate = rate
                if rate != TARGET_SAMPLE_RATE:
                    logger.info(f"Устройство не поддерживает {TARGET_SAMPLE_RATE} Гц, использую {rate} Гц + ресемплинг")
                stream_opened = True
                break
            except Exception as e:
                last_error = e
                logger.warning(f"Частота {rate} Гц не поддерживается: {e}")

        if not stream_opened:
            logger.error(f"Не удалось открыть поток ни на одной частоте: {last_error}")
            if system:
                system.stop()
            self.error.emit(f"Ошибка аудио-входа: {last_error}\nПопробуйте выбрать другой микрофон.")
            self.recording_finished.emit()
            return

        block = int(TARGET_SAMPLE_RATE * 0.05)

        def next_block() -> Optional[bytes]:
            """Следующие 50 мс звука, 16 кГц, int16; None — пока нет."""
            if self.source == "system":
                if system.available_samples() < block:
                    time.sleep(0.02)
                    return None
                return np.clip(system.read(block), -32768, 32767).astype(np.int16).tobytes()
            try:
                data = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                return None
            # [v3] Ресемплинг до 16 кГц: в v2 метод был, но не вызывался —
            # при 44.1/48 кГц распознаватель получал звук не той частоты
            data = self._resample(data, self.actual_sample_rate)
            if system:
                mic = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                data = np.clip(mic + system.read(len(mic)), -32768, 32767).astype(np.int16).tobytes()
            return data

        # Запускаем поток захвата звука
        try:
            with (self.stream if self.stream else contextlib.nullcontext()):
                logger.info(f"Запись запущена: источник {self.source}, микрофон ID {self.device_id}.")
                
                while self.is_running:
                    data = next_block()
                    if data is None:
                        continue

                    # [v3, 12.11.2026] Пауза: дочитать начатую фразу, затем пропускать звук.
                    # Тайминги слов не сдвигаются: звук паузы не попадает ни в распознавание, ни в файл
                    if self._pause_wanted != self.paused:
                        if self._pause_wanted:
                            res = json.loads(rec.FinalResult())
                            text = res.get("text", "").strip()
                            if text:
                                self.final_words.emit(res.get("result", []))
                                self.final_chunk.emit(text)
                        self.paused = self._pause_wanted
                        self.paused_changed.emit(self.paused)
                    if self.paused:
                        continue

                    if self.save_audio_path:
                        self._pcm.append(data)

                    # Вычисляем громкость для визуализатора через логарифмическую шкалу децибел (dB),
                    # так как она идеально соответствует логарифмическому восприятию звука человеческим ухом
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    if len(audio_data) > 0:
                        # Вычисляем среднеквадратичное значение (RMS)
                        rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
                        if rms > 1.0:
                            # Переводим в децибелы (обычно диапазон RMS от 1 до 32767 дает от 0 до 90 дБ)
                            db = 20.0 * np.log10(rms)
                            # Масштабируем: порог тишины/шума 25дБ, порог максимального пика 75дБ
                            # Это дает превосходную чувствительность даже для тихих микрофонов!
                            volume = (db - 25.0) / 50.0
                            volume = min(1.0, max(0.0, volume))
                        else:
                            volume = 0.0
                        self.volume_changed.emit(volume)

                    # Распознавание Vosk
                    if rec.AcceptWaveform(data):
                        res = json.loads(rec.Result())
                        text = res.get("text", "").strip()
                        if text:
                            self.final_words.emit(res.get("result", []))
                            self.final_chunk.emit(text)
                    else:
                        partial = json.loads(rec.PartialResult())
                        partial_text = partial.get("partial", "").strip()
                        if partial_text:
                            self.partial_result.emit(partial_text)

                # Завершаем распознавание
                final_res = json.loads(rec.FinalResult())
                text = final_res.get("text", "").strip()
                if text:
                    self.final_words.emit(final_res.get("result", []))
                    self.final_chunk.emit(text)

        except Exception as e:
            logger.error(f"Ошибка в цикле записи/распознавания: {e}")
            self.error.emit(f"Произошла системная ошибка при записи: {e}")
        finally:
            if self.stream:
                self.stream.close()
                self.stream = None
            if system:
                system.stop()
            self._save_audio()

            # Очищаем очередь
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break

            logger.info("Запись с микрофона остановлена.")
            self.recording_finished.emit()

    def _save_audio(self):
        """[v3] Звук записи → Opus 24 кбит/с (~2 МБ на 10 мин) через ffmpeg; тайминги слов совпадают с файлом."""
        if not self.save_audio_path or not self._pcm:
            return
        pcm, self._pcm = b"".join(self._pcm), []
        if len(pcm) < TARGET_SAMPLE_RATE * 2:  # меньше секунды
            return
        try:
            os.makedirs(os.path.dirname(self.save_audio_path), exist_ok=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(TARGET_SAMPLE_RATE),
                            "-ac", "1", "-i", "-", "-c:a", "libopus", "-b:a", "24k", self.save_audio_path],
                           input=pcm, check=True, capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.saved_audio_path = self.save_audio_path
            logger.info(f"Звук записи сохранён: {self.save_audio_path}")
        except Exception as e:
            logger.error(f"Не удалось сохранить звук записи: {e}")
