import sys
import os
import logging
from logging.handlers import RotatingFileHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket

APP_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_NAME = "vosk-transcriber-v3-single-instance"
DATA_DIR = os.path.join(APP_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
# [12.11.2026] Установщик кладёт ffmpeg в bin рядом с программой
_BIN = os.path.join(APP_DIR, "bin")
if os.path.isdir(_BIN):
    os.environ["PATH"] = _BIN + os.pathsep + os.environ.get("PATH", "")

# [v3] Работаем из папки программы при любом способе запуска (ярлык, pythonw, двойной клик)
os.chdir(APP_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Настройка системного логгера: консоль (если есть) + файл data/app.log
# (под pythonw консоли нет — без файла ошибки терялись)
handlers = [RotatingFileHandler(os.path.join(DATA_DIR, "app.log"), maxBytes=1_000_000, backupCount=2, encoding="utf-8")]
if sys.stdout is not None:
    handlers.append(logging.StreamHandler(sys.stdout))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=handlers,
    force=True
)
logger = logging.getLogger("AppMain")


def _log_uncaught(exc_type, exc, tb):
    logger.critical("Необработанная ошибка", exc_info=(exc_type, exc, tb))


sys.excepthook = _log_uncaught


def main():
    logger.info("Запуск приложения «Голос» (VOSK v3)...")

    # Решаем проблемы с масштабированием на High-DPI экранах (Qt6 делает это по умолчанию,
    # но на всякий случай можно задать явные параметры)
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("Голос")
    from core.updates import VERSION
    app.setApplicationVersion(VERSION)
    # [v3] Окно прячется в трей — приложение не должно завершаться вместе с ним
    app.setQuitOnLastWindowClosed(False)

    # [v3] Один экземпляр: второй перехватывал бы ту же горячую клавишу и вставлял текст дважды.
    # Именованный канал исчезает вместе с процессом — после сбоя запуск не блокируется.
    probe = QLocalSocket()
    probe.connectToServer(INSTANCE_NAME)
    if probe.waitForConnected(300):
        probe.write(b"show")
        probe.waitForBytesWritten(300)
        logger.info("Программа уже запущена — показываю существующее окно.")
        return 0

    # [v3, 12.11.2026] Язык интерфейса: ru / uk / en (вкладка «О программе»); первый запуск — язык Windows
    from core import i18n
    from core.settings import AppSettings
    # [v3.2.2, 20.11.2026] Первый запуск — язык окна установщика, затем язык Windows; запоминается
    lang = AppSettings.get("ui/lang")
    if not lang:
        lang = i18n.installer_language(APP_DIR) or i18n.default_language()
        AppSettings.set("ui/lang", lang)
    i18n.set_language(lang)
    i18n.install()

    from gui.main_window import MainWindow
    # Создаем и показываем главное окно
    window = MainWindow()
    i18n.translate_tree(window)
    window.show()

    server = QLocalServer()
    QLocalServer.removeServer(INSTANCE_NAME)
    server.listen(INSTANCE_NAME)
    server.newConnection.connect(lambda: (server.nextPendingConnection(), window.show_from_tray()))

    # [v3.2.2] Обновления: вопрос при первом запуске, потом — тихая проверка раз в сутки, если разрешено
    from PySide6.QtCore import QTimer
    QTimer.singleShot(1500, window.about_tab.startup_updates)

    # Запуск цикла обработки событий Qt
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
