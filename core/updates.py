"""
[v3.2.2, 20.11.2026] Проверка обновлений на GitHub.
Решено 19.11.2026:
один вопрос при первом запуске («Проверять обновления на GitHub?»), меняется в «Настройках»;
кнопка «Проверить обновления» в «О программе».
Конфиденциальность: запрос — только чтение страницы релизов, с компьютера ничего не уходит,
кроме самого запроса. Без согласия человека запроса нет (кнопка или «да» на вопросе).
"""
import json
import logging
import time
import urllib.request

from PySide6.QtCore import QThread, Signal

VERSION = "3.2.5"
VERSION_DATE = "22.11.2026"
# Адрес открытого репозитория — один на всю программу
REPO = "gof020466-stack/holos-app"
RELEASES_URL = f"https://github.com/{REPO}/releases"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
AUTO_INTERVAL = 24 * 3600  # автопроверка при запуске — не чаще раза в сутки

logger = logging.getLogger("Updates")


def _parse(v: str) -> tuple:
    parts = []
    for p in v.strip().lstrip("vV").split("."):
        num = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(num) if num else 0)
    return tuple(parts)


def is_newer(remote: str, local: str = VERSION) -> bool:
    return _parse(remote) > _parse(local)


def fetch_latest(timeout: float = 10.0) -> dict:
    """{'version', 'url'} последнего релиза. Ошибка сети или нет релизов — исключение.
    [3.3, 22.11.2026] Сначала — переход со страницы /releases/latest на /releases/tag/vX.Y.Z:
    у страниц сайта нет лимита API (60 запросов в час на адрес, общий у многих людей).
    API — запасной путь."""
    try:
        req = urllib.request.Request(f"{RELEASES_URL}/latest", method="HEAD",
                                     headers={"User-Agent": "Holos-update-check"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final = resp.geturl()
        if "/releases/tag/" in final:
            return {"version": final.rsplit("/", 1)[-1], "url": final}
    except Exception as e:
        logger.info("Страница релизов не ответила, пробую API: %s", e)
    req = urllib.request.Request(API_URL, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": "Holos-update-check"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return {"version": data.get("tag_name", ""), "url": data.get("html_url") or RELEASES_URL}


class UpdateChecker(QThread):
    """Проверка в фоне: окно не замирает. found(версия, адрес) / latest() / failed(текст)."""
    found = Signal(str, str)
    latest = Signal()
    failed = Signal(str)

    def run(self):
        try:
            info = fetch_latest()
        except Exception as e:  # нет сети, репозиторий закрыт, релизов нет
            logger.info("Проверка обновлений не удалась: %s", e)
            self.failed.emit(str(e))
            return
        if info["version"] and is_newer(info["version"]):
            logger.info("Есть новая версия: %s", info["version"])
            self.found.emit(info["version"].lstrip("vV"), info["url"])
        else:
            self.latest.emit()


def auto_check_due(last: float) -> bool:
    return time.time() - (last or 0) >= AUTO_INTERVAL
