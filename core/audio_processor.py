import os
import subprocess
import json
import logging
from typing import Optional, List, Dict, Any
import numpy as np
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger("AudioProcessor")

class FileTranscriptionWorker(QThread):
    # Сигналы для общения с GUI
    progress = Signal(int, float, float)  # (процент, текущие секунды, всего секунд)
    partial_result = Signal(str)         # (частичный текст)
    final_chunk = Signal(str)            # (фрагмент распознанного текста)
    error = Signal(str)                  # (сообщение об ошибке)
    transcription_finished = Signal(str, list)         # (полный текст, список слов с таймингами)
    status = Signal(str)                 # [v3] этап работы для строки статуса

    def __init__(self, file_path: str, vosk_manager, sample_rate: int = 16000, num_speakers: Optional[int] = None):
        super().__init__()
        self.file_path = file_path
        self.vosk_manager = vosk_manager
        self.sample_rate = sample_rate
        self.is_cancelled = False
        # [v3] Диаризация: None — не разделять, 0 — определить число говорящих самому, N — говорящих N
        self.num_speakers = num_speakers

    def cancel(self):
        self.is_cancelled = True

    def get_duration(self) -> float:
        """
        Использует ffprobe для получения длительности аудиофайла в секундах.
        """
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                self.file_path
            ]
            # Запускаем ffprobe (скрываем окно на Windows)
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0 # SW_HIDE

            result = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True, 
                startupinfo=startupinfo,
                check=True
            )
            duration_str = result.stdout.strip()
            return float(duration_str)
        except Exception as e:
            logger.error(f"Не удалось получить длительность аудиофайла через ffprobe: {e}")
            return 0.0

    def run(self):
        if not os.path.exists(self.file_path):
            self.error.emit(f"Файл не найден: {self.file_path}")
            return

        # Получаем длительность для отслеживания прогресса
        total_duration = self.get_duration()
        if total_duration == 0.0:
            logger.warning("Длительность файла неизвестна или равна 0. Использование прогресс-бара будет ограничено.")

        # Получаем распознаватель из VoskManager
        # Включаем вывод слов с таймингами
        rec = self.vosk_manager.get_recognizer(self.sample_rate)
        if not rec:
            self.error.emit("Модель Vosk не загружена. Зайдите во вкладку 'Модели' и выберите модель.")
            return

        rec.SetWords(True)  # Позволяет получать тайминги слов

        # Команда FFmpeg для декодирования аудио в сырой PCM 16kHz mono 16-bit
        # '-' в конце указывает на вывод в stdout
        ffmpeg_cmd = [
            "ffmpeg",
            "-loglevel", "quiet",
            "-i", self.file_path,
            "-ar", str(self.sample_rate),
            "-ac", "1",
            "-f", "s16le",
            "-"
        ]

        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0 # SW_HIDE

            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo
            )
        except Exception as e:
            self.error.emit(f"Не удалось запустить FFmpeg. Убедитесь, что он установлен в системе.\nДетали: {e}")
            return

        # 1 sample = 2 bytes (16-bit)
        # 16000 samples per second = 32000 bytes per second
        bytes_per_sec = self.sample_rate * 2
        chunk_size = 4000  # размер порции чтения
        total_bytes_read = 0
        
        full_text_list = []
        words_list = []
        pcm_chunks = []  # [v3] весь звук — для диаризации

        logger.info(f"Начало транскрибации файла: {self.file_path}")

        try:
            while True:
                if self.is_cancelled:
                    process.terminate()
                    self.error.emit("Транскрибация отменена пользователем.")
                    return

                data = process.stdout.read(chunk_size)
                if len(data) == 0:
                    break

                total_bytes_read += len(data)
                if self.num_speakers is not None:
                    pcm_chunks.append(data)

                # Рассчитываем текущее время в секундах и прогресс
                current_time = total_bytes_read / bytes_per_sec
                if total_duration > 0.0:
                    prog_percent = int((current_time / total_duration) * 100)
                    prog_percent = min(99, max(0, prog_percent)) # 100% будет при завершении
                    self.progress.emit(prog_percent, current_time, total_duration)
                else:
                    self.progress.emit(0, current_time, 0.0)

                # Подаем байты в распознаватель Vosk
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    text = res.get("text", "").strip()
                    if text:
                        full_text_list.append(text)
                        self.final_chunk.emit(text)
                        
                        # Сохраняем тайминги слов
                        if "result" in res:
                            words_list.extend(res["result"])
                else:
                    partial = json.loads(rec.PartialResult())
                    partial_text = partial.get("partial", "").strip()
                    if partial_text:
                        self.partial_result.emit(partial_text)

            # Получаем финальный результат после окончания потока
            final_res = json.loads(rec.FinalResult())
            text = final_res.get("text", "").strip()
            if text:
                full_text_list.append(text)
                self.final_chunk.emit(text)
                if "result" in final_res:
                    words_list.extend(final_res["result"])

            full_text = " ".join(full_text_list).strip()
            if self.num_speakers is not None and words_list and pcm_chunks:
                self.status.emit("Разделяю по говорящим... (≈ 1/5 длительности записи)")
                try:
                    from core import diarizer
                    pcm = np.frombuffer(b"".join(pcm_chunks), dtype=np.int16)
                    diarizer.label_words(words_list, diarizer.diarize(pcm, self.num_speakers))
                except Exception as e:
                    logger.error(f"Диаризация не удалась: {e}")
            self.progress.emit(100, total_duration if total_duration > 0 else current_time, total_duration)
            self.transcription_finished.emit(full_text, words_list)

        except Exception as e:
            logger.error(f"Ошибка во время распознавания файла: {e}")
            self.error.emit(f"Ошибка при распознавании: {e}")
        finally:
            if process.poll() is None:
                process.terminate()
