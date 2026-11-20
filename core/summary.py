"""
[v3.2, 18.11.2026] Ф2: краткое изложение записи — в окно Claude Desktop, только по кнопке.

Решение 18.11.2026: только по кнопке, и человек видит, куда уходит текст; конфиденциальность —
ключевой принцип программы. Поэтому: автоматического изложения нет; кнопка подписана «облако»;
перед отправкой — предупреждение с флажком «Больше не спрашивать» (сброс — «Настройки → Изложение»).

Путь — тот же, что у «Ассистента»: окно Claude находится по заголовку и процессу, текст вставляется
через буфер обмена, Enter отправляет. Ключа API и оплаты нет. Окна нет — текст остаётся в буфере.
"""
import time
import logging

import keyboard
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication

from core.settings import AppSettings
from core.assistant_target import find_window, activate_window

logger = logging.getLogger("Summary")

PROMPTS = {
    "ru": "Кратко изложи эту запись: о чём она, какие приняты решения, какие задачи и кто что сказал. "
          "Ответ — на русском.",
    "uk": "Стисло виклади цей запис: про що він, які ухвалено рішення, які завдання і хто що сказав. "
          "Відповідь — українською.",
    "en": "Briefly summarize this recording: what it is about, what was decided, what the tasks are "
          "and who said what. Answer in English.",
}


def detect_language(text: str) -> str:
    """Язык записи по буквам: і ї є ґ — украинский; латиницы больше кириллицы — английский."""
    cyr = sum(1 for c in text if "а" <= c.lower() <= "я" or c.lower() in "ёіїєґ")
    lat = sum(1 for c in text if "a" <= c.lower() <= "z")
    if lat > cyr:
        return "en"
    uk = sum(1 for c in text.lower() if c in "іїєґ")
    return "uk" if cyr and uk / cyr > 0.01 else "ru"


def build_request(text: str) -> str:
    return PROMPTS[detect_language(text)] + "\n\n---\n\n" + text.strip()


def send(text: str) -> str:
    """
    Отправляет запрос с текстом в окно Claude. Возвращает "sent" или "clipboard" (окна Claude нет).
    """
    request = build_request(text)
    clipboard = QGuiApplication.clipboard()
    hwnd = find_window(AppSettings.get("assistant/window_title"), AppSettings.get("assistant/window_exe"))
    if not hwnd:
        clipboard.setText(request)
        logger.info("Изложение: окна Claude нет — запрос в буфере обмена.")
        return "clipboard"
    previous = clipboard.text() if AppSettings.get("dictation/restore_clipboard") else None
    clipboard.setText(request)
    activate_window(hwnd)
    time.sleep(0.1)
    keyboard.send("ctrl+v")
    if AppSettings.get("assistant/send_enter"):
        time.sleep(0.4)  # длинный текст Claude вставляет дольше короткой фразы
        keyboard.send("enter")
    if previous:
        QTimer.singleShot(2000, lambda: clipboard.setText(previous))
    logger.info(f"Изложение: запрос отправлен в Claude ({len(request)} знаков).")
    return "sent"
