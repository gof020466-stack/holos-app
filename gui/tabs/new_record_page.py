"""
[v3.2, 18.11.2026, Д2 и Ф1] «Новая запись»: источник — микрофон, звук компьютера, оба или файл.
Микрофон, звук компьютера и «оба» — вкладка записи (MicTab), файл — вкладка файла (FileTab).
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup, QStackedWidget
from PySide6.QtCore import QSize
import qtawesome as qta

from core.settings import AppSettings

SOURCES = [("mic", "Микрофон", "fa5s.microphone"),
           ("system", "Звук компьютера", "fa5s.desktop"),
           ("both", "Оба: созвон", "fa5s.users"),
           ("file", "Файл", "fa5s.file-audio")]


class NewRecordPage(QWidget):
    def __init__(self, mic_tab, file_tab, parent=None):
        super().__init__(parent)
        self.mic_tab = mic_tab
        self.file_tab = file_tab
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Новая запись")
        title.setProperty("class", "TitleLabel")
        layout.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        for key, text, icon in SOURCES:
            b = QPushButton(" " + text)
            b.setObjectName("SourceButton")
            b.setCheckable(True)
            b.setIcon(qta.icon(icon, color="#a0a0ab"))
            b.setIconSize(QSize(15, 15))
            b.clicked.connect(lambda _=False, k=key: self.set_source(k))
            self.group.addButton(b)
            self.buttons[key] = b
            row.addWidget(b)
        row.addStretch(1)
        layout.addLayout(row)

        self.stack = QStackedWidget()
        self.stack.addWidget(mic_tab)
        self.stack.addWidget(file_tab)
        layout.addWidget(self.stack, 1)
        self.set_source(AppSettings.get("record/source"))

    def is_busy(self) -> bool:
        return bool((self.mic_tab.worker and self.mic_tab.worker.isRunning())
                    or (self.file_tab.worker and self.file_tab.worker.isRunning()))

    def set_source(self, key: str):
        if self.is_busy():
            # Во время записи или расшифровки источник не меняется — кнопка возвращается к текущему
            current = "file" if self.stack.currentWidget() is self.file_tab else self.mic_tab.source
            self.buttons[current].setChecked(True)
            return
        if key not in self.buttons:
            key = "mic"
        self.buttons[key].setChecked(True)
        if key == "file":
            self.stack.setCurrentWidget(self.file_tab)
        else:
            self.mic_tab.set_source(key)
            self.stack.setCurrentWidget(self.mic_tab)

    def current_is_file(self) -> bool:
        return self.stack.currentWidget() is self.file_tab
