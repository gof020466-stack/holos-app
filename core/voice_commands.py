import os
import logging
import winsound
from typing import List, Dict, Any
from PySide6.QtCore import QObject, Signal
from vosk import Model, KaldiRecognizer

from core.mic_recorder import MicTranscriptionWorker
from core.vosk_manager import DEFAULT_MODELS_PATH

logger = logging.getLogger("VoiceCommands")

# [v3] Команды слушает лёгкая модель (грузится за секунду, почти не нагружает процессор).
# Команда срабатывает, только если вся фраза между паузами точно равна команде.
# Грамматику из двух фраз не используем: на тесте 29.10.2026 «начальник записал»
# и «опять запись» распознавались как «начать запись»; без грамматики — ни одной ошибки
COMMAND_MODEL_ID = "vosk-model-small-ru-0.22"
START_PHRASE = "начать запись"
STOP_PHRASE = "стоп запись"
CONTINUE_PHRASE = "продолжить запись"  # снять паузу записи; без паузы — дописать в запись, выбранную в «Истории»
# [v3, 12.11.2026] Пауза внутри одной записи. Просто «пауза» не берём — слово звучит в обычной речи
PAUSE_PHRASE = "пауза запись"
PAUSE_VARIANTS = (PAUSE_PHRASE, "пауза записи", "паузу запись", "паузу записи")
DICTATE_PHRASE = "начать диктовку"     # как F8: текст — в активное окно (31.10.2026, F8 без рук)
DICTATE_VARIANTS = (DICTATE_PHRASE, "начать диктовка", "начать диктовки")
# [v3, 03.11.2026] «Ассистент» — первое слово фразы; остаток фразы (если сказан сразу) — текст для Claude
ASSISTANT_VARIANTS = ("ассистент", "ассистента", "ассистенту")


def split_wake_word(text: str):
    """
    «ассистент включи музыку» → «включи музыку»; «ассистент» → ""; другая фраза → None.
    """
    words = text.split()
    if words and words[0] in ASSISTANT_VARIANTS:
        return " ".join(words[1:])
    return None


def beep(start: bool):
    """Короткий сигнал: работа голосом идёт без взгляда на экран."""
    try:
        winsound.Beep(900, 75) if start else winsound.Beep(1200, 90)
    except Exception:
        pass


def strip_pause_command(words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """[v3, 12.11.2026] Убирает из конца слова команды «пауза запись» — основная модель слышит её тоже."""
    tail = [str(w.get("word", "")).lower() for w in words[-2:]]
    if len(tail) == 2 and tail[0].startswith("пауз") and tail[1].startswith("запис"):
        return words[:-2]
    if tail and tail[-1].startswith("пауз"):
        return words[:-1]
    return words


def strip_stop_command(words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Убирает из конца записи слова команды «стоп запись» — основная модель слышит её тоже.
    """
    tail = [str(w.get("word", "")).lower() for w in words[-2:]]
    if len(tail) == 2 and tail[0] == "стоп" and tail[1].startswith("запис"):
        return words[:-2]
    if tail and tail[-1] == "стоп":
        return words[:-1]
    return words


class _CommandSource:
    """Подставляется в MicTranscriptionWorker вместо VoskManager: распознаватель лёгкой модели."""
    def __init__(self, model: Model):
        self.model = model

    def get_recognizer(self, sample_rate: int) -> KaldiRecognizer:
        return KaldiRecognizer(self.model, sample_rate)


class VoiceCommandListener(QObject):
    """
    Фоновое прослушивание микрофона по умолчанию: сигналы на «начать запись» и «стоп запись».
    """
    start_requested = Signal()
    stop_requested = Signal()
    continue_requested = Signal()
    pause_requested = Signal()   # [v3, 12.11.2026] «пауза запись»
    dictate_requested = Signal()
    assistant_requested = Signal(str)  # остаток фразы после «Ассистент» ("" — ждать фразу)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = None
        self.worker = None

    def is_running(self) -> bool:
        return bool(self.worker and self.worker.isRunning())

    def start(self) -> bool:
        if self.is_running():
            return True
        if self.model is None:
            try:
                self.model = Model(os.path.join(DEFAULT_MODELS_PATH, COMMAND_MODEL_ID))
            except Exception as e:
                logger.error(f"Не удалось загрузить модель команд {COMMAND_MODEL_ID}: {e}")
                return False
        self.worker = MicTranscriptionWorker(None, _CommandSource(self.model))
        self.worker.final_chunk.connect(self._on_phrase)
        self.worker.error.connect(lambda e: logger.error(f"Прослушивание команд остановлено: {e}"))
        self.worker.start()
        logger.info("Голосовые команды включены.")
        return True

    def stop(self):
        if self.worker:
            self.worker.stop()
            self.worker.wait(2000)
            self.worker = None
            logger.info("Голосовые команды выключены.")

    def _on_phrase(self, text: str):
        tail = split_wake_word(text)
        if tail is not None:
            logger.info(f"Голосовая команда: ассистент [{tail}]")
            self.assistant_requested.emit(tail)
        elif text == START_PHRASE:
            logger.info("Голосовая команда: начать запись")
            self.start_requested.emit()
        elif text == STOP_PHRASE:
            logger.info("Голосовая команда: стоп запись")
            self.stop_requested.emit()
        elif text == CONTINUE_PHRASE:
            logger.info("Голосовая команда: продолжить запись")
            self.continue_requested.emit()
        elif text in PAUSE_VARIANTS:
            logger.info("Голосовая команда: пауза запись")
            self.pause_requested.emit()
        elif text in DICTATE_VARIANTS:
            logger.info("Голосовая команда: начать диктовку")
            self.dictate_requested.emit()
