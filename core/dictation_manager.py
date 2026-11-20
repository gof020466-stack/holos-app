import time
import ctypes
import logging
import winsound
from typing import Optional, List
from PySide6.QtCore import QObject, Signal, QThread, QTimer
from PySide6.QtGui import QGuiApplication
import keyboard

from core.mic_recorder import MicTranscriptionWorker
from core.punctuator import Punctuator
from core.db_manager import DBManager
from core.settings import AppSettings
from core.dictionary import apply_replacements
from core.voice_commands import strip_stop_command
from core.assistant_target import find_window, activate_window
from core.local_commands import try_local

logger = logging.getLogger("DictationManager")

user32 = ctypes.windll.user32

class DictationManager(QObject):
    """
    Глобальный менеджер диктовки по горячим клавишам для любого активного окна Windows.
    """
    # Сигналы для связи с GUI и оверлеем
    hotkey_triggered = Signal()
    dictation_started = Signal(str)           # (имя горячей клавиши)
    partial_text_updated = Signal(str)        # (живая фраза)
    final_chunk_received = Signal(str)        # (зафиксированный кусок фразы)
    volume_changed = Signal(float)            # (громкость для индикатора)
    dictation_finished = Signal(str, bool)    # (итоговый текст, вставлен ли в окно)
    error_occurred = Signal(str)
    assistant_sent = Signal(str, str)         # [v3] (фраза, куда ушла: «Claude» / «VOSK: музыка» / «буфер обмена»)

    def __init__(self, vosk_manager, parent=None):
        super().__init__(parent)
        self.vosk_manager = vosk_manager
        self.db = DBManager()

        # [v3] Настройки читаются из data/settings.ini и сохраняются при изменении
        self.current_hotkey = AppSettings.get("dictation/hotkey")
        self.is_active = AppSettings.get("dictation/enabled")  # Включена ли глобальная прослушка клавиши
        self.is_dictating = False       # Идет ли прямо сейчас запись речи

        # Настройки пользователя
        self.auto_insert = AppSettings.get("dictation/auto_insert")        # Вставлять ли через Ctrl+V в активное окно
        self.auto_punctuate = AppSettings.get("dictation/auto_punctuate")  # Применять ли пунктуацию и заглавные буквы
        self.sound_feedback = AppSettings.get("dictation/sound")           # Звуковой сигнал при старте/стопе
        self.restore_clipboard = AppSettings.get("dictation/restore_clipboard")  # Вернуть прежнее содержимое буфера
        self.new_paragraph = AppSettings.get("dictation/new_paragraph")    # Каждая диктовка — отдельный абзац

        self.target_hwnd = None         # Хэндл окна, в которое будет вставлен текст
        self.device_id = None           # ID устройства ввода (None = системный микрофон по умолчанию)
        self.worker: Optional[MicTranscriptionWorker] = None
        self.recorded_chunks: List[str] = []
        self.recorded_words: list = []

        # [v3, 03.11.2026] Режим «Ассистент»: фраза до паузы → окно Claude → Enter
        self.assistant_mode = False
        self._started_at = 0.0
        self._last_speech = 0.0
        self._last_partial = ""
        self._heard = False
        self._silence_timer = QTimer(self)
        self._silence_timer.setInterval(250)
        self._silence_timer.timeout.connect(self._check_assistant_silence)

        # Подключаем внутренний сигнал для безопасного перехода из потока keyboard в поток Qt
        self.hotkey_triggered.connect(self._handle_hotkey_on_qt_thread)
        
        # Регистрируем горячую клавишу
        if self.is_active:
            self._register_hotkey()

    def set_option(self, name: str, value: bool):
        """
        [v3] Меняет пользовательскую опцию и сохраняет её в настройках.
        """
        setattr(self, name, value)
        key = {"auto_insert": "dictation/auto_insert",
               "auto_punctuate": "dictation/auto_punctuate",
               "sound_feedback": "dictation/sound",
               "restore_clipboard": "dictation/restore_clipboard",
               "new_paragraph": "dictation/new_paragraph"}[name]
        AppSettings.set(key, value)

    def set_hotkey(self, new_hotkey: str) -> bool:
        """
        Переназначает горячую клавишу диктовки.
        """
        try:
            self._unregister_hotkey()
            self.current_hotkey = new_hotkey
            AppSettings.set("dictation/hotkey", new_hotkey)
            if self.is_active:
                self._register_hotkey()
            logger.info(f"Горячая клавиша диктовки изменена на: {new_hotkey}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при установке горячей клавиши {new_hotkey}: {e}")
            return False

    def set_enabled(self, enabled: bool):
        """
        Включает или выключает перехват глобальной горячей клавиши.
        """
        if enabled == self.is_active and enabled:
            return
        self.is_active = enabled
        AppSettings.set("dictation/enabled", enabled)
        if enabled:
            self._register_hotkey()
        else:
            if self.is_dictating:
                self.stop_dictation()
            self._unregister_hotkey()
        logger.info(f"Статус глобальной диктовки изменен: {enabled}")

    def shutdown(self):
        """
        [v3] Снимает перехват клавиши при выходе, не меняя сохранённую настройку «включено».
        """
        if self.is_dictating:
            self.stop_dictation()
        if self.worker and self.worker.isRunning():
            self.worker.wait(2000)
        self._unregister_hotkey()

    def _register_hotkey(self):
        try:
            # [v3] suppress=True: клавиша не уходит в активное приложение
            # (в v2 F8 доходил, например, до Excel и включал режим выделения)
            keyboard.add_hotkey(self.current_hotkey.lower(), self._on_keyboard_event, suppress=True)
            logger.info(f"Глобальная горячая клавиша [{self.current_hotkey}] успешно активирована.")
        except Exception as e:
            logger.error(f"Не удалось зарегистрировать горячую клавишу [{self.current_hotkey}]: {e}")

    def _unregister_hotkey(self):
        try:
            keyboard.remove_hotkey(self.current_hotkey.lower())
        except Exception:
            pass

    def _on_keyboard_event(self):
        """
        Вызывается в фоновом потоке перехвата keyboard.
        Перенаправляет вызов в поток Qt через сигнал.
        """
        if self.is_active:
            self.hotkey_triggered.emit()

    def _handle_hotkey_on_qt_thread(self):
        """
        Обработка нажатия горячей клавиши в основном GUI-потоке Qt.
        """
        if self.is_dictating:
            self.stop_dictation()
        elif self.worker and self.worker.isRunning():
            # [v3] Предыдущая запись ещё дописывает хвост — новое нажатие игнорируем,
            # иначе старый поток отдаст текст в буфер новой диктовки
            logger.info("Предыдущая диктовка ещё завершается, нажатие пропущено.")
        else:
            self.start_dictation()

    def start_dictation(self, assistant: bool = False):
        """
        Запускает процесс диктовки с захватом текущего активного окна.
        [v3] assistant=True — текст уйдёт в окно Claude, запись остановится сама по паузе.
        """
        if not self.vosk_manager.active_model:
            logger.warning("Попытка запуска диктовки без активной модели Vosk.")
            self.error_occurred.emit("Модель Vosk не загружена! Откройте вкладку 'Модели' и загрузите языковую модель.")
            return

        # 1. Запоминаем текущее активное окно Windows (куда пользователь хочет вставить текст)
        self.target_hwnd = user32.GetForegroundWindow()
        self.is_dictating = True
        self.recorded_chunks = []
        self.recorded_words = []
        self.assistant_mode = assistant
        if assistant:
            self._started_at = self._last_speech = time.monotonic()
            self._last_partial = ""
            self._heard = False
            self._silence_timer.start()

        # 2. Звуковой сигнал подтверждения
        if self.sound_feedback:
            try:
                winsound.Beep(900, 75)
            except Exception:
                pass

        # 3. Уведомляем GUI и оверлей
        self.dictation_started.emit("Ассистент" if assistant else self.current_hotkey)

        # 4. Запускаем фоновый захват микрофона
        # self.device_id (None = системный микрофон по умолчанию или выбранный пользователем ID)
        self.worker = MicTranscriptionWorker(device_id=self.device_id, vosk_manager=self.vosk_manager)
        self.worker.partial_result.connect(self._on_partial)
        self.worker.final_words.connect(self._on_final_words)
        self.worker.final_chunk.connect(self._on_final_chunk)
        self.worker.volume_changed.connect(self.volume_changed.emit)
        self.worker.error.connect(self._on_worker_error)
        self.worker.recording_finished.connect(self._on_worker_finished)
        self.worker.start()

        logger.info(f"Диктовка запущена. Целевое окно HWND: {self.target_hwnd}")

    def stop_dictation(self):
        """
        Останавливает диктовку и инициирует вставку текста.
        """
        if not self.is_dictating:
            return

        self.is_dictating = False
        self._silence_timer.stop()

        # Звуковой сигнал завершения
        if self.sound_feedback:
            try:
                winsound.Beep(1200, 90)
            except Exception:
                pass

        if self.worker:
            self.worker.stop()

    def _get_accumulated_text(self, partial: str = "") -> str:
        chunks_str = " ".join(self.recorded_chunks)
        if partial and partial.strip():
            full = (chunks_str + " " + partial).strip()
        else:
            full = chunks_str.strip()
        if full:
            full = full[0].upper() + full[1:]
        return full

    def _on_partial(self, text: str):
        if text.strip() and text != self._last_partial:
            self._mark_speech()
        self._last_partial = text
        full = self._get_accumulated_text(partial=text)
        self.partial_text_updated.emit(full)

    def _on_final_words(self, words: list):
        self.recorded_words.extend(words)

    def _mark_speech(self):
        self._heard = True
        self._last_speech = time.monotonic()

    def _check_assistant_silence(self):
        """
        [v3] Режим «Ассистент»: пауза после речи — конец фразы; нет речи — отмена; предел длины.
        Речь — когда меняется живой текст распознавания.
        """
        if not (self.is_dictating and self.assistant_mode):
            self._silence_timer.stop()
            return
        now = time.monotonic()
        if now - self._started_at > AppSettings.get("assistant/max"):
            logger.info("Ассистент: предел длины фразы.")
            self.stop_dictation()
        elif self._heard and now - self._last_speech > AppSettings.get("assistant/silence"):
            self.stop_dictation()
        elif not self._heard and now - self._started_at > AppSettings.get("assistant/no_speech"):
            logger.info("Ассистент: речи нет — отмена.")
            self.stop_dictation()

    def _on_final_chunk(self, chunk: str):
        if chunk.strip():
            self._mark_speech()
        self.recorded_chunks.append(chunk)
        full = self._get_accumulated_text()
        self.final_chunk_received.emit(full)

    def _on_worker_error(self, err: str):
        self.is_dictating = False
        self.assistant_mode = False
        self._silence_timer.stop()
        self.error_occurred.emit(err)

    def _on_worker_finished(self):
        """
        Вызывается после полной остановки потока захвата звука.
        Форматирует текст, сохраняет в историю и вставляет в активное окно.
        """
        assistant = self.assistant_mode
        self.assistant_mode = False
        # [v3] Остановка голосом: основная модель тоже слышит «стоп запись» — убираем
        if self.recorded_words:
            self.recorded_words = strip_stop_command(self.recorded_words)
            if not self.recorded_words:
                self.recorded_chunks = []
        if not self.recorded_chunks:
            self.dictation_finished.emit("", False)
            return

        # 1. Форматирование текста (автопунктуация)
        # [v3] Знаки — по паузам между словами; без абзацев: текст вставляется одним куском
        if self.auto_punctuate and self.recorded_words:
            pauses = dict(AppSettings.pauses(), paragraph_pause=None)
            final_text = Punctuator.punctuate_words_with_timing(self.recorded_words, **pauses)
        elif self.auto_punctuate:
            final_text = Punctuator.punctuate_plain_text(chunks=self.recorded_chunks)
        else:
            final_text = " ".join(self.recorded_chunks).strip()

        if not final_text:
            self.dictation_finished.emit("", False)
            return
        final_text = apply_replacements(final_text)

        if assistant:
            self.dictation_finished.emit(final_text, self.send_to_assistant(final_text))
            return

        # 2. Сохраняем в постоянную базу данных SQLite
        title = f"Диктовка [{self.current_hotkey}]"
        self.db.add_item(title, final_text, [], f"Быстрая диктовка ({self.current_hotkey})")
        logger.info(f"Диктовка завершена. Текст: '{final_text}' сохранен в базу данных.")

        # 3. Вставка в активное приложение пользователя
        pasted = False
        if self.auto_insert and self.target_hwnd:
            # [v3] Пустая строка после текста: в Obsidian (Markdown) следующая диктовка — новый абзац
            pasted = self._paste_text_to_target_window(final_text + ("\n\n" if self.new_paragraph else ""))

        self.dictation_finished.emit(final_text, pasted)

    def send_to_assistant(self, text: str) -> bool:
        """
        [v3, 03.11.2026] Фраза для Claude: в историю, в поле ввода окна Claude, затем Enter.
        Окна нет — текст остаётся в буфере обмена.
        """
        text = text.strip()
        if not text:
            return False
        if try_local(text):
            self.assistant_sent.emit(text, "VOSK: музыка")
            return True
        text = text[0].upper() + text[1:]
        self.db.add_item("Ассистент", text, [], "Голосом для Claude")
        hwnd = find_window(AppSettings.get("assistant/window_title"), AppSettings.get("assistant/window_exe"))
        if not hwnd:
            QGuiApplication.clipboard().setText(text)
            self.assistant_sent.emit(text, "буфер обмена (окна Claude нет)")
            self.error_occurred.emit("Окно Claude не найдено — текст в буфере обмена.")
            return False
        self.assistant_sent.emit(text, "Claude")
        self.target_hwnd = hwnd
        activate_window(hwnd)
        if not self._paste_text_to_target_window(text):
            return False
        if AppSettings.get("assistant/send_enter"):
            time.sleep(0.15)
            keyboard.send("enter")
        logger.info(f"Ассистент: отправлено в Claude: '{text}'")
        return True

    def _paste_text_to_target_window(self, text: str) -> bool:
        """
        Восстанавливает фокус на целевом окне пользователя и вставляет текст через буфер обмена.
        """
        try:
            # 1. Копируем в буфер обмена Qt (прежний текст запоминаем, чтобы вернуть)
            clipboard = QGuiApplication.clipboard()
            previous = clipboard.text() if self.restore_clipboard else None
            clipboard.setText(text)

            # 2. Активируем окно пользователя, где был фокус до диктовки
            if self.target_hwnd and user32.IsWindow(self.target_hwnd):
                user32.SetForegroundWindow(self.target_hwnd)
                # Даем Windows немного времени переключить фокус
                time.sleep(0.06)

            # 3. Симулируем нажатие Ctrl+V
            keyboard.send("ctrl+v")
            logger.info("Текст успешно вставлен в активное окно через Ctrl+V.")

            # 4. [v3] Возвращаем пользователю прежний буфер — после того, как приложение заберёт вставку
            if previous:
                QTimer.singleShot(400, lambda: clipboard.setText(previous))
            return True
        except Exception as e:
            logger.error(f"Не удалось вставить текст в окно: {e}")
            return False
