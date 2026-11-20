import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QComboBox, QCheckBox, QFrame, 
                             QTextEdit, QMessageBox)
from PySide6.QtCore import Qt
import qtawesome as qta
from core.mic_recorder import get_input_devices
from gui.widgets import ToggleSwitch, SettingRow

logger = logging.getLogger("DictationTab")

AVAILABLE_HOTKEYS = [
    "F8",
    "F9",
    "F10",
    "F12",
    "ctrl+shift+d",
    "alt+d"
]

class DictationTab(QWidget):
    """
    Вкладка настройки и тестирования режима глобальной диктовки по горячим клавишам.
    """
    def __init__(self, dictation_manager, parent=None):
        super().__init__(parent)
        self.dictation_manager = dictation_manager
        self.setup_ui()
        self.refresh_devices()
        self._connect_signals()
        self.update_service_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 1. Заголовок
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        
        title = QLabel("Диктовка")
        title.setProperty("class", "TitleLabel")

        subtitle = QLabel("Текст голосом в любое окно: Telegram, Word, браузер, заметку. Клавишу и микрофон меняют в «Настройки → Общие»")
        subtitle.setWordWrap(True)
        subtitle.setProperty("class", "SubtitleLabel")
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addLayout(header_layout)

        # 2. Карточка статуса службы
        self.status_card = QFrame()
        self.status_card.setProperty("class", "CardFrame")
        status_layout = QHBoxLayout(self.status_card)
        status_layout.setContentsMargins(15, 15, 15, 15)
        
        self.status_icon = QLabel()
        self.status_icon.setPixmap(qta.icon("fa5s.broadcast-tower", color="#10b981").pixmap(32, 32))
        status_layout.addWidget(self.status_icon)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        self.lbl_service_title = QLabel("Служба диктовки активна")
        self.lbl_service_title.setProperty("class", "HeaderLabel")
        
        self.lbl_service_desc = QLabel("В любом окне: клавиша — говорите — клавиша ещё раз")
        self.lbl_service_desc.setStyleSheet("color: #a0a0ab; font-size: 12px;")
        
        info_layout.addWidget(self.lbl_service_title)
        info_layout.addWidget(self.lbl_service_desc)
        status_layout.addLayout(info_layout, 1)

        self.btn_toggle_service = QPushButton("Выключить")
        self.btn_toggle_service.setProperty("class", "SecondaryButton")
        self.btn_toggle_service.clicked.connect(self.toggle_service)
        status_layout.addWidget(self.btn_toggle_service)

        layout.addWidget(self.status_card)

        # 3. Карточка параметров и настроек
        settings_card = QFrame()
        settings_card.setProperty("class", "CardFrame")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(18, 16, 18, 16)
        settings_layout.setSpacing(12)

        lbl_settings = QLabel("Диктовка по клавише")
        lbl_settings.setProperty("class", "HeaderLabel")
        settings_layout.addWidget(lbl_settings)

        # Выбор микрофона
        mic_row = QHBoxLayout()
        mic_row.setSpacing(12)
        lbl_mic = QLabel("Микрофон:")
        lbl_mic.setStyleSheet("font-size: 13px; font-weight: 500;")
        
        self.cb_devices = QComboBox()
        self.cb_devices.setStyleSheet("QComboBox { min-width: 250px; }")
        # [v3] Высота как во вкладке записи: в тесной карточке строка срезалась наполовину (31.10.2026)
        self.cb_devices.setMinimumHeight(34)
        self.cb_devices.currentIndexChanged.connect(self.on_device_changed)

        self.btn_refresh_mics = QPushButton()
        self.btn_refresh_mics.setFixedSize(34, 34)
        self.btn_refresh_mics.setIcon(qta.icon("fa5s.sync-alt", color="#e2e2e5"))
        self.btn_refresh_mics.setProperty("class", "SecondaryButton")
        self.btn_refresh_mics.clicked.connect(self.refresh_devices)
        
        mic_row.addWidget(lbl_mic)
        mic_row.addWidget(self.cb_devices, 1)
        mic_row.addWidget(self.btn_refresh_mics)
        settings_layout.addLayout(mic_row)

        # Выбор клавиши
        hotkey_row = QHBoxLayout()
        hotkey_row.setSpacing(12)
        lbl_choose = QLabel("Клавиша диктовки:")
        lbl_choose.setStyleSheet("font-size: 13px; font-weight: 500;")
        
        self.cb_hotkeys = QComboBox()
        self.cb_hotkeys.setStyleSheet("QComboBox { min-width: 160px; }")
        self.cb_hotkeys.setMinimumHeight(34)
        for hk in AVAILABLE_HOTKEYS:
            display_name = f"{hk} (По умолчанию)" if hk == "F8" else hk
            self.cb_hotkeys.addItem(display_name, hk)
        # [v3] Показываем сохранённую клавишу
        saved_idx = self.cb_hotkeys.findData(self.dictation_manager.current_hotkey)
        if saved_idx >= 0:
            self.cb_hotkeys.setCurrentIndex(saved_idx)
        self.cb_hotkeys.currentIndexChanged.connect(self.on_hotkey_changed)
        
        hotkey_row.addWidget(lbl_choose)
        hotkey_row.addWidget(self.cb_hotkeys)
        hotkey_row.addStretch(1)
        settings_layout.addLayout(hotkey_row)

        # [v3.2, 18.11.2026, Д5] Переключатели: заголовок, строка пояснения, переключатель справа
        self.chk_auto_insert = ToggleSwitch()
        self.chk_auto_insert.setChecked(self.dictation_manager.auto_insert)
        self.chk_auto_insert.toggled.connect(self.on_auto_insert_toggled)

        self.chk_auto_punctuate = ToggleSwitch()
        self.chk_auto_punctuate.setChecked(self.dictation_manager.auto_punctuate)
        self.chk_auto_punctuate.toggled.connect(self.on_auto_punctuate_toggled)

        self.chk_sound = ToggleSwitch()
        self.chk_sound.setChecked(self.dictation_manager.sound_feedback)
        self.chk_sound.toggled.connect(self.on_sound_toggled)

        self.chk_restore_clipboard = ToggleSwitch()
        self.chk_restore_clipboard.setChecked(self.dictation_manager.restore_clipboard)
        self.chk_restore_clipboard.toggled.connect(
            lambda checked: self.dictation_manager.set_option("restore_clipboard", checked))

        self.chk_new_paragraph = ToggleSwitch()
        self.chk_new_paragraph.setChecked(self.dictation_manager.new_paragraph)
        self.chk_new_paragraph.toggled.connect(
            lambda checked: self.dictation_manager.set_option("new_paragraph", checked))

        for title, desc, switch in (
                ("Вставлять текст в окно", "Текст встаёт туда, где стоит курсор (Ctrl+V)", self.chk_auto_insert),
                ("Знаки препинания", "Точки и запятые по паузам, заглавные буквы", self.chk_auto_punctuate),
                ("Звуковой сигнал", "Короткий звук при старте и стопе диктовки", self.chk_sound),
                ("Вернуть буфер обмена", "После вставки в буфере — то, что было до диктовки", self.chk_restore_clipboard),
                ("Каждая диктовка — новый абзац", "После текста — пустая строка", self.chk_new_paragraph)):
            settings_layout.addWidget(SettingRow(title, desc, switch))

        # [v3.2, Д2] Карточку параметров показывает «Настройки → Общие»; здесь — состояние, памятка и проба
        self.settings_card = settings_card

        # 4. Карточка инструкции и поля быстрого теста
        test_card = QFrame()
        test_card.setProperty("class", "CardFrame")
        test_layout = QVBoxLayout(test_card)
        test_layout.setContentsMargins(18, 16, 18, 16)
        test_layout.setSpacing(10)

        lbl_test = QLabel("Проверка работы и быстрая инструкция:")
        lbl_test.setProperty("class", "HeaderLabel")
        test_layout.addWidget(lbl_test)

        guide_text = QLabel(
            "<b>Как пользоваться:</b><br>"
            "1. Модель загружается сама при запуске (последняя использованная; сменить — <b>«Настройки → Распознавание»</b>).<br>"
            "2. Перейдите в <b>любое приложение</b> (Telegram, Word, браузер, Notepad) или кликните в поле ниже.<br>"
            "3. Нажмите выбранную горячую клавишу (раздастся короткий сигнал и появится плавающий оверлей).<br>"
            "4. Произнесите фразу и нажмите клавишу ещё раз — текст вставится в поле ввода.<br>"
            "5. Закрытие окна сворачивает программу в трей — диктовка продолжает работать."
        )
        guide_text.setStyleSheet("color: #a0a0ab; font-size: 12px; line-height: 18px;")
        test_layout.addWidget(guide_text)

        self.txt_test_input = QTextEdit()
        self.txt_test_input.setPlaceholderText("Кликните сюда и нажмите горячую клавишу, чтобы проверить диктовку прямо сейчас...")
        self.txt_test_input.setMaximumHeight(85)
        self.txt_test_input.setStyleSheet("QTextEdit { font-size: 13px; }")
        test_layout.addWidget(self.txt_test_input)

        layout.addWidget(test_card)
        layout.addStretch(1)

    def refresh_devices(self):
        """
        Сканирует и наполняет список доступных аудиовходов.
        """
        self.cb_devices.blockSignals(True)
        self.cb_devices.clear()
        
        devices = get_input_devices()
        if not devices:
            self.cb_devices.addItem("Микрофоны не найдены", None)
            self.dictation_manager.device_id = None
            self.cb_devices.blockSignals(False)
            return

        selected_idx = 0
        for i, dev in enumerate(devices):
            default_tag = " (по умолчанию)" if dev["is_default"] else ""
            self.cb_devices.addItem(f"{dev['name']}{default_tag}", dev["id"])
            if dev["is_default"]:
                selected_idx = i

        self.cb_devices.setCurrentIndex(selected_idx)
        self.dictation_manager.device_id = self.cb_devices.currentData()
        self.cb_devices.blockSignals(False)
        logger.info(f"Диктовка использует микрофон: ID {self.dictation_manager.device_id}")

    def on_device_changed(self, index: int):
        dev_id = self.cb_devices.itemData(index)
        self.dictation_manager.device_id = dev_id
        logger.info(f"Микрофон диктовки переключен на: ID {dev_id}")

    def _connect_signals(self):
        self.dictation_manager.error_occurred.connect(self.on_dictation_error)

    def toggle_service(self):
        self.dictation_manager.set_enabled(not self.dictation_manager.is_active)
        self.update_service_ui()

    def update_service_ui(self):
        """
        [v3] Приводит карточку статуса к фактическому состоянию (оно сохраняется между запусками).
        """
        if self.dictation_manager.is_active:
            self.lbl_service_title.setText("Диктовка по клавише включена")
            self.lbl_service_title.setStyleSheet("color: #10b981;")
            self.status_icon.setPixmap(qta.icon("fa5s.broadcast-tower", color="#10b981").pixmap(32, 32))
            self.btn_toggle_service.setText("Выключить")
        else:
            self.lbl_service_title.setText("Диктовка по клавише выключена")
            self.lbl_service_title.setStyleSheet("color: #a0a0ab;")
            self.status_icon.setPixmap(qta.icon("fa5s.pause-circle", color="#a0a0ab").pixmap(32, 32))
            self.btn_toggle_service.setText("Включить")

    def on_hotkey_changed(self, index: int):
        hotkey = self.cb_hotkeys.itemData(index)
        if hotkey:
            self.dictation_manager.set_hotkey(hotkey)

    def on_auto_insert_toggled(self, checked: bool):
        self.dictation_manager.set_option("auto_insert", checked)

    def on_auto_punctuate_toggled(self, checked: bool):
        self.dictation_manager.set_option("auto_punctuate", checked)

    def on_sound_toggled(self, checked: bool):
        self.dictation_manager.set_option("sound_feedback", checked)

    def on_dictation_error(self, err_msg: str):
        QMessageBox.warning(self, "Диктовка", err_msg)
