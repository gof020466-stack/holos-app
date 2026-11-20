"""
[v3.2, 18.11.2026] Снимки окон программы — для сверки «до / после» и для README.

Окно строится без побочных действий: горячая клавиша, голосовые команды и автозагрузка модели
выключены, настройки не записываются, вместо личной «Истории» — пробная база с примерами.

Запуск:  python tools\\snapshots.py <папка> [ru|uk|en] [ширина высота]
"""
import os
import sys
import tempfile

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

out_dir = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "snapshots")
lang = sys.argv[2] if len(sys.argv) > 2 else "ru"
size = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else None
os.makedirs(out_dir, exist_ok=True)

from PySide6.QtWidgets import QApplication  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from core import db_manager  # noqa: E402

OVERRIDE = {"dictation/enabled": False, "voice/commands_enabled": False, "model/autoload": False}
_orig_get = AppSettings.get.__func__
AppSettings.get = classmethod(lambda cls, key: OVERRIDE.get(key, _orig_get(cls, key)))
AppSettings.set = classmethod(lambda cls, key, value: OVERRIDE.__setitem__(key, value))

demo_db = os.path.join(tempfile.mkdtemp(), "demo.db")
db_manager.DBManager.__init__.__defaults__ = (demo_db,)
demo = db_manager.DBManager()
demo.add_item("[10:15:02] Созвон с командой", "[0:00] Говорящий 1: Добрый день, начнём с плана на неделю.\n\n"
              "[0:06] Говорящий 2: Согласен. Первым — выпуск версии 3.2.", [], "Звук компьютера и микрофон", None)
demo.add_item("[09:40:11] Запись с микрофона", "Идея для статьи: приватная диктовка без облака.", [],
              "Запись с микрофона", None)

from core import i18n  # noqa: E402
i18n.set_language(lang)
app = QApplication(sys.argv)
i18n.install()
from gui.main_window import MainWindow  # noqa: E402

w = MainWindow()
i18n.translate_tree(w)
if size:
    w.resize(*size)
w.show()
for _ in range(20):
    app.processEvents()

pages = [(str(i), i) for i in range(w.stacked_widget.count())]
# Источники «Новой записи» и вкладки «Настроек» — тоже снимками (Д3, Д4, Д7)
nr, st = w.stacked_widget.indexOf(w.new_record_page), w.stacked_widget.indexOf(w.settings_tab)
for key in ("system", "both", "file"):
    pages.append((f"{nr}-{key}", lambda k=key: (w.switch_tab(nr), w.new_record_page.set_source(k))))
for t in range(1, w.settings_tab.tabs.count()):
    pages.append((f"{st}-{t}", lambda t=t: (w.switch_tab(st), w.settings_tab.tabs.setCurrentIndex(t))))
for name, index in pages:
    w.switch_tab(index) if not callable(index) else index()
    for _ in range(10):
        app.processEvents()
    path = os.path.join(out_dir, f"{lang}-{name}.png")
    w.grab().save(path)
    print(path)
    if lang != "ru":
        # Видимые подписи, оставшиеся по-русски: им нужен перевод в core/i18n.py
        import re
        from PySide6 import QtWidgets as W
        for ch in w.findChildren(W.QWidget):
            if not ch.isVisible():
                continue
            texts = []
            if isinstance(ch, (W.QLabel, W.QAbstractButton)):
                texts.append(ch.text())
            if isinstance(ch, W.QTabWidget):
                texts += [ch.tabText(i) for i in range(ch.count())]
            for t in texts:
                # en — любая кириллица; uk — буквы, которых нет в украинском (ы, э, ъ, ё)
                if re.search("[а-яё]" if lang == "en" else "[ыэъё]", t or "", re.I):
                    print("  НЕТ ПЕРЕВОДА:", repr(t))
w._really_quit = True
w.dictation_manager.shutdown()
w.tray.hide()
