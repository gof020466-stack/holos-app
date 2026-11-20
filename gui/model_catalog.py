import os
import zipfile
import logging
import requests
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QTableWidget, QTableWidgetItem, QPushButton, QProgressBar,
                               QHeaderView, QAbstractItemView, QMessageBox, QCheckBox)
from PySide6.QtCore import Qt, QThread, Signal
import qtawesome as qta

logger = logging.getLogger("ModelCatalog")

# Официальный список моделей Vosk (JSON: name, lang, lang_text, url, size, size_text, type, obsolete)
CATALOG_URL = "https://alphacephei.com/vosk/models/model-list.json"

LANG_RU = {
    "ru": "Русский", "uk": "Украинский", "ua": "Украинский", "en-us": "Английский (США)",
    "en-in": "Английский (Индия)", "de": "Немецкий", "fr": "Французский", "es": "Испанский",
    "it": "Итальянский", "pl": "Польский", "pt": "Португальский", "cn": "Китайский",
    "ja": "Японский", "tr": "Турецкий", "kz": "Казахский", "uz": "Узбекский",
    "be": "Белорусский", "cs": "Чешский", "nl": "Нидерландский", "ko": "Корейский",
}
TYPE_RU = {"small": "лёгкая", "big": "большая", "big-lgraph": "большая (облегчённый граф)"}


class CatalogLoader(QThread):
    loaded = Signal(list)
    failed = Signal(str)

    def run(self):
        try:
            resp = requests.get(CATALOG_URL, timeout=20)
            resp.raise_for_status()
            models = [m for m in resp.json()
                      if str(m.get("obsolete", "false")).lower() != "true"
                      and m.get("type") in TYPE_RU]
            self.loaded.emit(models)
        except Exception as e:
            self.failed.emit(str(e))


class ModelDownloadWorker(QThread):
    """
    Скачивает ZIP модели во временный файл в папке моделей и распаковывает его.
    """
    progress = Signal(int, str)       # (процент, текст статуса)
    finished_ok = Signal(str)         # (имя модели)
    failed = Signal(str)

    def __init__(self, model: dict, models_dir: str):
        super().__init__()
        self.model = model
        self.models_dir = models_dir
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        name = self.model["name"]
        zip_path = os.path.join(self.models_dir, name + ".zip.part")
        try:
            with requests.get(self.model["url"], stream=True, timeout=30) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length") or self.model.get("size") or 0)
                done = 0
                with open(zip_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 256):
                        if self.cancelled:
                            raise InterruptedError("Загрузка отменена.")
                        f.write(chunk)
                        done += len(chunk)
                        pct = int(done * 100 / total) if total else 0
                        self.progress.emit(min(pct, 99), f"Скачано {done / 1048576:.0f} из {total / 1048576:.0f} МБ")

            self.progress.emit(99, "Распаковка...")
            with zipfile.ZipFile(zip_path) as zf:
                # Защита от путей вида ../ внутри архива
                root = os.path.realpath(self.models_dir)
                for member in zf.namelist():
                    target = os.path.realpath(os.path.join(root, member))
                    if not target.startswith(root + os.sep):
                        raise ValueError(f"Небезопасный путь в архиве: {member}")
                zf.extractall(self.models_dir)
            self.progress.emit(100, "Готово")
            self.finished_ok.emit(name)
        except Exception as e:
            logger.error(f"Ошибка загрузки модели {name}: {e}")
            self.failed.emit(str(e))
        finally:
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except OSError:
                    pass


