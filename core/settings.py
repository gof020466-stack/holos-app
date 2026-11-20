import os
from PySide6.QtCore import QSettings

# [v3] Настройки хранятся в INI рядом с базой: переносятся вместе с папкой программы
# и не пересекаются с v1/v2 (у них настроек нет).
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "settings.ini")

# [12.11.2026] Первый запуск после установки — русская GigaAM со знаками
DEFAULT_MODEL_ID = "sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16"

DEFAULTS = {
    "model/last_id": DEFAULT_MODEL_ID,
    # [v3, 12.11.2026] Язык интерфейса: ru / uk / en; "" — по языку Windows при первом запуске
    "ui/lang": "",
    "model/autoload": True,
    # [v3.2.2, 20.11.2026] Проверка обновлений на GitHub: вопрос — один раз при первом запуске
    "updates/asked": False,
    "updates/check": False,
    "updates/last": 0.0,
    "dictation/hotkey": "F8",
    "dictation/enabled": True,
    "dictation/auto_insert": True,
    "dictation/auto_punctuate": True,
    "dictation/sound": True,
    "dictation/restore_clipboard": True,
    # [v3] После вставки — пустая строка: следующая диктовка начинается с нового абзаца
    "dictation/new_paragraph": True,
    "window/close_to_tray": True,
    "window/dark_theme": True,
    # [v3] Паузы (с) для пунктуации живой речи: короче comma — без знака,
    # от sentence — точка, от paragraph — новый абзац
    # 29.10.2026: 0.7 / 1.2 → 1.0 / 2.0 — точки посреди фраз из-за пауз раздумья
    "punct/comma_pause": 1.0,
    "punct/sentence_pause": 2.0,
    "punct/paragraph_pause": 3.0,
    # [v3] Голосовые команды «начать запись» / «стоп запись» во вкладке «Запись с микрофона»
    "voice/commands_enabled": True,
    # [v3] Словарь пользователя — заметка Markdown (замены и горячие слова), см. core/dictionary.py; "" — без словаря
    "dict/path": "",
    "dict/hotwords_score": 1.5,
    # [v3] Звук записей с микрофона — data\записи рядом с программой (меняется в «О программе»)
    "mic/save_audio": True,
    "mic/audio_dir": os.path.join(os.path.dirname(SETTINGS_PATH), "записи"),
    # [v3.2, 18.11.2026] Ф1: источник новой записи — mic / system (звук компьютера) / both
    "record/source": "mic",
    "mic/punctuation": True,
    # [v3.2] Ф2: изложение в Claude — только по кнопке; True — спрашивать перед каждой отправкой
    # (флажок «Больше не спрашивать»; человек видит, куда уходит текст)
    "summary/ask": True,
    # [v3.2] Ф3: папка заметок Markdown — «Документы\Голос» (меняется в «Настройках»)
    "export/md_dir": os.path.join(os.path.expanduser("~"), "Documents", "Голос"),
    # [v3] Окно «Идёт запись речи» (диктовка): место, куда его перетащили; "" — по центру сверху
    "overlay/pos": "",
    # [v3, 03.11.2026] «Ассистент, …» — фраза уходит в окно Claude и отправляется (Enter).
    # Слово-пробуждение слушает модель команд; сама фраза — основной моделью до паузы.
    "assistant/wake_word": "ассистент",
    "assistant/window_title": "Claude",
    "assistant/window_exe": "claude.exe",
    "assistant/send_enter": True,
    # 03.11.2026: 2 с — фразу обрывало на полуслове → 3 с
    "assistant/silence": 3.0,     # с тишины после речи — конец фразы
    "assistant/no_speech": 8.0,   # с без речи после «Ассистент» — отмена
    "assistant/max": 60.0,        # с — предел одной фразы
    # Музыка (пауза, продолжи, выключи…) — свой скрипт, без Claude: core/local_commands.py; "" — нет
    "assistant/music_script": "",
}


class AppSettings:
    """
    Тонкая обёртка над QSettings с типизированными значениями по умолчанию.
    """
    _qs = None

    @classmethod
    def _store(cls) -> QSettings:
        if cls._qs is None:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            cls._qs = QSettings(SETTINGS_PATH, QSettings.IniFormat)
        return cls._qs

    @classmethod
    def get(cls, key: str):
        default = DEFAULTS.get(key)
        value = cls._store().value(key, default)
        # INI возвращает bool как строку 'true'/'false'
        if isinstance(default, bool) and isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        if isinstance(default, float):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default
        return value

    @classmethod
    def pauses(cls) -> dict:
        """[v3] Пороги пауз для Punctuator.punctuate_words_with_timing."""
        return {"comma_pause": cls.get("punct/comma_pause"),
                "sentence_pause": cls.get("punct/sentence_pause"),
                "paragraph_pause": cls.get("punct/paragraph_pause")}

    @classmethod
    def set(cls, key: str, value):
        cls._store().setValue(key, value)
        cls._store().sync()
