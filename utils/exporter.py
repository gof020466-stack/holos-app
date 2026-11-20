import json
import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger("Exporter")


def build_markdown(title: str, text: str, created_at: str, duration_s: float = 0.0) -> tuple:
    """
    [v3.2, 18.11.2026] Ф3: заметка Markdown для базы Obsidian — как голосовая заметка:
    свойство «источник: голос», имя «Мысли от ГГГГ-ММ-ДД ЧЧ-ММ».
    Возвращает (имя файла без пути, содержимое).
    """
    from core.i18n import tr
    try:
        when = datetime.strptime(created_at[:19], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        when = datetime.now()
    clean_title = re.sub(r"^\[\d{1,2}:\d{2}(:\d{2})?\]\s*", "", tr(title or "")).strip() or tr("Запись")
    speakers = len(set(re.findall(r"Говорящий (\d+)", text or "")))
    duration = ""
    if duration_s and duration_s > 0:
        s = int(round(duration_s))
        duration = f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"
    # Свойства — русскими ключами: их удобно искать в Obsidian
    props = ["---", "источник: голос", f"дата: {when:%Y-%m-%d %H:%M}"]
    if duration:
        props.append(f"длительность: \"{duration}\"")
    if speakers:
        props.append(f"говорящие: {speakers}")
    props.append("---")
    facts = [f"**{tr('Дата')}:** {when:%d.%m.%Y %H:%M}"]
    if duration:
        facts.append(f"**{tr('Длительность')}:** {duration}")
    if speakers:
        facts.append(f"**{tr('Говорящие')}:** {speakers}")
    body = "\n".join(props) + f"\n\n# {clean_title}\n\n" + " · ".join(facts) + "\n\n" + (text or "").strip() + "\n"
    name = tr(f"Мысли от {when:%Y-%m-%d %H-%M}") + ".md"
    return name, body


def unique_path(folder: str, name: str) -> str:
    """Имя занято — «… (2).md», «… (3).md»: чужой файл не перезаписывается."""
    base, ext = os.path.splitext(name)
    path, n = os.path.join(folder, name), 2
    while os.path.exists(path):
        path, n = os.path.join(folder, f"{base} ({n}){ext}"), n + 1
    return path

def format_time_srt(seconds: float) -> str:
    """
    Форматирует секунды в формат SRT: HH:MM:SS,mmm
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def words_to_srt(words: List[Dict[str, Any]], max_words: int = 8, max_pause: float = 1.5) -> str:
    """
    Группирует список слов с таймингами Vosk в блоки субтитров SRT.
    """
    if not words:
        return ""

    srt_entries = []
    current_chunk = []
    chunk_start = 0.0
    entry_idx = 1

    for i, word_info in enumerate(words):
        word = word_info.get("word", "")
        start = word_info.get("start", 0.0)
        end = word_info.get("end", 0.0)

        if not current_chunk:
            chunk_start = start

        current_chunk.append(word)

        # Условия для закрытия текущего субтитра:
        # 1. Достигнуто макс. количество слов в строке
        # 2. Это последнее слово
        # 3. Пауза до следующего слова больше заданного значения (max_pause)
        is_last = (i == len(words) - 1)
        long_pause = False
        if not is_last:
            next_start = words[i+1].get("start", 0.0)
            long_pause = (next_start - end > max_pause)

        if len(current_chunk) >= max_words or is_last or long_pause:
            start_str = format_time_srt(chunk_start)
            end_str = format_time_srt(end)
            text = " ".join(current_chunk)

            srt_entries.append(f"{entry_idx}\n{start_str} --> {end_str}\n{text}\n")
            
            entry_idx += 1
            current_chunk = []

    return "\n".join(srt_entries)

class Exporter:
    @staticmethod
    def save_txt(text: str, file_path: str) -> bool:
        """
        Сохраняет обычный текст в файл.
        """
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info(f"Текст успешно сохранен в TXT: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Не удалось сохранить TXT: {e}")
            return False

    @staticmethod
    def save_srt(words: List[Dict[str, Any]], file_path: str, max_words: int = 8) -> bool:
        """
        Сохраняет список слов в виде файла субтитров SRT.
        """
        try:
            srt_content = words_to_srt(words, max_words=max_words)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            logger.info(f"Субтитры успешно сохранены в SRT: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Не удалось сохранить SRT: {e}")
            return False

    @staticmethod
    def save_json(words: List[Dict[str, Any]], full_text: str, file_path: str) -> bool:
        """
        Сохраняет полную структуру (текст и тайминги слов) в JSON.
        """
        try:
            data = {
                "text": full_text,
                "words": words
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info(f"Данные успешно сохранены в JSON: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Не удалось сохранить JSON: {e}")
            return False

    @staticmethod
    def save_md(title: str, text: str, created_at: str, folder: str, duration_s: float = 0.0) -> Optional[str]:
        """[v3.2] Ф3: заметка .md в папку (по умолчанию — «00_Входящие» базы). Путь или None."""
        try:
            os.makedirs(folder, exist_ok=True)
            name, body = build_markdown(title, text, created_at, duration_s)
            path = unique_path(folder, name)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(body)
            logger.info(f"Заметка Markdown сохранена: {path}")
            return path
        except Exception as e:
            logger.error(f"Не удалось сохранить Markdown: {e}")
            return None