class ModelCatalogDialog(QDialog):
    """
    [v3] Каталог официальных моделей Vosk: поиск, загрузка с прогрессом, автоматическая распаковка.
    """

    def __init__(self, models_dir: str, parent=None):
        super().__init__(parent)
        self.models_dir = models_dir
        self.models = []
        self.loader = None
        self.downloader = None
        self.setWindowTitle("Каталог моделей Vosk")
        self.resize(820, 560)
        self.setup_ui()
        self.load_catalog()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Официальные модели alphacephei.com")
        title.setProperty("class", "TitleLabel")
        layout.addWidget(title)

        hint = QLabel(f"Модель скачивается и распаковывается в {self.models_dir}. "
                      "Лёгкие (~50 МБ) — для диктовки, большие (1–2 ГБ) — для точной расшифровки файлов.")
        hint.setWordWrap(True)
        hint.setProperty("class", "SubtitleLabel")
        layout.addWidget(hint)

        filter_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Фильтр: язык или имя модели (например, ru, uk, english)")
        self.search.textChanged.connect(self.fill_table)
        self.chk_installed = QCheckBox("Скрыть установленные")
        self.chk_installed.toggled.connect(self.fill_table)
        filter_row.addWidget(self.search, 1)
        filter_row.addWidget(self.chk_installed)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Язык", "Модель", "Размер", "Тип"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self.update_buttons)
        self.table.itemDoubleClicked.connect(lambda _: self.start_download())
        layout.addWidget(self.table, 1)

        self.lbl_status = QLabel("Загрузка списка моделей...")
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.lbl_status)
        layout.addWidget(self.progress)

        buttons = QHBoxLayout()
        self.btn_cancel = QPushButton("Отменить загрузку")
        self.btn_cancel.setProperty("class", "SecondaryButton")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self.cancel_download)
        self.btn_close = QPushButton("Закрыть")
        self.btn_close.setProperty("class", "SecondaryButton")
        self.btn_close.clicked.connect(self.reject)
        self.btn_download = QPushButton("Скачать и установить")
        self.btn_download.setProperty("class", "PrimaryButton")
        self.btn_download.setIcon(qta.icon("fa5s.download", color="#ffffff"))
        self.btn_download.setEnabled(False)
        self.btn_download.clicked.connect(self.start_download)
        buttons.addWidget(self.btn_cancel)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_close)
        buttons.addWidget(self.btn_download)
        layout.addLayout(buttons)

    def load_catalog(self):
        self.loader = CatalogLoader()
        self.loader.loaded.connect(self.on_catalog_loaded)
        self.loader.failed.connect(self.on_catalog_failed)
        self.loader.start()

    def on_catalog_loaded(self, models: list):
        # Русский, украинский, английский — сверху; дальше по языку
        priority = {"ru": 0, "uk": 1, "ua": 1, "en-us": 2}
        self.models = sorted(models, key=lambda m: (priority.get(m.get("lang"), 9), m.get("lang_text", ""), m.get("size", 0)))
        self.lbl_status.setText(f"Доступно моделей: {len(self.models)}. Выберите строку и нажмите «Скачать».")
        self.fill_table()

    def on_catalog_failed(self, err: str):
        self.lbl_status.setText(f"Не удалось получить каталог (нет интернета?): {err}")

    def is_installed(self, name: str) -> bool:
        return os.path.isdir(os.path.join(self.models_dir, name))

    def fill_table(self):
        query = self.search.text().strip().lower()
        hide_installed = self.chk_installed.isChecked()
        self.table.setRowCount(0)
        for m in self.models:
            lang = LANG_RU.get(m.get("lang"), m.get("lang_text", m.get("lang", "")))
            haystack = f"{m.get('lang')} {m.get('lang_text')} {lang} {m['name']}".lower()
            if query and query not in haystack:
                continue
            installed = self.is_installed(m["name"])
            if installed and hide_installed:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            name_item = QTableWidgetItem(m["name"] + ("  ✓ установлена" if installed else ""))
            name_item.setData(Qt.UserRole, m)
            for col, item in enumerate([QTableWidgetItem(lang), name_item,
                                        QTableWidgetItem(m.get("size_text", "")),
                                        QTableWidgetItem(TYPE_RU.get(m.get("type"), m.get("type", "")))]):
                if installed:
                    item.setForeground(Qt.gray)
                self.table.setItem(row, col, item)
        self.table.resizeColumnToContents(0)
        self.update_buttons()

    def selected_model(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        return self.table.item(rows[0].row(), 1).data(Qt.UserRole)

    def update_buttons(self):
        busy = self.downloader is not None and self.downloader.isRunning()
        m = self.selected_model()
        self.btn_download.setEnabled(bool(m) and not busy and not self.is_installed(m["name"]))

    def start_download(self):
        m = self.selected_model()
        if not m or self.is_installed(m["name"]) or (self.downloader and self.downloader.isRunning()):
            return
        size_mb = (m.get("size") or 0) / 1048576
        if size_mb > 500:
            reply = QMessageBox.question(
                self, "Большая модель",
                f"Модель {m['name']} занимает {m.get('size_text')} (после распаковки — больше). Скачать?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        self.downloader = ModelDownloadWorker(m, self.models_dir)
        self.downloader.progress.connect(self.on_progress)
        self.downloader.finished_ok.connect(self.on_download_ok)
        self.downloader.failed.connect(self.on_download_failed)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.btn_cancel.setVisible(True)
        self.lbl_status.setText(f"Загрузка {m['name']}...")
        self.downloader.start()
        self.update_buttons()

    def on_progress(self, pct: int, text: str):
        self.progress.setValue(pct)
        self.lbl_status.setText(text)

    def on_download_ok(self, name: str):
        self.progress.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.lbl_status.setText(f"Модель {name} установлена. Выберите её в списке «Распознавание».")
        self.fill_table()

    def on_download_failed(self, err: str):
        self.progress.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.lbl_status.setText(f"Ошибка: {err}")
        self.update_buttons()

    def cancel_download(self):
        if self.downloader and self.downloader.isRunning():
            self.downloader.cancel()

    def _confirm_stop(self) -> bool:
        """Перед закрытием останавливает фоновые потоки; False — пользователь передумал."""
        if self.downloader and self.downloader.isRunning():
            reply = QMessageBox.question(self, "Загрузка идёт", "Прервать загрузку модели?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return False
            self.downloader.cancel()
            self.downloader.wait(10000)
        if self.loader and self.loader.isRunning():
            self.loader.wait(20000)
        return True

    def reject(self):
        # Esc и крестик идут сюда: поток не должен пережить диалог
        if self._confirm_stop():
            super().reject()

    def closeEvent(self, event):
        if not self._confirm_stop():
            event.ignore()
            return
        super().closeEvent(event)
