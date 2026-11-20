import os
import re
import bisect
import logging
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTextEdit, QListWidget, QListWidgetItem,
                             QFrame, QFileDialog, QMessageBox, QSplitter, QLineEdit, QSlider, QCheckBox,
                             QMenu)
from PySide6.QtCore import Qt, QSize, QUrl, QEvent, Signal, QTimer
from PySide6.QtGui import QGuiApplication, QTextCursor, QTextCharFormat, QColor
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
import qtawesome as qta

from core.db_manager import DBManager
from core.punctuator import Punctuator
from core.settings import AppSettings
from core.dictionary import apply_replacements
from core.mic_recorder import MicTranscriptionWorker
from core.voice_commands import strip_stop_command, beep
from gui.recording_watch import RecordingWatch
from core.i18n import tr
from utils.exporter import Exporter

logger = logging.getLogger("HistoryTab")

class HistoryTab(QWidget):
    speakers_requested = Signal(str)  # [v3.2] путь к звуку записи — разделить по говорящим
    summary_ask_changed = Signal(bool)  # [v3.2] флажок «Больше не спрашивать» → переключатель в Настройках

    def __init__(self, vosk_manager=None, parent=None):
        super().__init__(parent)
        self.db = DBManager()
        self.vosk_manager = vosk_manager
        self.history_items = []
        self.active_item = None
        # [v3] Дописывание голосом в выбранную запись
        self.append_worker = None
        self.append_chunks = []
        self.append_target_id = None
        # [v3] Плеер-караоке: позиции слов в тексте редактора
        self.word_starts_ms = []
        self.token_spans = []
        self.highlighted_token = -1
        self.setup_ui()
        self.setup_player()
        self.load_history()
        self.update_editor_state()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Заголовок
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        
        title = QLabel("Записи")
        title.setProperty("class", "TitleLabel")

        subtitle = QLabel("Все расшифровки хранятся на этом компьютере: поиск, правка, плеер, экспорт")
        subtitle.setProperty("class", "SubtitleLabel")
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addLayout(header_layout)

        # Создаем Splitter для разделения истории и редактора
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle { background-color: #2d2d34; width: 1px; }"
        )

        # -------------------------------------------------------------
        # Левая панель - список истории и поиск
        # -------------------------------------------------------------
        self.left_panel = QFrame()
        self.left_panel.setProperty("class", "CardFrame")
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)
        
        # Заголовок списка и счетчик
        history_header = QHBoxLayout()
        lbl_history = QLabel("Сохранённые записи:")
        lbl_history.setProperty("class", "HeaderLabel")
        
        self.lbl_count = QLabel("0")
        self.lbl_count.setStyleSheet("color: #a0a0ab; font-size: 12px; font-weight: 500;")
        # [v3.2, 18.11.2026] Узкий список: заголовок «Сохранённые записи:» обрезался — повторял
        # заголовок страницы «Записи»; остаётся счётчик «Записей: N»
        lbl_history.setVisible(False)
        history_header.addWidget(self.lbl_count)
        history_header.addStretch(1)
        left_layout.addLayout(history_header)

        # Поле поиска по записям
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Поиск по записям и тексту...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.on_search_changed)
        left_layout.addWidget(self.search_input)

        # Список записей
        self.list_history = QListWidget()
        self.list_history.setObjectName("HistoryListWidget")
        # [v3.2, Д4] Длинное название — переносом в две строки, без прокрутки вбок
        self.list_history.setWordWrap(True)
        self.list_history.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_history.currentRowChanged.connect(self.on_item_selection_changed)
        left_layout.addWidget(self.list_history, 1)

        # Кнопки управления историей
        history_btns_layout = QHBoxLayout()
        history_btns_layout.setSpacing(8)

        self.btn_delete = QPushButton(" Удалить")
        self.btn_delete.setProperty("class", "DangerButton")
        self.btn_delete.setIcon(qta.icon("fa5s.trash-alt", color="#ffffff"))
        self.btn_delete.clicked.connect(self.delete_active_item)
        self.btn_delete.setEnabled(False)
        
        self.btn_clear_all = QPushButton(" Очистить всё")
        self.btn_clear_all.setProperty("class", "SecondaryButton")
        self.btn_clear_all.setIcon(qta.icon("fa5s.eraser", color="#a0a0ab"))
        self.btn_clear_all.clicked.connect(self.clear_all_history)
        self.btn_clear_all.setEnabled(False)

        # [v3.2, 18.11.2026] «Очистить всё» — значком с подсказкой: две широкие кнопки держали
        # список широким, окно текста — узким
        self.btn_clear_all.setText("")
        self.btn_clear_all.setToolTip("Очистить всё — удалить все записи")
        history_btns_layout.addWidget(self.btn_delete, 1)
        history_btns_layout.addWidget(self.btn_clear_all)
        left_layout.addLayout(history_btns_layout)

        # -------------------------------------------------------------
        # Правая панель - редактор и экспорт
        # -------------------------------------------------------------
        self.right_panel = QFrame()
        self.right_panel.setProperty("class", "CardFrame")
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)
        right_layout.setSpacing(12)

        # Информация о текущем тексте
        self.info_bar = QHBoxLayout()
        info_titles = QVBoxLayout()
        info_titles.setSpacing(2)
        
        self.lbl_active_title = QLabel("Выберите запись из списка слева")
        self.lbl_active_title.setProperty("class", "HeaderLabel")
        
        self.lbl_active_date = QLabel("")
        self.lbl_active_date.setStyleSheet("color: #71717a; font-size: 11px;")
        
        info_titles.addWidget(self.lbl_active_title)
        info_titles.addWidget(self.lbl_active_date)
        self.info_bar.addLayout(info_titles, 1)

        self.lbl_stats = QLabel("")
        self.lbl_stats.setStyleSheet("color: #a0a0ab; font-size: 12px;")
        self.info_bar.addWidget(self.lbl_stats)
        
        right_layout.addLayout(self.info_bar)

        # [v3] Панель плеера (видна, если у записи есть исходный аудио/видеофайл)
        self.player_bar = QFrame()
        player_layout = QHBoxLayout(self.player_bar)
        player_layout.setContentsMargins(0, 0, 0, 0)
        player_layout.setSpacing(8)
        self.btn_play = QPushButton()
        self.btn_play.setFixedSize(34, 34)
        self.btn_play.setProperty("class", "SecondaryButton")
        self.btn_play.setIcon(qta.icon("fa5s.play", color="#6366f1"))
        self.btn_play.setToolTip("Воспроизвести / пауза")
        self.btn_play.clicked.connect(self.toggle_play)
        self.slider_pos = QSlider(Qt.Horizontal)
        self.slider_pos.sliderMoved.connect(lambda ms: self.player.setPosition(ms))
        self.lbl_player_time = QLabel("00:00 / 00:00")
        self.lbl_player_time.setStyleSheet("color: #a0a0ab; font-size: 12px;")
        self.slider_pos.setMinimumWidth(120)
        self.slider_pos.setToolTip("Клик по слову в тексте — перемотка к этому слову")
        player_layout.addWidget(self.btn_play)
        player_layout.addWidget(self.slider_pos, 1)
        player_layout.addWidget(self.lbl_player_time)
        self.player_bar.setVisible(False)
        right_layout.addWidget(self.player_bar)

        # [v3, 11.11.2026] Признак «идёт запись» при дописывании голосом: таймер, уровень, предупреждение
        self.lbl_append_status = QLabel("")
        self.lbl_append_status.setVisible(False)
        right_layout.addWidget(self.lbl_append_status)
        self.append_watch = RecordingWatch(self)
        self.append_watch.status_changed.connect(self.on_append_status)

        # Редактор текста
        self.txt_editor = QTextEdit()
        self.txt_editor.setStyleSheet(
            "QTextEdit { font-size: 14px; line-height: 22px; padding: 10px; }"
        )
        self.txt_editor.textChanged.connect(self.on_text_edited)
        self.txt_editor.viewport().installEventFilter(self)
        right_layout.addWidget(self.txt_editor, 1)

        # Панель кнопок экспорта и обработки
        export_layout = QHBoxLayout()
        export_layout.setSpacing(10)

        self.btn_copy = QPushButton("Копировать")
        self.btn_copy.setProperty("class", "SecondaryButton")
        self.btn_copy.setIcon(qta.icon("fa5s.copy", color="#e2e2e5"))
        self.btn_copy.clicked.connect(self.copy_to_clipboard)

        self.btn_auto_punct = QPushButton(" Расставить знаки")
        self.btn_auto_punct.setProperty("class", "SecondaryButton")
        self.btn_auto_punct.setIcon(qta.icon("fa5s.magic", color="#6366f1"))
        self.btn_auto_punct.clicked.connect(self.auto_punctuate_active_text)

        self.btn_save_txt = QPushButton("Экспорт в TXT")
        self.btn_save_txt.setProperty("class", "SecondaryButton")
        self.btn_save_txt.setIcon(qta.icon("fa5s.file-alt", color="#e2e2e5"))
        self.btn_save_txt.clicked.connect(self.export_txt)

        self.btn_save_srt = QPushButton("Экспорт в SRT")
        self.btn_save_srt.setProperty("class", "SecondaryButton")
        self.btn_save_srt.setIcon(qta.icon("fa5s.closed-captioning", color="#e2e2e5"))
        self.btn_save_srt.clicked.connect(self.export_srt)

        self.btn_save_json = QPushButton("Экспорт в JSON")
        self.btn_save_json.setProperty("class", "SecondaryButton")
        self.btn_save_json.setIcon(qta.icon("fa5s.code", color="#e2e2e5"))
        self.btn_save_json.clicked.connect(self.export_json)

        # [v3] Дописать голосом в конец выбранной записи
        self.btn_append_voice = QPushButton(" Дописать голосом")
        self.btn_append_voice.setProperty("class", "SecondaryButton")
        self.btn_append_voice.setIcon(qta.icon("fa5s.microphone", color="#6366f1"))
        self.btn_append_voice.setToolTip("Запись с микрофона по умолчанию; текст добавится в конец записи")
        self.btn_append_voice.clicked.connect(self.toggle_append_voice)

        # [v3.2, 18.11.2026] Ф3: заметка Markdown в базу (папка — «Настройки → Общие»)
        self.btn_save_md = QPushButton("Экспорт в MD")
        self.btn_save_md.setProperty("class", "SecondaryButton")
        self.btn_save_md.setIcon(qta.icon("fa5b.markdown", color="#e2e2e5"))
        self.btn_save_md.setToolTip("Заметка .md с датой, длительностью и говорящими — в папку из «Настройки → Общие»")
        self.btn_save_md.clicked.connect(self.export_md)

        # [v3.2] Ф2: изложение — только по этой кнопке; подпись говорит, что текст уходит в облако
        self.btn_summary = QPushButton(" Изложение в Claude — облако")
        self.btn_summary.setObjectName("CloudButton")
        self.btn_summary.setIcon(qta.icon("fa5s.cloud-upload-alt", color="#f59e0b"))
        self.btn_summary.setToolTip("Текст записи уйдёт в окно Claude, оттуда — в облако Anthropic.\n"
                                    "Без нажатия этой кнопки текст не покидает компьютер.")
        self.btn_summary.clicked.connect(self.send_summary)

        # [v3.2] Ф1: запись созвона → разделить по говорящим (страница «Новая запись → Файл»)
        self.btn_speakers = QPushButton(" Говорящие")
        self.btn_speakers.setProperty("class", "SecondaryButton")
        self.btn_speakers.setIcon(qta.icon("fa5s.users", color="#6366f1"))
        self.btn_speakers.setToolTip("Расшифровать звук этой записи заново и разделить текст по говорящим")
        self.btn_speakers.clicked.connect(
            lambda: self.speakers_requested.emit((self.active_item or {}).get("media_path") or ""))

        # [v3] Две строки кнопок: в одну строку 7 кнопок не помещались
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)
        actions_layout.addWidget(self.btn_copy)
        actions_layout.addWidget(self.btn_auto_punct)
        actions_layout.addWidget(self.btn_append_voice)
        actions_layout.addStretch(1)
        right_layout.addLayout(actions_layout)

        # [v3.2, Д4] Три строки: в две новые кнопки не помещались и обрезались
        cloud_layout = QHBoxLayout()
        cloud_layout.setSpacing(10)
        cloud_layout.addWidget(self.btn_summary)
        cloud_layout.addWidget(self.btn_speakers)
        cloud_layout.addStretch(1)
        right_layout.addLayout(cloud_layout)

        # [v3.2, 18.11.2026] Экспорт — одной кнопкой с меню во второй строке: строкой ниже
        # окно текста стало выше. Кнопки форматов остаются — меню нажимает их.
        self.btn_export = QPushButton(" Экспорт")
        self.btn_export.setProperty("class", "SecondaryButton")
        self.btn_export.setIcon(qta.icon("fa5s.file-export", color="#e2e2e5"))
        export_menu = QMenu(self.btn_export)
        for btn, fmt in ((self.btn_save_md, "MD — заметка в базу"), (self.btn_save_txt, "TXT"),
                         (self.btn_save_srt, "SRT"), (self.btn_save_json, "JSON")):
            btn.setText(fmt)
            act = export_menu.addAction(tr(fmt))
            act.triggered.connect(btn.click)
            btn.setVisible(False)
        export_menu.aboutToShow.connect(lambda: [
            a.setEnabled(b.isEnabled()) for a, b in zip(
                export_menu.actions(),
                (self.btn_save_md, self.btn_save_txt, self.btn_save_srt, self.btn_save_json))])
        self.btn_export.setMenu(export_menu)
        cloud_layout.insertWidget(cloud_layout.count() - 1, self.btn_export)

        # Добавляем панели в сплиттер. [v3.2, 18.11.2026] Список уже, окно текста растёт с окном
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        self.left_panel.setMaximumWidth(240)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([200, 700])

        layout.addWidget(splitter, 1)

    def load_history(self, search_query: str = ""):
        """
        Загружает историю записей из базы данных SQLite с учетом поискового фильтра.
        """
        self.list_history.blockSignals(True)
        self.list_history.clear()
        
        if search_query.strip():
            self.history_items = self.db.search_items(search_query)
        else:
            self.history_items = self.db.get_all_items()

        self.lbl_count.setText(f"Записей: {len(self.history_items)}")
        self.btn_clear_all.setEnabled(len(self.history_items) > 0)

        for item in self.history_items:
            list_item = QListWidgetItem(tr(item["title"]))  # [12.11.2026] заголовок — на языке интерфейса
            list_item.setData(Qt.UserRole, item["id"])
            list_item.setToolTip(tr(item["title"]))  # [v3.2] полное название, если в списке сокращено
            
            source_name = item.get("source", "") or ""
            if "звук компьютера" in source_name.lower():
                list_item.setIcon(qta.icon("fa5s.desktop", color="#22c55e"))
            elif "диктовка" in source_name.lower():
                list_item.setIcon(qta.icon("fa5s.bolt", color="#f59e0b"))
            elif "микрофон" in source_name.lower():
                list_item.setIcon(qta.icon("fa5s.microphone", color="#6366f1"))
            else:
                list_item.setIcon(qta.icon("fa5s.file-audio", color="#a855f7"))
                
            self.list_history.addItem(list_item)

        self.list_history.blockSignals(False)

        # Если есть записи, выбираем первую
        if self.history_items:
            self.list_history.setCurrentRow(0)
        else:
            self.active_item = None
            self.update_editor_state()

    def on_search_changed(self, text: str):
        """
        Живая фильтрация записей при вводе поискового запроса.
        """
        self.load_history(text)

    def save_mic_draft(self, item_id: int, title: str, text: str, words: list) -> int:
        """
        [v3, 12.11.2026] Черновик записи с микрофона на паузе: первый раз — новая запись,
        дальше — та же запись обновляется. Список обновляется, только если не идёт дописывание.
        """
        if item_id:
            self.db.update_item(item_id, title, text, words, None)
        else:
            item_id = self.db.add_item(title, text, words, "Запись с микрофона", None) or 0
            logger.info(f"Черновик записи на паузе сохранён в базу данных с ID: {item_id}")
        if self.append_worker is None:
            self.load_history(self.search_input.text())
        return item_id

    def add_transcript(self, text: str, words: list, source_name: str, media_path: str = None,
                       item_id: int = 0):
        """
        Сохраняет новую расшифровку в постоянную базу данных SQLite и обновляет интерфейс.
        [v3, 12.11.2026] item_id — черновик паузы: обновить его, новую запись не создавать.
        """
        if item_id:
            draft = next((i for i in self.db.get_all_items() if i["id"] == item_id), None)
            title = draft["title"] if draft else f"[{datetime.now().strftime('%H:%M:%S')}] {source_name}"
            self.db.update_item(item_id, title, text, words, media_path)
            logger.info(f"Запись с паузами сохранена в базу данных с ID: {item_id}")
        else:
            timestamp = datetime.now().strftime("%H:%M:%S")
            title = f"[{timestamp}] {source_name}"

            # Сохраняем в SQLite
            item_id = self.db.add_item(title, text, words, source_name, media_path)
            logger.info(f"Новая расшифровка успешно сохранена в базу данных с ID: {item_id}")
        
        # Очищаем поле поиска, чтобы показать свежую запись на самом верху
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)

        # Перезагружаем список
        self.load_history()
        
        # Выбираем первую запись (она только что добавлена сверху)
        if self.list_history.count() > 0:
            self.list_history.setCurrentRow(0)

    def on_item_selection_changed(self, row: int):
        """
        Обработка выбора записи в списке.
        """
        if row < 0 or row >= len(self.history_items):
            self.active_item = None
            self.update_editor_state()
            return

        self.active_item = self.history_items[row]
        
        self.lbl_active_title.setText(self.active_item["title"])
        created_at = self.active_item.get("created_at", "")
        self.lbl_active_date.setText(f"Создано: {created_at}" if created_at else "")
        
        # Загружаем текст без вызова auto-save
        self.txt_editor.blockSignals(True)
        self.txt_editor.setPlainText(self.active_item["text"])
        self.txt_editor.blockSignals(False)

        self.update_stats()
        self.update_editor_state()
        self.load_media_for_active()

    def on_text_edited(self):
        """
        Автоматически сохраняет любые пользовательские правки текста обратно в SQLite.
        """
        if not self.active_item:
            return
            
        new_text = self.txt_editor.toPlainText()
        self.active_item["text"] = new_text
        
        # Сохраняем в БД
        self.db.update_item_text(self.active_item["id"], new_text)
        self.update_stats()
        self.rebuild_token_map()

    def update_stats(self):
        if not self.active_item:
            self.lbl_stats.setText("")
            return
            
        text = self.txt_editor.toPlainText()
        char_count = len(text)
        word_count = len(text.split()) if text.strip() else 0
        self.lbl_stats.setText(f"Слов: {word_count} | Символов: {char_count}")

    def update_editor_state(self):
        """
        Управляет доступностью редактора и кнопок действий.
        """
        has_active = (self.active_item is not None)
        appending = self.append_worker is not None
        self.txt_editor.setEnabled(has_active)
        # [v3, 11.11.2026] Во время дописывания редактор показывает живой текст — руками не правится
        self.txt_editor.setReadOnly(appending)
        self.btn_append_voice.setEnabled(has_active or appending)
        self.list_history.setEnabled(not appending)
        self.btn_copy.setEnabled(has_active)
        self.btn_auto_punct.setEnabled(has_active)
        self.btn_save_txt.setEnabled(has_active)
        self.btn_save_json.setEnabled(has_active)
        self.btn_save_md.setEnabled(has_active)
        self.btn_summary.setEnabled(has_active and not appending)
        media = (self.active_item or {}).get("media_path") or ""
        self.btn_speakers.setEnabled(has_active and not appending and bool(media) and os.path.exists(media))
        self.btn_delete.setEnabled(has_active)
        
        has_words = False
        if has_active:
            has_words = len(self.active_item.get("words", [])) > 0
            
        self.btn_save_srt.setEnabled(has_active and has_words)
        
        if not has_active:
            self.lbl_active_title.setText("Выберите запись из списка слева")
            self.lbl_active_date.setText("")
            self.txt_editor.setPlaceholderText("Здесь будет отображаться выбранный текст для редактирования...")
            self.txt_editor.clear()
            self.lbl_stats.setText("")
            if hasattr(self, "player"):
                self.player.stop()
                self.player_bar.setVisible(False)

    # -----------------------------------------------------------------
    # [v3] Дописывание голосом
    # -----------------------------------------------------------------
    def toggle_append_voice(self):
        if self.append_worker:
            self.btn_append_voice.setText(" Завершаю...")
            self.btn_append_voice.setEnabled(False)
            self.append_worker.stop()
            return
        if not self.active_item:
            return
        if not self.vosk_manager or not self.vosk_manager.active_model:
            QMessageBox.warning(self, "Модель не загружена",
                                "Дождитесь загрузки модели или выберите её: «Настройки → Распознавание».")
            return
        self.append_chunks = []
        self.append_words = []
        self.append_target_id = self.active_item["id"]
        # [v3, 11.11.2026] Исходный текст записи: живой текст дописывания показывается после него
        self.append_base = self.txt_editor.toPlainText().rstrip()
        self.append_worker = MicTranscriptionWorker(None, self.vosk_manager)
        self.append_worker.final_words.connect(self.append_words.extend)
        self.append_worker.final_chunk.connect(self.on_append_chunk)
        # [v3, 11.11.2026] Было: живая фраза — только в строке статистики сверху (последние 60 знаков),
        # а основной текст появлялся лишь после «стоп запись». Теперь — сразу в окне текста
        self.append_worker.partial_result.connect(self.render_append_live)
        self.append_worker.error.connect(lambda e: QMessageBox.critical(self, "Ошибка записи", e))
        self.append_worker.recording_finished.connect(self.on_append_finished)
        self.append_watch.attach(self.append_worker)
        self.lbl_append_status.setVisible(True)
        self.append_worker.start()
        self.btn_append_voice.setText(" Стоп запись")
        self.btn_append_voice.setIcon(qta.icon("fa5s.stop", color="#ef4444"))
        self.update_editor_state()

    def start_voice_append(self):
        """[v3] Команда «продолжить запись»: дописывание в выбранную запись (по умолчанию — самую новую)."""
        if self.append_worker or not self.active_item:
            return
        if not self.vosk_manager or not self.vosk_manager.active_model:
            # Без окна-предупреждения: при работе голосом его некому закрыть
            logger.info("Команда «продолжить запись» пропущена: модель ещё не загружена.")
            return
        self.toggle_append_voice()
        if self.append_worker:
            beep(True)

    def stop_voice_append(self):
        """[v3] Команда «стоп запись» во время дописывания."""
        if self.append_worker:
            beep(False)
            self.toggle_append_voice()

    def on_append_chunk(self, chunk: str):
        """[v3, 11.11.2026] Готовый кусок: в окно текста и сразу в базу (без знаков) — не пропадёт при сбое."""
        self.append_chunks.append(chunk)
        self.render_append_live()
        if self.append_target_id is not None:
            self.db.update_item_text(self.append_target_id, self._append_preview())

    def _append_preview(self, partial: str = "") -> str:
        added = " ".join(c for c in self.append_chunks + [partial] if c.strip())
        if not added:
            return self.append_base
        return self.append_base + ("\n\n" if self.append_base else "") + added

    def render_append_live(self, partial: str = ""):
        """[v3, 11.11.2026] Живой текст дописывания в основном окне; автосохранение не срабатывает."""
        if not self.append_worker:
            return
        self.txt_editor.blockSignals(True)
        self.txt_editor.setPlainText(self._append_preview(partial))
        self.txt_editor.blockSignals(False)
        self.txt_editor.moveCursor(QTextCursor.End)
        self.txt_editor.ensureCursorVisible()

    def on_append_status(self, text: str, warning: bool):
        self.lbl_append_status.setText(text)
        self.lbl_append_status.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: " + ("#f59e0b;" if warning else "#ef4444;"))

    def on_append_finished(self):
        self.append_watch.detach()
        self.lbl_append_status.setVisible(False)
        self.append_worker = None
        # [v3, 11.11.2026] Убираем живой предпросмотр: итог ниже собирается от исходного текста
        self.txt_editor.blockSignals(True)
        self.txt_editor.setPlainText(self.append_base)
        self.txt_editor.blockSignals(False)
        self.btn_append_voice.setText(" Дописать голосом")
        self.btn_append_voice.setIcon(qta.icon("fa5s.microphone", color="#6366f1"))
        # [v3] Знаки — по паузам между словами, как во вкладке «Запись с микрофона»
        words = strip_stop_command(self.append_words)
        if words:
            addition = Punctuator.punctuate_words_with_timing(words, **AppSettings.pauses())
        elif self.append_words:
            addition = ""
        else:
            addition = Punctuator.punctuate_plain_text(chunks=self.append_chunks) if self.append_chunks else ""
        addition = apply_replacements(addition)
        # Запись могла смениться только через список, а он заблокирован на время записи
        if addition and self.active_item and self.active_item["id"] == self.append_target_id:
            current = self.txt_editor.toPlainText().rstrip()
            separator = "\n\n" if current else ""
            self.txt_editor.setPlainText(current + separator + addition)  # автосохранение через textChanged
            self.txt_editor.moveCursor(QTextCursor.End)
        elif self.append_target_id is not None and self.append_chunks:
            # [v3, 11.11.2026] Дописывать нечего (была только команда «стоп») — убрать из базы черновик
            self.db.update_item_text(self.append_target_id, self.append_base)
        self.update_editor_state()
        self.update_stats()

    # -----------------------------------------------------------------
    # [v3] Плеер-караоке
    # -----------------------------------------------------------------
    def setup_player(self):
        self.audio_output = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.durationChanged.connect(lambda d: self.slider_pos.setRange(0, d))
        self.player.positionChanged.connect(self.on_player_position)
        self.player.playbackStateChanged.connect(self.on_playback_state)
        self.player.errorOccurred.connect(
            lambda err, msg: logger.warning(f"Плеер: {msg}") if err != QMediaPlayer.NoError else None)

    def load_media_for_active(self):
        self.player.stop()
        path = (self.active_item or {}).get("media_path")
        has_media = bool(path) and os.path.exists(path)
        self.player_bar.setVisible(has_media)
        self.player.setSource(QUrl.fromLocalFile(path) if has_media else QUrl())
        words = (self.active_item or {}).get("words", []) if has_media else []
        self.word_starts_ms = [int(float(w.get("start", 0)) * 1000) for w in words]
        self.rebuild_token_map()

    def rebuild_token_map(self):
        """Позиции слов в тексте редактора; пересчитываются после каждой правки."""
        self.highlighted_token = -1
        self.txt_editor.setExtraSelections([])
        if not self.word_starts_ms:
            self.token_spans = []
            return
        self.token_spans = [(m.start(), m.end()) for m in re.finditer(r"\S+", self.txt_editor.toPlainText())]

    def _token_to_word(self, token_idx: int) -> int:
        # Текст после пунктуации содержит те же слова, что и тайминги Vosk.
        # Если пользователь правил текст и число слов разошлось — сопоставляем пропорционально.
        n_tok, n_words = len(self.token_spans), len(self.word_starts_ms)
        if n_tok == n_words:
            return token_idx
        return min(n_words - 1, int(token_idx * n_words / max(1, n_tok)))

    def _word_to_token(self, word_idx: int) -> int:
        n_tok, n_words = len(self.token_spans), len(self.word_starts_ms)
        if n_tok == n_words:
            return word_idx
        return min(n_tok - 1, int(word_idx * n_tok / max(1, n_words)))

    def eventFilter(self, obj, event):
        # Клик по слову в редакторе — перемотка плеера на это слово
        if (obj is self.txt_editor.viewport() and event.type() == QEvent.MouseButtonRelease
                and self.player_bar.isVisible() and self.token_spans and self.word_starts_ms
                and not self.txt_editor.textCursor().hasSelection()):
            pos = self.txt_editor.cursorForPosition(event.position().toPoint()).position()
            starts = [s for s, _ in self.token_spans]
            token_idx = max(0, bisect.bisect_right(starts, pos) - 1)
            self.player.setPosition(self.word_starts_ms[self._token_to_word(token_idx)])
        return super().eventFilter(obj, event)

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def on_playback_state(self, state):
        playing = state == QMediaPlayer.PlayingState
        self.btn_play.setIcon(qta.icon("fa5s.pause" if playing else "fa5s.play", color="#6366f1"))

    def on_player_position(self, ms: int):
        if not self.slider_pos.isSliderDown():
            self.slider_pos.setValue(ms)
        fmt = lambda v: f"{v // 60000:02d}:{(v // 1000) % 60:02d}"
        self.lbl_player_time.setText(f"{fmt(ms)} / {fmt(self.player.duration())}")
        if not self.token_spans or not self.word_starts_ms:
            return
        word_idx = max(0, bisect.bisect_right(self.word_starts_ms, ms) - 1)
        token_idx = self._word_to_token(word_idx)
        if token_idx == self.highlighted_token:
            return
        self.highlighted_token = token_idx
        start, end = self.token_spans[token_idx]
        sel = QTextEdit.ExtraSelection()
        fmt_hl = QTextCharFormat()
        fmt_hl.setBackground(QColor(99, 102, 241, 110))
        sel.format = fmt_hl
        cursor = QTextCursor(self.txt_editor.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        sel.cursor = cursor
        self.txt_editor.setExtraSelections([sel])
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            # Держим подсвеченное слово в поле зрения, не трогая курсор пользователя
            rect = self.txt_editor.cursorRect(cursor)
            if not self.txt_editor.viewport().rect().contains(rect):
                bar = self.txt_editor.verticalScrollBar()
                bar.setValue(bar.value() + rect.top() - self.txt_editor.viewport().height() // 3)

    def shutdown(self):
        """Останавливает плеер и запись при выходе из программы."""
        self.player.stop()
        if self.append_worker:
            self.append_worker.stop()
            self.append_worker.wait(2000)

    def auto_punctuate_active_text(self):
        """
        Применяет интеллектуальную расстановку знаков препинания и заглавных букв к текущему тексту.
        """
        if not self.active_item:
            return

        words = self.active_item.get("words", [])
        current_text = self.txt_editor.toPlainText().strip()
        if not current_text:
            return

        # [v3] Тайминги — только если текст не правили и не дописывали (то же число слов),
        # иначе пересборка по таймингам стёрла бы правки и дописанное
        if words and len(words) == len(current_text.split()):
            formatted = Punctuator.punctuate_words_with_timing(words)
        else:
            formatted = Punctuator.punctuate_plain_text(current_text)

        if formatted:
            self.txt_editor.setPlainText(formatted)
            QMessageBox.information(self, "Пунктуация", "Знаки препинания и заглавные буквы успешно расставлены!")

    def delete_active_item(self):
        """
        Удаляет текущую выбранную запись из базы данных SQLite.
        """
        if not self.active_item:
            return
            
        reply = QMessageBox.question(
            self, "Удаление записи", 
            f"Вы действительно хотите навсегда удалить запись '{self.active_item['title']}' из базы данных?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.delete_item(self.active_item["id"])
            current_row = self.list_history.currentRow()
            
            # Перезагружаем с сохранением поискового запроса
            self.load_history(self.search_input.text())
            
            if self.history_items:
                new_row = min(current_row, len(self.history_items) - 1)
                self.list_history.setCurrentRow(new_row)
            else:
                self.active_item = None
                self.update_editor_state()

    def clear_all_history(self):
        """
        Полностью очищает всю базу данных истории.
        """
        if not self.history_items:
            return

        reply = QMessageBox.warning(
            self, "Очистка всей истории", 
            "Внимание! Вы собираетесь навсегда удалить ВСЕ записи из базы данных истории.\nЭто действие нельзя отменить. Продолжить?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.clear_all()
            self.search_input.clear()
            self.load_history()
            QMessageBox.information(self, "История очищена", "Все записи успешно удалены.")

    def copy_to_clipboard(self):
        if not self.active_item:
            return
        
        text = self.txt_editor.toPlainText()
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "Копирование", "Текст успешно скопирован в буфер обмена!")

    def export_txt(self):
        if not self.active_item:
            return
            
        source_clean = self.active_item['source'].split('.')[0] or 'transcription'
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить текст", f"{source_clean}.txt", 
            "Текстовые файлы (*.txt);;Все файлы (*.*)"
        )
        
        if file_path:
            text = self.txt_editor.toPlainText()
            if Exporter.save_txt(text, file_path):
                QMessageBox.information(self, "Экспорт", "Файл успешно сохранен в формате TXT!")

    def export_srt(self):
        if not self.active_item:
            return
            
        words = self.active_item.get("words", [])
        if not words:
            return
            
        source_clean = self.active_item['source'].split('.')[0] or 'subtitles'
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить субтитры", f"{source_clean}.srt", 
            "Файлы субтитров (*.srt);;Все файлы (*.*)"
        )
        
        if file_path:
            if Exporter.save_srt(words, file_path):
                QMessageBox.information(self, "Экспорт", "Субтитры успешно сохранены в формате SRT!")

    def export_json(self):
        if not self.active_item:
            return
            
        words = self.active_item.get("words", [])
        full_text = self.txt_editor.toPlainText()
        source_clean = self.active_item['source'].split('.')[0] or 'metadata'
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить метаданные JSON", f"{source_clean}.json", 
            "Файлы JSON (*.json);;Все файлы (*.*)"
        )
        
        if file_path:
            if Exporter.save_json(words, full_text, file_path):
                QMessageBox.information(self, "Экспорт", "Метаданные JSON успешно сохранены!")

    # -----------------------------------------------------------------
    # [v3.2, 18.11.2026] Ф3: заметка Markdown в базу
    # -----------------------------------------------------------------
    def _duration_s(self) -> float:
        if self.player_bar.isVisible() and self.player.duration() > 0:
            return self.player.duration() / 1000.0
        words = (self.active_item or {}).get("words", [])
        return float(words[-1].get("end", 0)) if words else 0.0

    def export_md(self):
        if not self.active_item:
            return
        folder = AppSettings.get("export/md_dir")
        path = Exporter.save_md(self.active_item["title"], self.txt_editor.toPlainText(),
                                self.active_item.get("created_at", ""), folder, self._duration_s())
        if path:
            QMessageBox.information(self, "Экспорт в MD", f"Заметка сохранена:\n{path}")
        else:
            QMessageBox.warning(self, "Экспорт в MD", f"Заметку не удалось сохранить в папку:\n{folder}")

    # -----------------------------------------------------------------
    # [v3.2] Ф2: изложение в Claude — только по кнопке, с предупреждением «облако»
    # -----------------------------------------------------------------
    def confirm_cloud(self) -> bool:
        """Предупреждение перед отправкой в облако; флажок «Больше не спрашивать» сохраняется в настройках."""
        if not AppSettings.get("summary/ask"):
            return True
        # Окно собирается здесь — переводы через tr() явно (подмена Qt в i18n их не видит)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(tr("Текст уйдёт в облако"))
        box.setText(tr("Текст записи уйдёт в Claude, в облако"))
        box.setInformativeText(tr("Программа вставит текст и запрос «кратко: о чём, решения, задачи, кто что сказал» "
                                  "в окно Claude. Claude отправит его в облако Anthropic — текст покинет этот компьютер.")
                               + "\n\n" + tr("Отправить?"))
        dont_ask = QCheckBox(tr("Больше не спрашивать"))
        dont_ask.setToolTip(tr("Вернуть вопрос — «Настройки → Изложение»"))
        box.setCheckBox(dont_ask)
        btn_send = box.addButton(tr("Отправить в Claude"), QMessageBox.AcceptRole)
        btn_cancel = box.addButton(tr("Отмена"), QMessageBox.RejectRole)
        box.setDefaultButton(btn_cancel)
        box.exec()
        if box.clickedButton() is not btn_send:
            return False
        if dont_ask.isChecked():
            AppSettings.set("summary/ask", False)
            self.summary_ask_changed.emit(False)
        return True

    def send_summary(self):
        if not self.active_item:
            return
        text = self.txt_editor.toPlainText().strip()
        if not text:
            return
        if not self.confirm_cloud():
            return
        from core import summary
        result = summary.send(text)
        if result == "clipboard":
            QMessageBox.information(self, "Изложение в Claude",
                                    "Окно Claude не найдено. Запрос с текстом — в буфере обмена:\n"
                                    "откройте Claude и вставьте (Ctrl+V).")
