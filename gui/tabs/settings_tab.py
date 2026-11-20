"""
[v3.2, 18.11.2026, Д2 и Д5] «Настройки» — вкладки «Общие», «Запись», «Распознавание», «Изложение».
Образец вида — Meetily: заголовок, строка пояснения, переключатель справа.
Переключатели — те же объекты, что были флажками во вкладках: логика и сохранение не менялись.
"""
import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QScrollArea, QFrame,
                               QPushButton, QFileDialog)
from PySide6.QtCore import Qt

from core.settings import AppSettings
from core.i18n import tr
from gui.widgets import ToggleSwitch, SettingRow, section_title


def _page(tabs: QTabWidget, title: str) -> QVBoxLayout:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    body = QWidget()
    body.setObjectName("SettingsPage")
    scroll.setWidget(body)
    lay = QVBoxLayout(body)
    lay.setContentsMargins(4, 14, 12, 14)
    lay.setSpacing(8)
    tabs.addTab(scroll, tr(title))  # подписи вкладок i18n сам не видит — перевод явно
    return lay


class SettingsTab(QWidget):
    def __init__(self, mic_tab, dictation_tab, models_tab, set_dark_theme, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        title = QLabel("Настройки")
        title.setProperty("class", "TitleLabel")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("SettingsTabs")
        layout.addWidget(self.tabs, 1)

        # --- Общие ---
        g = _page(self.tabs, "Общие")
        g.addWidget(section_title("Вид и окно"))
        self.sw_dark = ToggleSwitch()
        self.sw_dark.setChecked(AppSettings.get("window/dark_theme"))
        self.sw_dark.toggled.connect(set_dark_theme)
        g.addWidget(SettingRow("Тёмная тема", "Тёмное или светлое оформление окна", self.sw_dark))
        self.sw_tray = ToggleSwitch()
        self.sw_tray.setChecked(AppSettings.get("window/close_to_tray"))
        self.sw_tray.toggled.connect(lambda v: AppSettings.set("window/close_to_tray", v))
        g.addWidget(SettingRow("Крестик прячет окно в трей",
                               "Диктовка и «Ассистент» работают дальше. Выход — меню значка в трее", self.sw_tray))
        # [v3.2.2, 20.11.2026] Проверка обновлений — то же значение, что вопрос при первом запуске
        g.addWidget(section_title("Обновления"))
        self.sw_updates = ToggleSwitch()
        self.sw_updates.setChecked(AppSettings.get("updates/check"))
        self.sw_updates.toggled.connect(lambda v: AppSettings.set("updates/check", v))
        g.addWidget(SettingRow("Проверять обновления",
                               "Раз в сутки при запуске — страница релизов на GitHub. Речь и записи с компьютера не уходят",
                               self.sw_updates))
        g.addWidget(section_title("Заметки Markdown"))
        btn_md = QPushButton("Изменить…")
        btn_md.setProperty("class", "SecondaryButton")
        btn_md.clicked.connect(self.choose_md_dir)
        self.md_row = SettingRow("Папка для «Экспорт в MD»", AppSettings.get("export/md_dir"), btn_md)
        g.addWidget(self.md_row)
        g.addWidget(section_title("Диктовка по клавише"))
        dictation_tab.settings_card.layout().itemAt(0).widget().setVisible(False)  # свой заголовок карточки
        g.addWidget(dictation_tab.settings_card)
        g.addStretch(1)

        # --- Запись ---
        r = _page(self.tabs, "Запись")
        r.addWidget(section_title("Новая запись"))
        r.addWidget(SettingRow("Знаки препинания", "Точки и запятые по паузам, заглавные буквы",
                               mic_tab.chk_punctuation))
        r.addWidget(SettingRow("Голосовые команды",
                               "«начать запись», «стоп запись», «пауза запись», «продолжить запись», «начать диктовку», «Ассистент, …»",
                               mic_tab.chk_voice))
        self.sw_audio = ToggleSwitch()
        self.sw_audio.setChecked(AppSettings.get("mic/save_audio"))
        self.sw_audio.toggled.connect(lambda v: AppSettings.set("mic/save_audio", v))
        r.addWidget(SettingRow("Сохранять звук записи",
                               "Нужен плееру в «Записях» и для «Говорящих». Папка — «О программе»", self.sw_audio))
        r.addStretch(1)

        # --- Распознавание ---
        self.tabs.addTab(models_tab, tr("Распознавание"))

        # --- Изложение ---
        s = _page(self.tabs, "Изложение")
        s.addWidget(section_title("Изложение в Claude — облако"))
        info = QLabel("Изложение делается только по кнопке «Изложение в Claude — облако» в «Записях». "
                      "Программа вставляет текст в окно Claude Desktop, а Claude отправляет его в облако Anthropic. "
                      "Без нажатия кнопки текст не покидает этот компьютер.")
        info.setWordWrap(True)
        info.setObjectName("SettingDesc")
        s.addWidget(info)
        self.sw_ask = ToggleSwitch()
        self.sw_ask.setChecked(AppSettings.get("summary/ask"))
        self.sw_ask.toggled.connect(lambda v: AppSettings.set("summary/ask", v))
        s.addWidget(SettingRow("Спрашивать перед отправкой",
                               "Окно «Текст уйдёт в облако» перед каждой отправкой", self.sw_ask))
        s.addWidget(SettingRow("Куда уходит текст",
                               "Окно Claude Desktop. Окна нет — запрос остаётся в буфере обмена", QLabel("Claude")))
        s.addStretch(1)

    def set_ask(self, ask: bool):
        """Флажок «Больше не спрашивать» в окне предупреждения → переключатель здесь."""
        self.sw_ask.blockSignals(True)
        self.sw_ask.setChecked(ask)
        self.sw_ask.blockSignals(False)

    def set_dark(self, dark: bool):
        self.sw_dark.blockSignals(True)
        self.sw_dark.setChecked(dark)
        self.sw_dark.blockSignals(False)

    def choose_md_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Папка для заметок Markdown", AppSettings.get("export/md_dir"))
        if folder:
            folder = os.path.normpath(folder)
            AppSettings.set("export/md_dir", folder)
            self.md_row.lbl_desc.setText(folder)
