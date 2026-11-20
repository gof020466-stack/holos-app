import os
import logging
from typing import Dict, List, Optional
from vosk import Model, KaldiRecognizer
from core.sherpa_engine import SherpaModel, SherpaRecognizer, is_sherpa_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("VoskManager")

# Путь по умолчанию к моделям на диске D.
# [v3] Перенос на другой компьютер (31.10.2026): нет этой папки — модели в «models» рядом с программой
HOME_MODELS_PATH = r"D:\Apps\VOSK_BASE\models"
APP_MODELS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
# [12.11.2026] Установщик «Голос» кладёт модели рядом с программой — они главнее домашней папки
DEFAULT_MODELS_PATH = APP_MODELS_PATH if os.path.isdir(APP_MODELS_PATH) else HOME_MODELS_PATH

# [v3] Размеры — распакованных папок на диске (замер 29.10.2026); прежние цифры были размерами архивов
MODEL_NAMES_MAPPING = {
    "vosk-model-ru-0.54": "Русский 0.54 (Новая точная, два прохода, 440 МБ)",
    "parakeet-ultra-onnx": "Украинский и др.: Parakeet Ultra (точнее v3, сама ставит знаки, 690 МБ)",
    "sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16": "Русский GigaAM v3 (Сбер, сама ставит знаки, 230 МБ)",
    "vosk-model-small-streaming-ru-0.54": "Русский 0.54 (Новая лёгкая потоковая, 120 МБ)",
    "vosk-model-ru-0.42": "Русский (Большая точная модель, 3,4 ГБ)",
    "vosk-model-small-ru-0.22": "Русский (Легкая модель, 90 МБ)",
    "vosk-model-en-us-0.22": "Английский (Большая точная модель, 2,7 ГБ)",
    "vosk-model-small-en-us-0.15": "Английский (Легкая модель, 70 МБ)",
    "vosk-model-uk-v3": "Украинский (Большая модель, 1 ГБ)",
    "vosk-model-small-uk-v3": "Украинский (Легкая модель, 410 МБ)",
}

# [v3.2, 18.11.2026, Д3] Имена в списке — без техники; прежнее имя с размером — во всплывающей подсказке
SIMPLE_NAMES = {
    "sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16": "Русский — точный (рекомендуем)",
    # 18.11.2026: название прямо говорит «Украинский, английский и другие» — иначе
    # англоязычный не видит свою модель и лезет в каталог
    "parakeet-ultra-onnx": "Украинский, английский и другие",
}
# Служебные: делят речь на фразы для GigaAM и Parakeet, слушают голосовые команды — в списке не нужны.
# [v3.2, 18.11.2026] Большая 0.54 (322 МБ, знаки по паузам) — тоже не в списке:
# название «Русский запасной» было непонятно.
SERVICE_MODELS = {"vosk-model-small-streaming-ru-0.54", "vosk-model-small-ru-0.22", "vosk-model-ru-0.54"}

class VoskManager:
    def __init__(self, models_dir: str = DEFAULT_MODELS_PATH):
        self.models_dir = models_dir
        self.active_model: Optional[Model] = None
        self.active_model_name: Optional[str] = None
        
        # Убедимся, что папка существует
        if not os.path.exists(self.models_dir):
            try:
                os.makedirs(self.models_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"Не удалось создать директорию для моделей: {e}")

    def scan_models(self) -> List[Dict[str, str]]:
        """
        Сканирует папку моделей и возвращает список найденных моделей
        с их красивыми именами, папками и путями.
        """
        found_models = []
        if not os.path.exists(self.models_dir):
            return found_models

        try:
            for entry in os.listdir(self.models_dir):
                full_path = os.path.join(self.models_dir, entry)
                # Модель Vosk — это папка, внутри которой обязательно есть am или conf
                if os.path.isdir(full_path):
                    has_am = os.path.isdir(os.path.join(full_path, "am"))
                    has_conf = os.path.isdir(os.path.join(full_path, "conf"))
                    if has_am or has_conf or is_sherpa_model(full_path):
                        from core.i18n import tr  # [12.11.2026] имя модели — на языке интерфейса
                        details = tr(MODEL_NAMES_MAPPING.get(entry, entry))
                        found_models.append({
                            "id": entry,
                            "name": tr(SIMPLE_NAMES.get(entry, details)),
                            "details": details,
                            "service": entry in SERVICE_MODELS,
                            "path": full_path
                        })
        except Exception as e:
            logger.error(f"Ошибка при сканировании папки моделей: {e}")
            
        order = list(SIMPLE_NAMES)  # [v3.2] рекомендуемая — первой
        return sorted(found_models, key=lambda x: (order.index(x["id"]) if x["id"] in order else len(order), x["name"]))

    def load_model(self, model_id: str) -> bool:
        """
        Загружает выбранную модель в память. Это ресурсоемкая операция.
        """
        model_path = os.path.join(self.models_dir, model_id)
        if not os.path.exists(model_path):
            logger.error(f"Папка модели не найдена: {model_path}")
            return False

        try:
            logger.info(f"Начало загрузки модели: {model_id}...")
            # Высвобождаем предыдущую модель, если она была
            self.active_model = None
            
            # Загружаем новую
            # [v3] Модели 0.54 — движок sherpa-onnx; остальные — Kaldi
            self.active_model = SherpaModel(model_path) if is_sherpa_model(model_path) else Model(model_path)
            self.active_model_name = model_id
            logger.info(f"Модель {model_id} успешно загружена.")
            return True
        except Exception as e:
            logger.error(f"Не удалось загрузить модель {model_id}: {e}")
            self.active_model = None
            self.active_model_name = None
            return False

    def get_recognizer(self, sample_rate: int = 16000) -> Optional[KaldiRecognizer]:
        """
        Создает и возвращает распознаватель KaldiRecognizer для активной модели.
        """
        if not self.active_model:
            logger.error("Нет активной загруженной модели для создания распознавателя.")
            return None
        if isinstance(self.active_model, SherpaModel):
            return SherpaRecognizer(self.active_model, sample_rate)
        return KaldiRecognizer(self.active_model, sample_rate)
