"""
[v3, 12.11.2026] Вкладка «О программе»: что это за программа, чья, какая лицензия,
где лежат данные, журнал, записи и модели. Образец — страница «О программе» в Handy.
Человек сразу видит, что это за программа, откуда она, куда она пишет и какая у неё лицензия.
"""
import os
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
                               QFrame, QFileDialog, QScrollArea, QMessageBox, QComboBox)
from PySide6.QtCore import Qt, QUrl, QProcess
from PySide6.QtGui import QDesktopServices
import qtawesome as qta

from core.settings import AppSettings, SETTINGS_PATH
from core import i18n
from core.vosk_manager import DEFAULT_MODELS_PATH

APP_NAME = "Голос"
# [12.11.2026] Канал — YouTube; «Поддержать» скрыта, пока нет способа оплаты (SUPPORT_URL пустой — кнопки нет)
CHANNEL_URL = "https://www.youtube.com/@BuckNeverBarks"
SUPPORT_URL = ""
from core import updates
APP_VERSION = f"{updates.VERSION} ({updates.VERSION_DATE})"
APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.dirname(SETTINGS_PATH)
LOG_FILE = os.path.join(DATA_DIR, "app.log")

# Что внутри и на каких условиях (проверено 12.11.2026 по метаданным пакетов и карточкам моделей)
CREDITS = [
    ("sherpa-onnx (k2-fsa)", "движок распознавания", "Apache 2.0"),
    ("Vosk (Alpha Cephei)", "потоковая модель 0.54 и модель голосовых команд", "Apache 2.0"),
    ("GigaAM v3 (Sber)", "русская модель со знаками препинания", "MIT"),
    ("Parakeet Ultra (Moondream · NVIDIA Parakeet TDT v3 · ONNX: mrfakename)",
     "украинский и 25 языков Европы", "CC-BY-4.0"),
    ("onnx-asr (istupakov)", "запуск Parakeet Ultra", "MIT"),
    ("ONNX Runtime (Microsoft)", "вычисления моделей", "MIT"),
    ("PySide6 / Qt", "окно программы", "LGPL-3.0"),
    # [20.11.2026] дополнено перед открытием кода: модели говорящих и FFmpeg
    ("pyannote segmentation 3.0 (CNRS)", "кто говорит: деление на реплики", "MIT"),
    ("3D-Speaker ERes2Net (Alibaba DAMO)", "кто говорит: отпечаток голоса", "Apache 2.0"),
    ("FFmpeg", "чтение аудиофайлов и запись звука", "LGPL-3.0, ffmpeg.org"),
]


class AboutTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("О программе")
        title.setProperty("class", "TitleLabel")
        subtitle = QLabel("Голос в текст без интернета: речь не уходит с этого компьютера")
        subtitle.setProperty("class", "SubtitleLabel")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = self._card(layout)
        # [12.11.2026] Язык интерфейса — как в Handy: «Язык приложения»
        row = QHBoxLayout()
        lbl = QLabel("Язык приложения")
        lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.cb_lang = QComboBox()
        for code, name in i18n.LANGS.items():
            self.cb_lang.addItem(name, code)
        self.cb_lang.setCurrentIndex(list(i18n.LANGS).index(i18n.language()))
        self.cb_lang.currentIndexChanged.connect(self.on_lang_changed)
        row.addWidget(lbl)
        row.addStretch(1)
        row.addWidget(self.cb_lang)
        card.addLayout(row)
        self._info(card, "Программа", APP_NAME)
        self._info(card, "Версия", APP_VERSION)
        # [12.11.2026] Авторы — «Бак + Claude»
        self._info(card, "Авторы", "Бак + Claude, 2026 — канал «Бак зря не гавкает»")
        self._info(card, "Лицензия программы", "MIT — свободно пользоваться, менять и передавать с указанием авторов")
        # [18.11.2026] модели — отдельно от программы: обновление ставится поверх, без моделей
        self._info(card, "Обновления", "Установщик обновления ставится поверх, история и настройки сохраняются")
        # [v3.2.2, 20.11.2026] кнопка «Проверить обновления» — проверка только по нажатию
        row = QHBoxLayout()
        lbl = QLabel("Проверить обновления")
        lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.btn_update = QPushButton("Проверить")
        self.btn_update.setProperty("class", "SecondaryButton")
        self.btn_update.setIcon(qta.icon("fa5s.sync-alt", color="#a0a0ab"))
        self.btn_update.clicked.connect(lambda: self.check_updates(manual=True))
        row.addWidget(lbl)
        row.addStretch(1)
        row.addWidget(self.btn_update)
        card.addLayout(row)
        self._checker = None
        self._info(card, "Исходный код", "Открытый код; устройство — DEVELOPER.md, все лицензии — THIRD_PARTY_LICENSES.md")
        self._button(card, "Канал «Бак зря не гавкает»", "Открыть канал", "fa5s.dog", CHANNEL_URL)
        if SUPPORT_URL:
            self._button(card, "Поддержка развития", "Поддержать", "fa5s.heart", SUPPORT_URL, primary=True)

        folders = self._card(layout, "Где что лежит")
        self._path(folders, "Каталог программы", APP_DIR)
        self._path(folders, "Данные: история, настройки", DATA_DIR)
        self._path(folders, "Журнал работы", LOG_FILE, open_target=DATA_DIR)
        self._path(folders, "Модели", DEFAULT_MODELS_PATH)
        self.audio_edit = self._path(folders, "Звук записей с микрофона", AppSettings.get("mic/audio_dir"),
                                     change=self.change_audio_dir)

        credits = self._card(layout, "Благодарности — что внутри и на каких условиях")
        for name, role, lic in CREDITS:
            row = QLabel(f"<b>{name}</b> — {i18n.tr(role)}. Лицензия: {lic}")
            row.setWordWrap(True)
            row.setStyleSheet("font-size: 13px;")
            credits.addWidget(row)
        note = QLabel("CC-BY-4.0 требует указывать автора модели — этот список и есть такое указание.")
        note.setWordWrap(True)
        note.setStyleSheet("font-size: 12px; color: #8b8b95;")
        credits.addWidget(note)
        layout.addStretch(1)

    # --- построение ---------------------------------------------------
    def _card(self, layout, header: str = ""):
        if header:
            lbl = QLabel(i18n.tr(header).upper())
            lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #8b8b95; margin-top: 6px;")
            layout.addWidget(lbl)
        frame = QFrame()
        frame.setProperty("class", "CardFrame")
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(16, 12, 16, 12)
        inner.setSpacing(10)
        layout.addWidget(frame)
        return inner

    def _info(self, card, name: str, value: str):
        row = QHBoxLayout()
        left = QLabel(name)
        left.setStyleSheet("font-size: 13px; font-weight: 600;")
        right = QLabel(value)
        right.setWordWrap(True)
        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        right.setTextInteractionFlags(Qt.TextSelectableByMouse)
        right.setStyleSheet("font-size: 13px;")
        row.addWidget(left)
        row.addWidget(right, 1)
        card.addLayout(row)

    def _button(self, card, name: str, text: str, icon: str, url: str, primary: bool = False):
        row = QHBoxLayout()
        left = QLabel(name)
        left.setStyleSheet("font-size: 13px; font-weight: 600;")
        btn = QPushButton(text)
        btn.setProperty("class", "PrimaryButton" if primary else "SecondaryButton")
        btn.setIcon(qta.icon(icon, color="#ffffff" if primary else "#a0a0ab"))
        btn.clicked.connect(lambda: self._open_url(url))
        row.addWidget(left)
        row.addStretch(1)
        row.addWidget(btn)
        card.addLayout(row)

    def _open_url(self, url: str):
        if url:
            QDesktopServices.openUrl(QUrl(url))
        else:
            QMessageBox.information(self, "Скоро", "Ссылка появится вместе с каналом «Бак зря не гавкает».")

    def _path(self, card, name: str, path: str, open_target: str = None, change=None) -> QLineEdit:
        lbl = QLabel(name)
        lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
        card.addWidget(lbl)
        row = QHBoxLayout()
        edit = QLineEdit(path)
        edit.setReadOnly(True)
        row.addWidget(edit, 1)
        btn_open = QPushButton("Открыть")
        btn_open.setProperty("class", "SecondaryButton")
        btn_open.setIcon(qta.icon("fa5s.folder-open", color="#a0a0ab"))
        btn_open.clicked.connect(lambda: self._open(open_target or edit.text()))
        row.addWidget(btn_open)
        if change:
            btn_change = QPushButton("Изменить…")
            btn_change.setProperty("class", "SecondaryButton")
            btn_change.clicked.connect(change)
            row.addWidget(btn_change)
        card.addLayout(row)
        return edit

    # --- действия -----------------------------------------------------
    @staticmethod
    def _open(path: str):
        target = path if os.path.isdir(path) else os.path.dirname(path)
        if os.path.isdir(target):
            os.startfile(target)

    def on_lang_changed(self, index: int):
        code = self.cb_lang.itemData(index)
        if code == i18n.language():
            return
        AppSettings.set("ui/lang", code)
        # Сообщение — уже на выбранном языке
        i18n.set_language(code)
        QMessageBox.information(self, i18n.tr("Язык изменён"), i18n.tr("Программа перезапустится на выбранном языке."))
        # Перезапуск: новый экземпляр стартует через 2 с, когда этот уже закрылся (один экземпляр программы)
        # 12.11.2026: через cmd кавычки `start ""` портились (окно «Windows не удаётся найти "\\"») —
        # теперь тот же Python ждёт 2 с и запускает main.py сам
        main_py = os.path.join(APP_DIR, "main.py")
        script = (f"import time, subprocess; time.sleep(2); "
                  f"subprocess.Popen([{sys.executable!r}, {main_py!r}], cwd={APP_DIR!r})")
        QProcess.startDetached(sys.executable, ["-c", script], APP_DIR)
        self.window().quit_app()

    # --- обновления [v3.2.2] -------------------------------------------
    def startup_updates(self):
        """При запуске: первый раз — вопрос; дальше — тихая проверка раз в сутки, если разрешено."""
        if not AppSettings.get("updates/asked"):
            answer = QMessageBox.question(
                self.window(), i18n.tr("Обновления"),
                i18n.tr("Проверять обновления на GitHub?\n\nРаз в сутки при запуске программа смотрит страницу "
                        "релизов на GitHub. Речь, записи и настройки с компьютера не уходят.\n\n"
                        "Изменить можно в «Настройки → Общие»."),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            allow = answer == QMessageBox.Yes
            AppSettings.set("updates/asked", True)
            AppSettings.set("updates/check", allow)
            sw = getattr(getattr(self.window(), "settings_tab", None), "sw_updates", None)
            if sw is not None:
                sw.blockSignals(True)
                sw.setChecked(allow)
                sw.blockSignals(False)
        if AppSettings.get("updates/check") and updates.auto_check_due(AppSettings.get("updates/last")):
            self.check_updates(manual=False)

    def check_updates(self, manual: bool):
        if self._checker is not None and self._checker.isRunning():
            return
        if manual:
            self.btn_update.setEnabled(False)
            self.btn_update.setText(i18n.tr("Проверяю…"))
        self._checker = updates.UpdateChecker(self)
        self._checker.found.connect(self._update_found)
        self._checker.latest.connect(lambda: self._update_done(manual, ok=True))
        self._checker.failed.connect(lambda _e: self._update_done(manual, ok=False))
        self._checker.start()

    def _reset_button(self):
        self.btn_update.setEnabled(True)
        self.btn_update.setText(i18n.tr("Проверить"))

    def _update_found(self, version: str, url: str):
        import time
        self._reset_button()
        AppSettings.set("updates/last", time.time())
        text = i18n.tr("Вышла версия {0}, у вас {1}.\n\nОткрыть страницу загрузки?").format(version, updates.VERSION)
        if QMessageBox.question(self.window(), i18n.tr("Обновления"), text,
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl(url))

    def _update_done(self, manual: bool, ok: bool):
        import time
        self._reset_button()
        if ok:
            AppSettings.set("updates/last", time.time())
        if not manual:
            return  # тихая проверка: сообщает только о новой версии
        if ok:
            QMessageBox.information(self, i18n.tr("Обновления"),
                                    i18n.tr("У вас последняя версия: {0}.").format(updates.VERSION))
        else:
            QMessageBox.warning(self, i18n.tr("Обновления"),
                                i18n.tr("Не удалось проверить обновления: нет интернета или на GitHub ещё нет релизов."
                                        "\n\nСтраница релизов: {0}").format(updates.RELEASES_URL))

    def change_audio_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Куда сохранять звук записей", self.audio_edit.text())
        if folder:
            folder = os.path.normpath(folder)
            AppSettings.set("mic/audio_dir", folder)
            self.audio_edit.setText(folder)
