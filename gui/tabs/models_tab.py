import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QListWidgetItem, QFrame, 
                             QProgressBar, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal
import qtawesome as qta

from core.settings import AppSettings
from core.vosk_manager import DEFAULT_MODELS_PATH
from gui.model_catalog import ModelCatalogDialog

logger = logging.getLogger("ModelsTab")

class ModelLoaderWorker(QThread):
    """
    Фоновый рабочий поток для загрузки тяжелых моделей Vosk в память.
    """
    loading_finished = Signal(bool, str)  # (успех, ID модели)

    def __init__(self, vosk_manager, model_id: str):
        super().__init__()
        self.vosk_manager = vosk_manager
        self.model_id = model_id

    def run(self):
        success = self.vosk_manager.load_model(self.model_id)
        self.loading_finished.emit(success, self.model_id)

class ModelsTab(QWidget):
    # Сигнал о том, что модель успешно загружена
    model_loaded = Signal(str)

    def __init__(self, vosk_manager, parent=None):
        super().__init__(parent)
        self.vosk_manager = vosk_manager
        self.loader_worker = None
        self.setup_ui()
        self.refresh_models()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Заголовок
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        
        # [v3.2, Д3] Без техники: язык → модель загружается сразу, кнопки «Загрузить в память» нет
        title = QLabel("Модели распознавания")
        title.setProperty("class", "TitleLabel")

        subtitle = QLabel("Выберите язык — модель загрузится сразу. Распознавание идёт на этом компьютере.")
        subtitle.setProperty("class", "SubtitleLabel")
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addLayout(header_layout)

        # Панель активной модели
        self.active_model_card = QFrame()
        self.active_model_card.setObjectName("ActiveModelCard")
        self.active_model_card.setProperty("class", "CardFrame")
        
        active_layout = QHBoxLayout(self.active_model_card)
        active_layout.setContentsMargins(15, 15, 15, 15)
        
        # Иконка статуса
        self.status_icon = QLabel()
        self.status_icon.setPixmap(qta.icon("fa5s.info-circle", color="#909296").pixmap(32, 32))
        active_layout.addWidget(self.status_icon)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        active_title = QLabel("Активная модель")
        active_title.setProperty("class", "HeaderLabel")
        self.active_model_name_label = QLabel("Модель не загружена. Пожалуйста, выберите модель ниже.")
        self.active_model_name_label.setObjectName("ActiveModelNameLabel")
        
        info_layout.addWidget(active_title)
        info_layout.addWidget(self.active_model_name_label)
        active_layout.addLayout(info_layout, 1)
        
        layout.addWidget(self.active_model_card)

        # Список моделей
        list_label = QLabel("Модели на этом компьютере:")
        list_label.setProperty("class", "HeaderLabel")
        layout.addWidget(list_label)

        self.models_list = QListWidget()
        self.models_list.setObjectName("ModelsListWidget")
        self.models_list.itemClicked.connect(lambda _item: self.load_selected_model(quiet=True))
        layout.addWidget(self.models_list, 1)

        # Прогресс-бар для загрузки модели
        self.progress_container = QWidget()
        self.progress_container.setVisible(False)
        progress_layout = QVBoxLayout(self.progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(5)
        
        self.progress_label = QLabel("Загрузка модели в память...")
        self.progress_label.setObjectName("ModelsProgressLabel")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Бегущий индикатор (Indeterminate)
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_container)

        # Кнопки управления
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        self.btn_refresh = QPushButton("Обновить список")
        self.btn_refresh.setProperty("class", "SecondaryButton")
        self.btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="#e2e2e5"))
        self.btn_refresh.clicked.connect(self.refresh_models)
        
        self.btn_load = QPushButton("Загрузить модель в память")
        self.btn_load.setProperty("class", "PrimaryButton")
        self.btn_load.setIcon(qta.icon("fa5s.download", color="#ffffff"))
        self.btn_load.clicked.connect(self.load_selected_model)
        
        # [v3] Каталог официальных моделей с загрузкой из интернета
        self.btn_catalog = QPushButton("Каталог моделей")
        self.btn_catalog.setProperty("class", "SecondaryButton")
        self.btn_catalog.setIcon(qta.icon("fa5s.cloud-download-alt", color="#e2e2e5"))
        self.btn_catalog.clicked.connect(self.open_catalog)

        buttons_layout.addWidget(self.btn_refresh)
        buttons_layout.addWidget(self.btn_catalog)
        buttons_layout.addStretch(1)
        self.btn_load.setVisible(False)  # [v3.2, Д3] щелчок по строке уже загружает модель
        layout.addLayout(buttons_layout)

    def refresh_models(self):
        """
        Пересканирует папку моделей и обновляет QListWidget.
        """
        self.models_list.clear()
        models = self.vosk_manager.scan_models()
        
        if not models:
            item = QListWidgetItem(f"Модели не найдены. Убедитесь, что распакованные папки моделей находятся в {DEFAULT_MODELS_PATH}")
            item.setFlags(Qt.NoItemFlags)
            item.setData(Qt.UserRole, None)
            self.models_list.addItem(item)
            self.btn_load.setEnabled(False)
            return

        self.btn_load.setEnabled(True)
        for model in models:
            if model.get("service") and self.vosk_manager.active_model_name != model["id"]:
                continue  # [v3.2] служебная модель — в списке не нужна
            item = QListWidgetItem()
            # Устанавливаем красивое имя
            item.setText(model["name"])
            item.setToolTip(model.get("details", ""))
            # Сохраняем ID модели (имя папки) в UserRole
            item.setData(Qt.UserRole, model["id"])
            
            # Помечаем иконкой
            is_active = (self.vosk_manager.active_model_name == model["id"])
            if is_active:
                item.setIcon(qta.icon("fa5s.check-circle", color="#10b981"))
                item.setSelected(True)
            else:
                item.setIcon(qta.icon("fa5s.folder", color="#6366f1"))
                
            self.models_list.addItem(item)

    def open_catalog(self):
        """
        [v3] Открывает каталог моделей; после закрытия пересканирует папку.
        """
        dialog = ModelCatalogDialog(self.vosk_manager.models_dir, self)
        dialog.exec()
        self.refresh_models()

    def load_selected_model(self, quiet: bool = False):
        """
        Запускает фоновую загрузку выбранной модели.
        [v3.2] quiet — щелчок по строке: без окон «выберите модель» / «уже загружена».
        """
        selected_items = self.models_list.selectedItems()
        if not selected_items:
            if not quiet:
                QMessageBox.warning(self, "Внимание", "Пожалуйста, выберите модель из списка.")
            return

        model_id = selected_items[0].data(Qt.UserRole)
        if not model_id:
            return

        # Если эта модель уже загружена, ничего не делаем
        if self.vosk_manager.active_model_name == model_id:
            if not quiet:
                QMessageBox.information(self, "Информация", "Эта модель уже загружена и активна.")
            return

        self.load_model_by_id(model_id)

    def load_model_by_id(self, model_id: str, silent: bool = False):
        """
        [v3] Фоновая загрузка модели по ID. silent=True — без диалогов (автозагрузка при старте).
        """
        if self.loader_worker and self.loader_worker.isRunning():
            return
        self._silent_load = silent

        # Деактивируем кнопки на время загрузки
        self.btn_load.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.models_list.setEnabled(False)
        
        # Показываем прогресс-бар
        self.progress_container.setVisible(True)
        self.progress_label.setText("Загрузка модели… обычно 3–10 секунд")

        # Запускаем фоновый поток
        self.loader_worker = ModelLoaderWorker(self.vosk_manager, model_id)
        self.loader_worker.loading_finished.connect(self.on_model_loaded)
        self.loader_worker.start()

    def on_model_loaded(self, success: bool, model_id: str):
        # Восстанавливаем элементы интерфейса
        self.btn_load.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self.models_list.setEnabled(True)
        self.progress_container.setVisible(False)

        if success:
            display_name = self.vosk_manager.active_model_name
            for i in range(self.models_list.count()):
                item = self.models_list.item(i)
                if item.data(Qt.UserRole) == model_id:
                    display_name = item.text()
                    break

            self.active_model_name_label.setText(f"{display_name} — Готово")
            self.active_model_name_label.setStyleSheet("color: #10b981; font-size: 13px; font-weight: 600;")
            self.status_icon.setPixmap(qta.icon("fa5s.check-circle", color="#10b981").pixmap(32, 32))
            
            # Перерисовываем иконки в списке
            self.refresh_models()
            
            # [v3] Запоминаем модель — при следующем запуске она загрузится сама
            AppSettings.set("model/last_id", model_id)

            # Генерируем сигнал наружу
            self.model_loaded.emit(model_id)
            logger.info(f"Модель {model_id} успешно загружена и готова к работе.")
        else:
            if not getattr(self, "_silent_load", False):
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить модель '{model_id}'. Проверьте целостность файлов модели.")
            self.active_model_name_label.setText("Ошибка при загрузке модели. Выберите другую.")
            self.active_model_name_label.setStyleSheet("color: #ef4444; font-size: 13px;")
            self.status_icon.setPixmap(qta.icon("fa5s.exclamation-triangle", color="#ef4444").pixmap(32, 32))
