import re
import sys
import logging
import subprocess

from core.settings import AppSettings

logger = logging.getLogger("LocalCommands")

# [v3, 03.11.2026] Короткие команды после «Ассистент» VOSK выполняет сам, без Claude:
# так они работают и тогда, когда Claude занят другой задачей.
# «Включи …» (поиск музыки) остаётся за Claude — ему нужно понять, что искать.
MUSIC_COMMANDS = {
    "пауза": "pause", "на паузу": "pause", "поставь на паузу": "pause",
    "продолжи": "resume", "продолжай": "resume", "играй": "resume",
    "выключи": "quit", "выключи музыку": "quit", "стоп музыка": "quit",
    "следующий": "next", "следующая": "next", "дальше": "next",
    "предыдущий": "prev", "предыдущая": "prev", "назад": "prev",
    "громче": "louder", "тише": "quieter",
}


def normalize(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def try_local(text: str) -> bool:
    """
    Фраза — команда музыки? Выполнить скрипт и вернуть True; иначе False (фраза уйдёт в Claude).
    """
    command = MUSIC_COMMANDS.get(normalize(text))
    if not command:
        return False
    script = AppSettings.get("assistant/music_script")
    if not script:
        return False
    # pythonw программы → python.exe рядом (вывод скрипта не нужен, окна нет)
    python = sys.executable.replace("pythonw.exe", "python.exe")
    try:
        subprocess.Popen([python, script, command], creationflags=subprocess.CREATE_NO_WINDOW)
        logger.info(f"Ассистент: музыка — {command}")
    except Exception as e:
        logger.error(f"Не удалось выполнить команду музыки {command}: {e}")
    return True
