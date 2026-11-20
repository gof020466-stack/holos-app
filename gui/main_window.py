import os
import logging
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                             QPushButton, QStackedWidget, QFrame, QLabel, QButtonGroup,
                             QApplication, QSystemTrayIcon, QMenu)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
import qtawesome as qta

from core.vosk_manager import VoskManager
from core.dictation_manager import DictationManager
from core.settings import AppSettings, DEFAULT_MODEL_ID
from core.voice_commands import beep
from gui.floating_overlay import FloatingOverlay
from gui.styles import DARK_THEME_STYLES, LIGHT_THEME_STYLES
from gui.tabs.file_tab import FileTab
from gui.tabs.mic_tab import MicTab
from gui.tabs.dictation_tab import DictationTab
from gui.tabs.models_tab import ModelsTab
from gui.tabs.history_tab import HistoryTab
from gui.tabs.assistant_tab import AssistantTab
from gui.tabs.about_tab import AboutTab
from gui.tabs.new_record_page import NewRecordPage
from gui.tabs.settings_tab import SettingsTab
from core.i18n import tr

logger = logging.getLogger("MainWindow")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Голос")
        self.setMinimumSize(980, 700)
        self.resize(1060, 740)
        self.setWindowIcon(qta.icon("fa5s.wave-square", color="#6366f1"))

        # [v3] Тема запоминается между запусками
        self.is_dark_theme = AppSettings.get("window/dark_theme")
        self._really_quit = False

        # Применяем стартовую Fluent QSS-стилизацию
        QApplication.instance().setStyleSheet(DARK_THEME_STYLES if self.is_dark_theme else LIGHT_THEME_STYLES)

        # Инициализируем VoskManager с путями на диске D
        self.vosk_manager = VoskManager()

        # Инициализируем менеджер глобальной диктовки и плавающий оверлей
        self.dictation_manager = DictationManager(self.vosk_manager, parent=self)
        self.overlay = FloatingOverlay()

        self.setup_ui()
        self.setup_dictation_connections()
        self.setup_tray()
        if not self.is_dark_theme:
            self.on_tab_changed(0)
        self.autoload_model()
        logger.info("Главное окно успешно инициализировано.")

    def autoload_model(self):
        """
        [v3] Загружает последнюю модель (по умолчанию — лёгкую русскую) в фоне сразу при запуске:
        диктовка готова без захода во вкладку «Модели».
        """
        if not AppSettings.get("model/autoload"):
            return
        available = {m["id"] for m in self.vosk_manager.scan_models()}
        model_id = AppSettings.get("model/last_id")
        if model_id not in available:
            model_id = DEFAULT_MODEL_ID if DEFAULT_MODEL_ID in available else None
        if model_id:
            logger.info(f"Автозагрузка модели: {model_id}")
            self.models_tab.load_model_by_id(model_id, silent=True)

    def setup_tray(self):
        """
        [v3] Значок в трее: закрытие окна прячет программу, глобальная диктовка продолжает работать.
        """
        self.tray = QSystemTrayIcon(qta.icon("fa5s.wave-square", color="#6366f1"), self)
        self.tray.setToolTip("Голос — диктовка по горячей клавише")
        menu = QMenu()
        act_show = menu.addAction("Открыть окно")
        act_show.triggered.connect(self.show_from_tray)
        self.act_dictation = menu.addAction("Диктовка включена")
        self.act_dictation.setCheckable(True)
        self.act_dictation.setChecked(self.dictation_manager.is_active)
        self.act_dictation.toggled.connect(self.on_tray_dictation_toggled)
        # [v3, 03.11.2026] Постоянное прослушивание: «Ассистент» и остальные голосовые команды.
        # Тот же переключатель, что флажок во вкладке «Запись с микрофона»
        self.act_listen = menu.addAction("Слушать «Ассистент»")
        self.act_listen.setCheckable(True)
        self.act_listen.setChecked(self.mic_tab.chk_voice.isChecked())
        self.act_listen.toggled.connect(self.mic_tab.chk_voice.setChecked)
        self.mic_tab.chk_voice.toggled.connect(self.on_listen_toggled)
        self.update_tray_state()
        menu.addSeparator()
        act_quit = menu.addAction("Выход")
        act_quit.triggered.connect(self.quit_app)
        self.tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.show_from_tray() if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
        self.tray.show()

    def update_tray_state(self):
        """
        [v3, 03.11.2026] Состояние видно по значку: зелёный — слушаю «Ассистент», серый — не слушаю.
        """
        listening = self.mic_tab.chk_voice.isChecked()
        self.tray.setIcon(qta.icon("fa5s.wave-square", color="#22c55e" if listening else "#8a8a93"))
        self.tray.setToolTip("Голос — слушаю «Ассистент»" if listening
                             else "Голос — прослушивание выключено (F8 работает)")

    def on_capture_started(self, *_):
        self.tray.setIcon(qta.icon("fa5s.microphone", color="#ef4444"))

    def on_listen_toggled(self, checked: bool):
        self.act_listen.blockSignals(True)
        self.act_listen.setChecked(checked)
        self.act_listen.blockSignals(False)
        self.update_tray_state()
        self.tray.showMessage("Голос",
                              "Слушаю «Ассистент»" if checked else "Прослушивание выключено",
                              QSystemTrayIcon.Information, 2000)

    def on_tray_dictation_toggled(self, checked: bool):
        self.dictation_manager.set_enabled(checked)
        self.dictation_tab.update_service_ui()

    def show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        self._really_quit = True
        self.close()

    def setup_ui(self):
        # Центральный виджет и главный горизонтальный слой
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # -------------------------------------------------------------
        # 1. ЛЕВАЯ ПАНЕЛЬ МЕНЮ (SIDEBAR)
        # -------------------------------------------------------------
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        # [v3.2, 18.11.2026] Меню уже на четверть (было 240): главное — окно текста.
        self.sidebar.setFixedWidth(180)

        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 20, 10, 20)
        sidebar_layout.setSpacing(8)

        # Логотип и Название приложения
        logo_layout = QHBoxLayout()
        logo_layout.setContentsMargins(5, 0, 5, 20)
        logo_layout.setSpacing(10)
        
        logo_icon = QLabel()
        logo_icon.setPixmap(qta.icon("fa5s.wave-square", color="#6366f1").pixmap(28, 28))
        
        logo_text = QLabel("Голос")
        logo_text.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")
        
        logo_layout.addWidget(logo_icon)
        logo_layout.addWidget(logo_text, 1)
        sidebar_layout.addLayout(logo_layout)

        # [v3.2, 18.11.2026, Д2] Меню по задачам: «Записи» первым, «Новая запись», «Диктовка», «Ассистент»;
        # внизу — главное действие (Д1) и «Настройки». Было: 7 пунктов вперемешку — режимы, история, «Модели Vosk»
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        self.menu_buttons = {}

        def menu_button(page: int, text: str):
            btn = QPushButton("  " + text)
            btn.setProperty("class", "MenuButton")
            btn.setCheckable(True)
            btn.setIcon(qta.icon(self.PAGE_ICONS[page], color="#a0a0ab"))
            btn.setIconSize(QSize(18, 18))
            self.btn_group.addButton(btn, page)
            self.menu_buttons[page] = btn
            return btn

        for page, text in ((self.PAGE_RECORDS, "Записи"), (self.PAGE_NEW, "Новая запись"),
                           (self.PAGE_DICTATION, "Диктовка"), (self.PAGE_ASSISTANT, "Ассистент")):
            sidebar_layout.addWidget(menu_button(page, text))
        self.menu_buttons[self.PAGE_RECORDS].setChecked(True)

        sidebar_layout.addStretch(1)

        # [v3.2, Д1] Главное действие всегда на виду: красная «Начать запись» и «Открыть файл»
        self.btn_side_record = QPushButton("  Начать запись")
        self.btn_side_record.setObjectName("SidebarRecord")
        self.btn_side_record.setProperty("recording", False)
        self.btn_side_record.setIcon(qta.icon("fa5s.circle", color="#ffffff"))
        self.btn_side_record.setIconSize(QSize(14, 14))
        self.btn_side_record.clicked.connect(self.on_side_record)
        sidebar_layout.addWidget(self.btn_side_record)

        self.btn_side_file = QPushButton("  Открыть файл")
        self.btn_side_file.setObjectName("SidebarFile")
        self.btn_side_file.setIcon(qta.icon("fa5s.folder-open", color="#a0a0ab"))
        self.btn_side_file.setIconSize(QSize(16, 16))
        self.btn_side_file.clicked.connect(self.on_side_file)
        sidebar_layout.addWidget(self.btn_side_file)
        sidebar_layout.addSpacing(10)

        sidebar_layout.addWidget(menu_button(self.PAGE_SETTINGS, "Настройки"))
        sidebar_layout.addWidget(menu_button(self.PAGE_ABOUT, "О программе"))

        # Метка версии приложения внизу сайдбара
        from core.updates import VERSION
        from core.i18n import tr
        lbl_version = QLabel(f"{tr('Версия')} {VERSION}")
        lbl_version.setStyleSheet("color: #52525b; font-size: 11px; font-weight: 500;")
        lbl_version.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(lbl_version)

        main_layout.addWidget(self.sidebar)

        # -------------------------------------------------------------
        # 2. ПРАВАЯ ПАНЕЛЬ С СЕКЦИЯМИ (QSTACKEDWIDGET)
        # -------------------------------------------------------------
        self.stacked_widget = QStackedWidget()

        # Создаем вкладки
        self.file_tab = FileTab(self.vosk_manager)
        self.mic_tab = MicTab(self.vosk_manager)
        self.dictation_tab = DictationTab(self.dictation_manager)
        self.models_tab = ModelsTab(self.vosk_manager)
        self.history_tab = HistoryTab(self.vosk_manager)
        self.new_record_page = NewRecordPage(self.mic_tab, self.file_tab)
        self.assistant_tab = AssistantTab(self.mic_tab.chk_voice)
        self.settings_tab = SettingsTab(self.mic_tab, self.dictation_tab, self.models_tab, self.set_dark_theme)
        self.about_tab = AboutTab()

        # Порядок — номера страниц PAGE_*
        for page in (self.history_tab, self.new_record_page, self.dictation_tab, self.assistant_tab,
                     self.settings_tab, self.about_tab):
            self.stacked_widget.addWidget(page)

        main_layout.addWidget(self.stacked_widget, 1)

        # -------------------------------------------------------------
        # 3. ПОДКЛЮЧЕНИЕ СИГНАЛОВ НАВИГАЦИИ
        # -------------------------------------------------------------
        # Переключение вкладок по нажатию на кнопки меню
        self.btn_group.idClicked.connect(self.switch_tab)

        # Автоматическая передача расшифрованного текста в Историю
        # [v3] Для файлов сохраняем полный путь к медиа — нужен плееру в истории
        self.file_tab.transcription_completed.connect(
            lambda text, words, name: self.on_transcription_completed(text, words, name, self.file_tab.selected_file_path))
        self.mic_tab.transcription_completed.connect(self.on_transcription_completed)
        # [v3] Команда «начать запись»: окно поверх, вкладка записи
        self.mic_tab.show_requested.connect(lambda: (self.show_from_tray(), self.show_recorder()))
        # [v3.2] Кнопка в меню повторяет состояние кнопки записи
        self.mic_tab.recording_changed.connect(self.on_recording_changed)
        # [v3.2] «Записи» → «Говорящие»: звук записи — на страницу файла с разделением по говорящим
        self.history_tab.speakers_requested.connect(self.on_speakers_requested)
        self.history_tab.summary_ask_changed.connect(self.settings_tab.set_ask)
        # [v3] «продолжить запись» — дописать в выбранную запись Истории; «стоп запись» — остановить
        self.mic_tab.busy_elsewhere = lambda: self.history_tab.append_worker is not None
        # [v3, 12.11.2026] Пауза записи: черновик — сразу в Историю
        self.mic_tab.save_draft = self.history_tab.save_mic_draft
        self.mic_tab.voice_listener.continue_requested.connect(self.on_voice_continue)
        self.mic_tab.voice_listener.stop_requested.connect(self.history_tab.stop_voice_append)
        # [v3] «начать диктовку» … «стоп запись» — то же, что F8 … F8, без рук
        self.mic_tab.voice_listener.dictate_requested.connect(self.on_voice_dictate)
        self.mic_tab.voice_listener.stop_requested.connect(self.dictation_manager.stop_dictation)
        # [v3, 03.11.2026] «Ассистент, …» — фраза в окно Claude
        self.mic_tab.voice_listener.assistant_requested.connect(self.on_voice_assistant)

        # Обновление иконок меню при переключении
        self.stacked_widget.currentChanged.connect(self.on_tab_changed)

        # Обновляем иконки для стартовой темы
        self.on_tab_changed(0)

    # -----------------------------------------------------------------
    # [v3.2, 18.11.2026] Страницы и главное действие в меню
    # -----------------------------------------------------------------
    PAGE_RECORDS, PAGE_NEW, PAGE_DICTATION, PAGE_ASSISTANT, PAGE_SETTINGS, PAGE_ABOUT = range(6)
    PAGE_ICONS = {0: "fa5s.list-ul", 1: "fa5s.plus-circle", 2: "fa5s.bolt", 3: "fa5s.headset",
                  4: "fa5s.cog", 5: "fa5s.info-circle"}

    def show_recorder(self):
        """Страница «Новая запись» с источником записи (не «Файл»)."""
        self.switch_tab(self.PAGE_NEW)
        if self.new_record_page.current_is_file():
            self.new_record_page.set_source(self.mic_tab.source)

    def on_side_record(self):
        if self.mic_tab.worker and self.mic_tab.worker.isRunning():
            self.mic_tab.stop_recording()
            return
        if self.file_tab.worker and self.file_tab.worker.isRunning():
            self.switch_tab(self.PAGE_NEW)
            return
        self.show_recorder()
        if self.history_tab.append_worker is None:
            self.mic_tab.start_recording()

    def on_side_file(self):
        self.switch_tab(self.PAGE_NEW)
        if self.new_record_page.is_busy():
            return
        self.new_record_page.set_source("file")
        self.file_tab.browse_file()

    def on_speakers_requested(self, path: str):
        if not path or self.new_record_page.is_busy():
            return
        self.switch_tab(self.PAGE_NEW)
        self.new_record_page.set_source("file")
        self.file_tab.open_for_speakers(path)

    def on_recording_changed(self, recording: bool):
        b = self.btn_side_record
        b.setText(tr("  Стоп запись") if recording else tr("  Начать запись"))
        b.setIcon(qta.icon("fa5s.stop" if recording else "fa5s.circle", color="#ffffff"))
        b.setProperty("recording", recording)
        b.style().unpolish(b)
        b.style().polish(b)

    def set_dark_theme(self, dark: bool):
        if dark != self.is_dark_theme:
            self.toggle_theme()

    def setup_dictation_connections(self):
        """
        Подключает сигналы DictationManager к оверлею и системе приложения.
        """
        self.dictation_manager.dictation_started.connect(self.overlay.show_listening)
        self.dictation_manager.partial_text_updated.connect(self.overlay.update_text)
        self.dictation_manager.final_chunk_received.connect(self.overlay.update_text)
        self.dictation_manager.volume_changed.connect(self.overlay.set_volume)
        self.dictation_manager.dictation_finished.connect(self.on_dictation_finished)
        self.dictation_manager.error_occurred.connect(self.overlay.show_error)
        # [v3, 03.11.2026] «Ассистент»: значок трея красный, пока идёт запись фразы; журнал во вкладке
        self.dictation_manager.dictation_started.connect(self.on_capture_started)
        self.dictation_manager.dictation_finished.connect(lambda *_: self.update_tray_state())
        self.dictation_manager.assistant_sent.connect(lambda text, target: self.assistant_tab.add_event(text, target))

    def on_dictation_finished(self, text: str, pasted: bool):
        """
        Обработка завершения диктовки.
        """
        if text:
            if pasted:
                self.overlay.show_success("Вставлено в окно!")
            else:
                self.overlay.show_success("Скопировано в буфер!")
            # Обновляем список истории
            self.history_tab.load_history()
        else:
            self.overlay.hide()

    def on_voice_dictate(self):
        dm = self.dictation_manager
        if (dm.is_dictating or (dm.worker and dm.worker.isRunning())
                or (self.mic_tab.worker and self.mic_tab.worker.isRunning())
                or self.history_tab.append_worker is not None):
            return
        dm.start_dictation()

    def on_voice_assistant(self, tail: str):
        """
        «Ассистент» отдельно — ждём фразу основной моделью до паузы;
        «Ассистент, включи …» одним духом — отправляем остаток, как его услышала модель команд.
        """
        dm = self.dictation_manager
        if (dm.is_dictating or (dm.worker and dm.worker.isRunning())
                or (self.mic_tab.worker and self.mic_tab.worker.isRunning())
                or self.history_tab.append_worker is not None):
            return
        if tail:
            beep(True)
            dm.assistant_sent.connect(self._show_tail, Qt.SingleShotConnection)
            dm.send_to_assistant(tail)
        else:
            dm.start_dictation(assistant=True)

    def _show_tail(self, text: str, target: str):
        self.overlay.show_command(text, "→ " + target)

    def on_voice_continue(self):
        if self.mic_tab.worker and self.mic_tab.worker.isRunning():
            return
        self.show_from_tray()
        self.switch_tab(self.PAGE_RECORDS)
        self.history_tab.start_voice_append()

    def switch_tab(self, index: int):
        """
        Переключает активный виджет в QStackedWidget и помечает нужную кнопку меню.
        """
        self.stacked_widget.setCurrentIndex(index)
        button = self.btn_group.button(index)
        if button:
            button.blockSignals(True)
            button.setChecked(True)
            button.blockSignals(False)

    def toggle_theme(self):
        """
        Переключает тему между светлой и темной.
        """
        self.is_dark_theme = not self.is_dark_theme
        AppSettings.set("window/dark_theme", self.is_dark_theme)

        QApplication.instance().setStyleSheet(DARK_THEME_STYLES if self.is_dark_theme else LIGHT_THEME_STYLES)
        self.settings_tab.set_dark(self.is_dark_theme)
        # Обновляем состояние иконок
        self.on_tab_changed(self.stacked_widget.currentIndex())

    def on_tab_changed(self, index: int):
        """
        Меняет цвета иконок для активной кнопки в сайдбаре при смене вкладки.
        """
        muted_color = "#a0a0ab" if self.is_dark_theme else "#55555d"
        for page, btn in self.menu_buttons.items():
            btn.setIcon(qta.icon(self.PAGE_ICONS[page], color="#6366f1" if page == index else muted_color))
        self.btn_side_file.setIcon(qta.icon("fa5s.folder-open", color=muted_color))

    def on_transcription_completed(self, text: str, words: list, source_name: str, media_path: str = None,
                                   item_id: int = 0):
        """
        Вызывается при получении расшифровки из микрофона или файла.
        [v3, 12.11.2026] item_id — черновик паузы записи с микрофона (0 — новой записи).
        """
        # Добавляем в историю
        self.history_tab.add_transcript(text, words, source_name, media_path, item_id)
        # Переключаемся на «Записи» для показа результата
        self.switch_tab(self.PAGE_RECORDS)

    def closeEvent(self, event):
        """
        [v3] Крестик прячет окно в трей (диктовка работает дальше).
        Полный выход — пункт «Выход» в меню трея.
        """
        tray_ok = hasattr(self, 'tray') and QSystemTrayIcon.isSystemTrayAvailable()
        if not self._really_quit and tray_ok and AppSettings.get("window/close_to_tray"):
            event.ignore()
            self.hide()
            if not getattr(self, "_tray_hint_shown", False):
                self.tray.showMessage("Голос",
                                      "Программа работает в трее. Диктовка — по горячей клавише. Выход — через меню значка.",
                                      QSystemTrayIcon.Information, 3000)
                self._tray_hint_shown = True
            return

        # При выходе корректно снимаем перехват горячих клавиш (сохранённая настройка не меняется)
        if hasattr(self, 'dictation_manager'):
            self.dictation_manager.shutdown()
        if hasattr(self, 'history_tab'):
            self.history_tab.shutdown()
        if hasattr(self, 'mic_tab'):
            self.mic_tab.shutdown()
        if hasattr(self, 'overlay'):
            self.overlay.close()
        if hasattr(self, 'tray'):
            self.tray.hide()
        super().closeEvent(event)
        QApplication.instance().quit()
