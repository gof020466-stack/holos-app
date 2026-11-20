from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QCheckBox, QListWidget, QFrame
from PySide6.QtCore import Qt

from core.settings import AppSettings
from core.local_commands import MUSIC_COMMANDS
from gui.widgets import ToggleSwitch, SettingRow, Collapsible


class AssistantTab(QWidget):
    """
    [v3, 03.11.2026] Вкладка «Ассистент»: включено ли прослушивание, как пользоваться,
    что услышано за сеанс и куда ушло.
    """
    def __init__(self, voice_checkbox: QCheckBox, parent=None):
        super().__init__(parent)
        self.voice_checkbox = voice_checkbox  # флажок вкладки «Запись с микрофона» — единственный источник состояния

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(14)

        title = QLabel("Ассистент — работа голосом без кнопок")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(title)

        # [v3.2, 18.11.2026, Д6] Одно состояние: подпись + переключатель (было — кружок и отдельный флажок)
        self.chk_listen = ToggleSwitch()
        self.chk_listen.setChecked(voice_checkbox.isChecked())
        self.chk_listen.toggled.connect(voice_checkbox.setChecked)
        voice_checkbox.toggled.connect(self._sync)
        self.state_row = SettingRow("", "Слово «Ассистент» и голосовые команды. F8 работает всегда", self.chk_listen)
        self.lbl_state = self.state_row.lbl_title
        layout.addWidget(self.state_row)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        music = ", ".join(sorted({k for k in MUSIC_COMMANDS if " " not in k}))
        help_text = QLabel(
            "<b>Команда для Claude:</b> «Ассистент» → сигнал и окно «Ассистент слушает» → фраза → "
            f"пауза {AppSettings.get('assistant/silence'):g} с → сигнал. Фраза уходит в чат Claude и отправляется.<br>"
            "Одним духом: «Ассистент, включи вальсы» — быстрее, но точность ниже.<br><br>"
            f"<b>Музыка — VOSK сам, без Claude:</b> «Ассистент, …» + {music}.<br><br>"
            "<b>Важно:</b> слово «Ассистент» в обычной речи тоже срабатывает, если перед ним пауза. "
            "Диктуете длинный текст — выключите прослушивание.")
        help_text.setWordWrap(True)
        help_text.setTextFormat(Qt.RichText)
        help_text.setStyleSheet("font-size: 13px;")
        card_layout.addWidget(help_text)
        layout.addWidget(Collapsible("Как пользоваться", card))

        lbl_log = QLabel("Услышано за сеанс")
        lbl_log.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(lbl_log)
        self.log = QListWidget()
        layout.addWidget(self.log, 1)

        self._sync(voice_checkbox.isChecked())

    def _sync(self, checked: bool):
        self.chk_listen.blockSignals(True)
        self.chk_listen.setChecked(checked)
        self.chk_listen.blockSignals(False)
        self.lbl_state.setText("Слушаю «Ассистент»" if checked else "Прослушивание выключено")
        self.lbl_state.setStyleSheet("font-size: 15px; font-weight: 600; color: %s;" % ("#22c55e" if checked else "#8a8a93"))

    def add_event(self, text: str, target: str):
        self.log.insertItem(0, f"{datetime.now():%H:%M:%S}  «{text}»  →  {target}")
