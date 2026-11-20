import os
import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFileDialog, QFrame, QProgressBar, 
                             QMessageBox, QTextEdit, QCheckBox, QComboBox)
from PySide6.QtCore import Qt, Signal
import qtawesome as qta
from core.audio_processor import FileTranscriptionWorker
from core.punctuator import Punctuator
from core.dictionary import apply_replacements
from core.settings import AppSettings
from core import diarizer

logger = logging.getLogger("FileTab")

class FileDropArea(QFrame):
    """
    Кастомная область Drag & Drop для выбора аудиофайлов.
    """
    file_dropped = Signal(str)
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropArea")
        self.setAcceptDrops(True)
        self.setProperty("class", "CardFrame")
        self.setProperty("dragged", False)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)
        
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setPixmap(qta.icon("fa5s.file-audio", color="#a0a0ab").pixmap(64, 64))
        
        self.text_label = QLabel("Перетащите аудиофайл сюда или нажмите для выбора")
        self.text_label.setObjectName("DropAreaText")
        self.text_label.setAlignment(Qt.AlignCenter)
        
        self.format_label = QLabel("Поддерживаются форматы: MP3, WAV, M4A, FLAC, OGG, MP4 и др.")
        self.format_label.setObjectName("DropAreaFormat")
        self.format_label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addWidget(self.format_label)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            self.setProperty("dragged", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.setProperty("dragged", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event):
        self.setProperty("dragged", False)
        self.style().unpolish(self)
        self.style().polish(self)
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if os.path.exists(file_path):
                self.file_dropped.emit(file_path)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

class FileTab(QWidget):
    # Сигнал для передачи распознанного текста в историю
    transcription_completed = Signal(str, list, str) # (текст, слова с таймингами, имя файла)

    def __init__(self, vosk_manager, parent=None):
        super().__init__(parent)
        self.vosk_manager = vosk_manager
        self.selected_file_path = None
        self.worker = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        # Заголовок
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        
        title = QLabel("Транскрибация аудиофайлов")
        title.setProperty("class", "TitleLabel")
        
        subtitle = QLabel("Запись разговора, лекции или видео — в текст, на этом компьютере, без интернета")
        subtitle.setProperty("class", "SubtitleLabel")
        
        # [v3.2] Заголовок «Новая запись» — у страницы; здесь только подсказка
        title.setVisible(False)
        header_layout.addWidget(subtitle)
        layout.addLayout(header_layout)

        # Область загрузки файла
        self.drop_area = FileDropArea()
        self.drop_area.file_dropped.connect(self.select_file)
        self.drop_area.clicked.connect(self.browse_file)
        layout.addWidget(self.drop_area, 1)  # [v3.2, Д7] зона файла занимает место — пустого отступа сверху нет

        # Карточка выбранного файла (скрыта по умолчанию)
        self.file_info_card = QFrame()
        self.file_info_card.setObjectName("FileInfoCard")
        self.file_info_card.setProperty("class", "CardFrame")
        self.file_info_card.setVisible(False)
        
        file_info_layout = QHBoxLayout(self.file_info_card)
        file_info_layout.setContentsMargins(15, 15, 15, 15)
        
        file_icon = QLabel()
        file_icon.setPixmap(qta.icon("fa5s.file-alt", color="#6366f1").pixmap(32, 32))
        file_info_layout.addWidget(file_icon)
        
        file_details_layout = QVBoxLayout()
        file_details_layout.setSpacing(2)
        self.lbl_file_name = QLabel("Имя файла.mp3")
        self.lbl_file_name.setProperty("class", "HeaderLabel")
        self.lbl_file_meta = QLabel("Размер: 15 МБ | Длительность: --:--")
        self.lbl_file_meta.setObjectName("FileMetaLabel")
        
        file_details_layout.addWidget(self.lbl_file_name)
        file_details_layout.addWidget(self.lbl_file_meta)
        file_info_layout.addLayout(file_details_layout, 1)
        
        self.btn_remove_file = QPushButton()
        self.btn_remove_file.setFixedSize(36, 36)
        self.btn_remove_file.setIcon(qta.icon("fa5s.times", color="#ef4444"))
        self.btn_remove_file.setObjectName("RemoveFileButton")
        self.btn_remove_file.clicked.connect(self.clear_selected_file)
        file_info_layout.addWidget(self.btn_remove_file)
        
        layout.addWidget(self.file_info_card)

        # Панель прогресса (скрыта по умолчанию)
        self.progress_card = QFrame()
        self.progress_card.setProperty("class", "CardFrame")
        self.progress_card.setVisible(False)
        
        progress_layout = QVBoxLayout(self.progress_card)
        progress_layout.setContentsMargins(15, 15, 15, 15)
        progress_layout.setSpacing(8)
        
        progress_header = QHBoxLayout()
        self.lbl_status = QLabel("Распознавание речи...")
        self.lbl_status.setProperty("class", "HeaderLabel")
        self.lbl_time_progress = QLabel("00:00 / 00:00")
        self.lbl_time_progress.setObjectName("TimeProgressLabel")
        progress_header.addWidget(self.lbl_status)
        progress_header.addStretch(1)
        progress_header.addWidget(self.lbl_time_progress)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        
        progress_layout.addLayout(progress_header)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addWidget(self.progress_card)

        # Поле вывода распознаваемого текста в реальном времени
        self.text_container = QWidget()
        self.text_container.setVisible(False)
        text_layout = QVBoxLayout(self.text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(5)
        
        live_label = QLabel("Текст транскрибации (живой поток):")
        live_label.setProperty("class", "HeaderLabel")
        
        self.txt_live_output = QTextEdit()
        self.txt_live_output.setReadOnly(True)
        self.txt_live_output.setStyleSheet("QTextEdit { font-size: 13px; line-height: 18px; }")
        
        text_layout.addWidget(live_label)
        text_layout.addWidget(self.txt_live_output)
        layout.addWidget(self.text_container, 1)

        # Панель управления действиями
        self.control_layout = QHBoxLayout()
        
        self.chk_punctuation = QCheckBox("Автоматическая пунктуация и заглавные буквы")
        self.chk_punctuation.setChecked(True)
        self.chk_punctuation.setStyleSheet("font-size: 13px; color: #a0a0ab;")
        
        self.btn_start = QPushButton("Начать транскрибацию")
        self.btn_start.setProperty("class", "PrimaryButton")
        self.btn_start.setIcon(qta.icon("fa5s.play", color="#ffffff"))
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self.start_transcription)
        
        self.btn_cancel = QPushButton("Отменить")
        self.btn_cancel.setProperty("class", "DangerButton")
        self.btn_cancel.setIcon(qta.icon("fa5s.stop", color="#ffffff"))
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self.cancel_transcription)
        
        # [v3] Диаризация: кто говорит. Число говорящих известно — точнее, чем «определить самому»
        self.cb_speakers = QComboBox()
        self.cb_speakers.addItem("Говорящие: не разделять", None)
        self.cb_speakers.addItem("Говорящие: определить самому", 0)
        for n in range(2, 7):
            self.cb_speakers.addItem(f"Говорящих: {n}", n)
        self.cb_speakers.setToolTip("Разделить текст по говорящим (диаризация). Работает дольше: ≈ 1/5 длительности записи")
        self.cb_speakers.setEnabled(diarizer.available())

        self.control_layout.addWidget(self.chk_punctuation)
        self.control_layout.addWidget(self.cb_speakers)
        self.control_layout.addStretch(1)
        self.control_layout.addWidget(self.btn_cancel)
        self.control_layout.addWidget(self.btn_start)
        layout.addStretch(0)  # [v3.2, Д7] файл выбран, текста ещё нет — место уходит вниз, а не между блоками
        layout.addLayout(self.control_layout)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите аудиофайл", "", 
            "Аудиофайлы (*.mp3 *.wav *.m4a *.flac *.ogg *.mp4 *.avi *.mkv *.wma);;Все файлы (*.*)"
        )
        if file_path:
            self.select_file(file_path)

    def select_file(self, file_path: str):
        if not os.path.exists(file_path):
            return
            
        self.selected_file_path = file_path
        
        # Получаем информацию о файле
        file_name = os.path.basename(file_path)
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        
        self.lbl_file_name.setText(file_name)
        self.lbl_file_meta.setText(f"Размер: {file_size_mb:.2f} МБ | Путь: {os.path.dirname(file_path)}")
        
        # Обновляем UI
        self.drop_area.setVisible(False)
        self.file_info_card.setVisible(True)
        self.btn_start.setEnabled(True)
        
        # Очищаем результаты
        self.txt_live_output.clear()
        self.text_container.setVisible(False)
        self.progress_card.setVisible(False)

    def open_for_speakers(self, file_path: str):
        """[v3.2] Из «Записей»: звук записи созвона — сразу с разделением по говорящим."""
        if self.worker and self.worker.isRunning():
            return
        self.select_file(file_path)
        idx = self.cb_speakers.findData(0)
        if idx >= 0 and self.cb_speakers.isEnabled():
            self.cb_speakers.setCurrentIndex(idx)

    def clear_selected_file(self):
        self.selected_file_path = None
        self.drop_area.setVisible(True)
        self.file_info_card.setVisible(False)
        self.btn_start.setEnabled(False)
        self.text_container.setVisible(False)
        self.progress_card.setVisible(False)

    def format_seconds(self, seconds: float) -> str:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m:02d}:{s:02d}"

    def start_transcription(self):
        if not self.selected_file_path:
            return
            
        if not self.vosk_manager.active_model:
            QMessageBox.warning(
                self, "Модель не выбрана", 
                "Модель распознавания ещё не загружена.\nВыберите язык: «Настройки → Распознавание»."
            )
            return

        # Инициализируем UI для процесса работы
        self.btn_start.setVisible(False)
        self.btn_cancel.setVisible(True)
        self.btn_remove_file.setEnabled(False)
        self.progress_card.setVisible(True)
        self.text_container.setVisible(True)
        
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Инициализация аудиодекодера FFmpeg...")
        self.lbl_time_progress.setText("00:00 / 00:00")
        self.txt_live_output.clear()

        # Создаем и запускаем фоновый рабочий поток
        self.worker = FileTranscriptionWorker(self.selected_file_path, self.vosk_manager,
                                              num_speakers=self.cb_speakers.currentData())
        self.worker.status.connect(self.lbl_status.setText)

        # Подключаем сигналы
        self.worker.progress.connect(self.on_progress)
        self.worker.partial_result.connect(self.on_partial_result)
        self.worker.final_chunk.connect(self.on_final_chunk)
        self.worker.error.connect(self.on_error)
        self.worker.transcription_finished.connect(self.on_finished)
        
        self.worker.start()

    def on_progress(self, percent: int, current: float, total: float):
        self.progress_bar.setValue(percent)
        self.lbl_status.setText("Распознавание речи...")
        self.lbl_time_progress.setText(f"{self.format_seconds(current)} / {self.format_seconds(total)}")

    def on_partial_result(self, partial_text: str):
        # Показываем текущую распознаваемую фразу в самом конце в квадратных скобках
        cursor = self.txt_live_output.textCursor()
        # Возвращаем курсор назад и стираем предыдущий временный текст, если нужно,
        # но проще дописывать в конец.
        # Для красивого вывода мы будем просто использовать отображение финальных чанков,
        # а частичные выводить во временную строку состояния.
        self.lbl_status.setText(f"Распознавание: {partial_text}...")

    def on_final_chunk(self, final_text: str):
        self.txt_live_output.append(final_text)

    def on_error(self, err_msg: str):
        QMessageBox.critical(self, "Ошибка транскрибации", err_msg)
        self.reset_ui_after_work()

    def on_finished(self, full_text: str, words: list):
        self.progress_bar.setValue(100)
        self.lbl_status.setText("Распознавание успешно завершено!")
        
        # Применяем пунктуацию, если включен чекбокс
        final_text = full_text
        if self.chk_punctuation.isChecked():
            formatted = Punctuator.punctuate_words_with_timing(words)
            if formatted:
                final_text = formatted
            elif full_text:
                final_text = Punctuator.punctuate_plain_text(full_text)
        # [v3] Разделено по говорящим — текст репликами «[м:сс] Говорящий N: …»
        punct = self.chk_punctuation.isChecked()
        dialog = diarizer.format_dialog(words, lambda ws: Punctuator.punctuate_words_with_timing(
            ws, **dict(AppSettings.pauses(), paragraph_pause=None)) if punct
            else " ".join(str(w.get("word", "")) for w in ws))
        if dialog:
            final_text = dialog

        # Передаем текст в систему истории
        file_name = os.path.basename(self.selected_file_path)
        self.transcription_completed.emit(apply_replacements(final_text), words, file_name)
        
        QMessageBox.information(self, "Успех", "Файл распознан и добавлен в «Записи».")
        self.reset_ui_after_work()

    def cancel_transcription(self):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "Отмена", "Вы уверены, что хотите прервать транскрибацию?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker.cancel()

    def reset_ui_after_work(self):
        self.btn_start.setVisible(True)
        self.btn_cancel.setVisible(False)
        self.btn_remove_file.setEnabled(True)
        self.progress_card.setVisible(False)
        self.worker = None
