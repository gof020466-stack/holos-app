import os
import html
import logging
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QComboBox, QFrame, QTextEdit,
                             QMessageBox, QCheckBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
import qtawesome as qta
from core.mic_recorder import get_input_devices, MicTranscriptionWorker
from core.punctuator import Punctuator
from core.settings import AppSettings
from core.dictionary import apply_replacements
from core.voice_commands import (VoiceCommandListener, strip_stop_command, strip_pause_command, beep,
                                 START_PHRASE, STOP_PHRASE, CONTINUE_PHRASE, DICTATE_PHRASE, PAUSE_PHRASE)
from gui.visualizer import VolumeVisualizer
from gui.recording_watch import RecordingWatch
from gui.widgets import ToggleSwitch

logger = logging.getLogger("MicTab")

class MicTab(QWidget):
    # Сигнал для передачи распознанного текста в историю
    # (текст, слова с таймингами, метка источника, путь к звуку, ID черновика в Истории или 0)
    transcription_completed = Signal(str, list, str, str, int)
    show_requested = Signal()  # [v3] Голосовой старт: показать окно на этой вкладке
    recording_changed = Signal(bool)  # [v3.2, Д1] кнопка «Начать запись» в меню меняет вид вместе с этой

    def __init__(self, vosk_manager, parent=None):
        super().__init__(parent)
        self.vosk_manager = vosk_manager
        self.worker = None
        self.recorded_chunks = []
        self.recorded_words = []
        self._last_partial = None
        self._error_occurred = False
        self.busy_elsewhere = lambda: False  # [v3] Главное окно подставляет проверку «дописывания» в Истории
        # [v3, 12.11.2026] Черновик на паузе: главное окно подставляет сохранение в Историю
        # save_draft(item_id или 0, заголовок, текст, слова) → item_id
        self.save_draft = None
        self.draft_id = 0
        self.draft_title = ""
        self.recording_source = "mic"
        self.setup_ui()
        self.refresh_devices()
        # [v3, 11.11.2026] Таймер, уровень звука и предупреждение «звук есть, текста нет»
        self.watch = RecordingWatch(self)
        self.watch.status_changed.connect(self.on_watch_status)

        self.voice_listener = VoiceCommandListener(self)
        self.voice_listener.start_requested.connect(self.on_voice_start)
        self.voice_listener.stop_requested.connect(self.on_voice_stop)
        self.voice_listener.pause_requested.connect(self.on_voice_pause)
        self.voice_listener.continue_requested.connect(self.on_voice_continue)
        if self.chk_voice.isChecked():
            self.voice_listener.start()

    def showEvent(self, event):
        """Очищаем поле и буфер при каждом открытии вкладки."""
        super().showEvent(event)
        if not (self.worker and self.worker.isRunning()):
            self.txt_output.clear()
            self.recorded_chunks = []
            self.recorded_words = []

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # [v3.2, 18.11.2026] Подсказка под выбором источника (заголовок «Новая запись» — у страницы)
        self.lbl_hint = QLabel("")
        self.lbl_hint.setProperty("class", "SubtitleLabel")
        self.lbl_hint.setWordWrap(True)
        layout.addWidget(self.lbl_hint)

        # Панель выбора микрофона (скрыта, когда пишется только звук компьютера)
        self.device_row = QWidget()
        device_layout = QHBoxLayout(self.device_row)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_layout.setSpacing(10)

        lbl_device = QLabel("Микрофон:")
        lbl_device.setStyleSheet("font-weight: 500; font-size: 13px;")

        self.cb_devices = QComboBox()
        self.cb_devices.setStyleSheet("QComboBox { min-width: 250px; }")

        self.btn_refresh_devices = QPushButton()
        self.btn_refresh_devices.setFixedSize(34, 34)
        self.btn_refresh_devices.setIcon(qta.icon("fa5s.sync-alt", color="#e2e2e5"))
        self.btn_refresh_devices.setProperty("class", "SecondaryButton")
        self.btn_refresh_devices.setToolTip("Обновить список микрофонов")
        self.btn_refresh_devices.clicked.connect(self.refresh_devices)

        device_layout.addWidget(lbl_device)
        device_layout.addWidget(self.cb_devices, 1)
        device_layout.addWidget(self.btn_refresh_devices)
        layout.addWidget(self.device_row)

        # [v3.2] Ф1: чей звук пишется, кроме микрофона
        self.lbl_speaker = QLabel("")
        self.lbl_speaker.setStyleSheet("font-size: 13px;")
        self.lbl_speaker.setWordWrap(True)
        layout.addWidget(self.lbl_speaker)

        # [v3.2, Д8] Состояние и уровень звука — узкой строкой у кнопки «Запись» (было — карточка ~20 % окна)
        self.lbl_status = QLabel("Ожидание запуска записи...")
        self.lbl_status.setObjectName("MicStatusLabel")
        self.visualizer = VolumeVisualizer(num_bars=18)
        self.visualizer.setFixedSize(150, 30)

        # Окно вывода распознаваемого текста
        text_layout = QVBoxLayout()
        text_layout.setSpacing(5)
        
        text_label = QLabel("Распознанный текст:")
        text_label.setProperty("class", "HeaderLabel")
        
        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setPlaceholderText("Здесь будет появляться распознанный текст по мере вашей речи...")
        self.txt_output.setStyleSheet("QTextEdit { font-size: 14px; line-height: 20px; }")
        
        text_layout.addWidget(text_label)
        text_layout.addWidget(self.txt_output)
        layout.addLayout(text_layout, 1)

        # Кнопки управления записью
        buttons_layout = QHBoxLayout()

        # [v3.2, Д4] Переключатели — в «Настройки → Запись» (здесь подписи обрезались по ширине окна)
        self.chk_punctuation = ToggleSwitch()
        self.chk_punctuation.setChecked(AppSettings.get("mic/punctuation"))
        self.chk_punctuation.toggled.connect(lambda v: AppSettings.set("mic/punctuation", v))

        self.chk_voice = ToggleSwitch()
        self.chk_voice.setToolTip(f"«{PAUSE_PHRASE}» — пауза; «{CONTINUE_PHRASE}» — дальше, в ту же запись\n"
                                  f"«{CONTINUE_PHRASE}» без паузы — дописать голосом в запись, выбранную в Истории\n"
                                  f"«{DICTATE_PHRASE}» — текст в активное окно, как F8\n"
                                  "«Ассистент, …» — фраза в окно Claude и отправка\n"
                                  "Перед командой и после неё — пауза")
        self.chk_voice.setChecked(AppSettings.get("voice/commands_enabled"))
        self.chk_voice.toggled.connect(self.on_voice_toggled)

        self.btn_record = QPushButton("Начать запись")
        self.btn_record.setObjectName("RecordButton")
        self.btn_record.setProperty("class", "PrimaryButton")
        self.btn_record.setProperty("recording", False)
        self.btn_record.setIcon(qta.icon("fa5s.microphone", color="#ffffff"))
        self.btn_record.clicked.connect(self.toggle_recording)

        # [v3, 12.11.2026] Пауза внутри одной записи (запись и файл — одни)
        self.btn_pause = QPushButton("Пауза")
        self.btn_pause.setProperty("class", "SecondaryButton")
        self.btn_pause.setIcon(qta.icon("fa5s.pause", color="#e2e2e5"))
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self.toggle_pause)

        buttons_layout.addWidget(self.lbl_status, 1)
        buttons_layout.addWidget(self.visualizer)
        buttons_layout.addWidget(self.btn_pause)
        buttons_layout.addWidget(self.btn_record)

        layout.addLayout(buttons_layout)
        self.set_source(AppSettings.get("record/source"))

    # -----------------------------------------------------------------
    # [v3.2, 18.11.2026] Ф1: источник звука — микрофон, звук компьютера или оба
    # -----------------------------------------------------------------
    SOURCE_NAMES = {"mic": "Запись с микрофона", "system": "Звук компьютера", "both": "Звук компьютера и микрофон"}
    SOURCE_HINTS = {
        "mic": "Ваш голос — в текст, на этом компьютере, без интернета",
        "system": "То, что звучит в динамиках или наушниках: ролик, вебинар, голос собеседника",
        "both": "Созвон: собеседники и вы — в одну запись. Потом «Говорящие» разделят текст по голосам",
    }

    def set_source(self, source: str):
        if source not in self.SOURCE_NAMES:
            source = "mic"
        if self.worker and self.worker.isRunning():
            return
        self.source = source
        AppSettings.set("record/source", source)
        self.lbl_hint.setText(self.SOURCE_HINTS[source])
        self.device_row.setVisible(source != "system")
        if source == "mic":
            self.lbl_speaker.setVisible(False)
        else:
            from core import system_audio
            name = system_audio.speaker_name() if system_audio.available() else ""
            self.lbl_speaker.setText(f"Звук компьютера: {name}" if name
                                     else "Звук компьютера недоступен: устройство вывода не найдено")
            self.lbl_speaker.setVisible(True)
        self.btn_record.setEnabled(source == "system" or self.cb_devices.currentData() not in (None, -1))

    def refresh_devices(self):
        """
        Обновляет список доступных аудиовходов.
        """
        self.cb_devices.clear()
        devices = get_input_devices()

        if not devices:
            self.cb_devices.addItem("Микрофоны не найдены", -1)
            self.btn_record.setEnabled(getattr(self, "source", "mic") == "system")
            return

        self.btn_record.setEnabled(True)
        
        for dev in devices:
            default_text = " (по умолчанию)" if dev["is_default"] else ""
            self.cb_devices.addItem(f"{dev['name']}{default_text}", dev["id"])
            
            # Если это устройство по умолчанию, выбираем его
            if dev["is_default"]:
                self.cb_devices.setCurrentIndex(self.cb_devices.count() - 1)

    def toggle_recording(self):
        """
        Переключает состояние записи (Пуск/Стоп).
        """
        if self.worker and self.worker.isRunning():
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if not self.vosk_manager.active_model:
            QMessageBox.warning(
                self, "Модель не выбрана", 
                "Модель распознавания ещё не загружена.\nВыберите язык: «Настройки → Распознавание»."
            )
            return

        device_id = self.cb_devices.currentData()
        if device_id == -1 and self.source != "system":
            QMessageBox.warning(self, "Ошибка", "Устройство записи не найдено.")
            return
        self.recording_source = self.source

        self.recorded_chunks = []
        self.recorded_words = []
        self._last_partial = None
        self._error_occurred = False
        self.draft_id = 0
        self.draft_title = f"[{datetime.now().strftime('%H:%M:%S')}] {self.SOURCE_NAMES[self.source]}"
        self.txt_output.clear()

        # Меняем дизайн кнопки на активную запись (красная/пурпурная)
        self.btn_record.setText("Стоп запись")  # как голосовая команда (31.10.2026)
        self.btn_record.setProperty("recording", True)
        self.btn_record.style().unpolish(self.btn_record)
        self.btn_record.style().polish(self.btn_record)
        self.btn_record.setIcon(qta.icon("fa5s.stop", color="#ffffff"))
        
        self.lbl_status.setText("Идёт запись...")
        self.lbl_status.setStyleSheet("color: #ef4444; font-size: 14px; font-weight: 600;")

        self.cb_devices.setEnabled(False)
        self.btn_refresh_devices.setEnabled(False)
        self.recording_changed.emit(True)

        # Запускаем фоновую запись
        # Семплирование по умолчанию 16000 Гц
        audio_path = None
        if AppSettings.get("mic/save_audio"):
            audio_path = os.path.join(AppSettings.get("mic/audio_dir"),
                                      datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".ogg")
        self.worker = MicTranscriptionWorker(device_id, self.vosk_manager, save_audio_path=audio_path,
                                             source=self.source)

        # Подключаем сигналы
        self.worker.partial_result.connect(self.on_partial_result)
        self.worker.final_words.connect(self.on_final_words)
        self.worker.final_chunk.connect(self.on_final_chunk)
        self.worker.volume_changed.connect(self.visualizer.set_volume)
        self.worker.error.connect(self.on_error)
        self.worker.recording_finished.connect(self.on_finished)
        self.worker.paused_changed.connect(self.on_paused_changed)
        self.watch.attach(self.worker)

        self.worker.start()
        self.btn_pause.setEnabled(True)

    # -----------------------------------------------------------------
    # [v3, 12.11.2026] Пауза: одна длинная диктовка — одна запись и один файл
    # -----------------------------------------------------------------
    def is_paused(self) -> bool:
        return bool(self.worker and self.worker.isRunning() and self.worker._pause_wanted)

    def toggle_pause(self):
        if not (self.worker and self.worker.isRunning()):
            return
        self.worker.set_paused(not self.worker._pause_wanted)

    def on_voice_pause(self):
        if self.worker and self.worker.isRunning() and not self.worker._pause_wanted:
            beep(False)
            self.worker.set_paused(True)

    def on_voice_continue(self):
        if self.is_paused():
            beep(True)
            self.worker.set_paused(False)

    def on_paused_changed(self, paused: bool):
        self.watch.set_paused(paused)
        self.btn_pause.setText("Продолжить" if paused else "Пауза")
        self.btn_pause.setIcon(qta.icon("fa5s.play" if paused else "fa5s.pause", color="#e2e2e5"))
        if paused:
            # Слова команды «пауза запись» основная модель тоже слышит — убрать
            self.recorded_words = strip_pause_command(self.recorded_words)
            self.render_live()
            self._save_draft()

    def _final_text(self, words: list) -> str:
        if words:
            if self.chk_punctuation.isChecked():
                return Punctuator.punctuate_words_with_timing(words, **AppSettings.pauses())
            return " ".join(str(w.get("word", "")) for w in words)
        if self.recorded_chunks and not self.recorded_words:
            return " ".join(self.recorded_chunks).strip()
        return ""

    def _save_draft(self):
        """На паузе текст сразу уходит в Историю: при сбое программы он не пропадёт."""
        if not self.save_draft:
            return
        text = self._final_text(self.recorded_words)
        if not text:
            return
        try:
            self.draft_id = self.save_draft(self.draft_id, self.draft_title,
                                            apply_replacements(text), self.recorded_words) or self.draft_id
        except Exception as e:
            logger.error(f"Черновик на паузе не сохранён: {e}")

    def on_watch_status(self, text: str, warning: bool):
        self.lbl_status.setText(text)
        self.lbl_status.setStyleSheet("font-size: 14px; font-weight: 600; color: "
                                      + ("#f59e0b;" if warning else "#ef4444;"))

    def stop_recording(self):
        if self.worker:
            self.watch.detach()
            self.lbl_status.setText("Остановка записи... Обработка последних фраз")
            self.worker.stop()

    def on_partial_result(self, partial_text: str):
        # [v3] Текущая фраза видна сразу в окне текста (серым), а не только в строке статуса
        if partial_text != self._last_partial:
            self._last_partial = partial_text
            self.render_live(partial_text)

    def on_final_words(self, words: list):
        self.recorded_words.extend(words)

    def on_final_chunk(self, final_text: str):
        self.recorded_chunks.append(final_text)
        self._last_partial = None
        self.render_live()

    def render_live(self, partial: str = ""):
        """
        [v3] Живой текст: одна диктовка — один абзац; новый абзац только после длинной паузы.
        В v3.0 каждая пауза давала новую строку (append на каждый блок Vosk).
        """
        paragraph_pause = AppSettings.get("punct/paragraph_pause")
        paragraphs = [[]]
        prev_end = None
        for w in self.recorded_words:
            if prev_end is not None and float(w.get("start", 0)) - prev_end >= paragraph_pause:
                paragraphs.append([])
            paragraphs[-1].append(str(w.get("word", "")))
            prev_end = float(w.get("end", 0))
        parts = [html.escape(" ".join(p)) for p in paragraphs if p]
        body = "<br><br>".join(parts)
        if partial:
            body += (" " if parts else "") + f'<span style="color:#8b8b95;">{html.escape(partial)}</span>'
        self.txt_output.setHtml(body)
        self.txt_output.moveCursor(QTextCursor.End)
        self.txt_output.ensureCursorVisible()

    # -----------------------------------------------------------------
    # [v3] Голосовые команды
    # -----------------------------------------------------------------
    def on_voice_toggled(self, checked: bool):
        AppSettings.set("voice/commands_enabled", checked)
        if checked:
            if not self.voice_listener.start():
                QMessageBox.warning(self, "Голосовые команды",
                                    "Не удалось загрузить лёгкую русскую модель для команд.")
                self.chk_voice.setChecked(False)
        else:
            self.voice_listener.stop()

    def on_voice_start(self):
        if (self.worker and self.worker.isRunning()) or self.busy_elsewhere():
            return
        self.show_requested.emit()
        self.start_recording()
        if self.worker:
            beep(True)

    def on_voice_stop(self):
        if self.worker and self.worker.isRunning():
            beep(False)
            self.stop_recording()

    def shutdown(self):
        """Останавливает прослушивание команд и запись при выходе из программы."""
        self.voice_listener.stop()
        if self.worker:
            self.worker.stop()
            self.worker.wait(2000)

    def on_error(self, err_msg: str):
        self._error_occurred = True
        QMessageBox.critical(self, "Ошибка аудио-записи", err_msg)
        self.reset_ui()

    def on_finished(self):
        if self._error_occurred:
            self._error_occurred = False
            return
        audio_path = self.worker.saved_audio_path if self.worker else None
        self.reset_ui()

        # [v3] Без всплывающих окон: их пришлось бы закрывать руками, а запись идёт и голосом
        words = strip_stop_command(self.recorded_words)
        final_text = self._final_text(words)

        if final_text:
            # Передаем записанный текст во вкладку истории
            # [v3] Слова с таймингами и звук — для плеера-караоке в «Истории»
            # [v3, 12.11.2026] Была пауза — обновляется её черновик, новой записи нет
            self.transcription_completed.emit(apply_replacements(final_text), words or [],
                                              self.SOURCE_NAMES[self.recording_source], audio_path or "",
                                              self.draft_id)
        else:
            self.lbl_status.setText("Запись завершена, но не было распознано ни одного слова.")

    def reset_ui(self):
        self.watch.detach()
        self.btn_pause.setEnabled(False)
        self.btn_pause.setText("Пауза")
        self.btn_pause.setIcon(qta.icon("fa5s.pause", color="#e2e2e5"))
        self.btn_record.setText("Начать запись")
        self.btn_record.setProperty("recording", False)
        self.btn_record.style().unpolish(self.btn_record)
        self.btn_record.style().polish(self.btn_record)
        self.btn_record.setIcon(qta.icon("fa5s.microphone", color="#ffffff"))
        
        self.lbl_status.setText("Ожидание запуска записи...")
        self.lbl_status.setStyleSheet("")
        
        self.cb_devices.setEnabled(True)
        self.btn_refresh_devices.setEnabled(True)
        self.visualizer.set_volume(0.0)
        self.worker = None
        self.recording_changed.emit(False)
