import re
from typing import List, Dict, Any, Optional

# Вопросительные слова в русском языке
QUESTION_STARTERS = {
    "как", "почему", "зачем", "когда", "где", "куда", "откуда", 
    "сколько", "кто", "что", "чей", "чья", "чье", "чьи",
    "какой", "какая", "какое", "какие", "каком", "какой", "какую",
    "кому", "чему", "кого", "чего", "кем", "чем", "ком", "чем",
    "неужели", "разве"
}

# [v3] Вопрос — только по однозначным признакам. «как/что/когда» в начале фразы
# в диктовке чаще союзы («отражается как новый абзац»), по ним «?» ставился ошибочно
QUESTION_PARTICLES = {"ли", "разве", "неужели"}

# Союзы и вводные слова, перед которыми почти всегда ставится запятая
# [v3] Убраны «как/где/куда/откуда»: в середине фразы они чаще без запятой
COMMA_WORDS = {
    "а", "но", "однако", "что", "чтобы", "если", "хотя",
    "потому", "поэтому", "который", "которая", "которое", "которые",
    "которого", "которой", "которых", "которому", "которым",
    "будто", "словно"
}

# [v3] После этих слов запятая перед союзом не ставится («и что делали», «а если»)
NO_COMMA_AFTER = {"и", "или", "а", "но", "да", "ни", "не", "же", "то"}

# Известные имена собственные и бренды для автоматической капитализации
PROPER_NAMES = {
    "россия", "россии", "россией", "рф", "москва", "москвы", "москве",
    "санкт-петербург", "питер", "петербург",
    "windows", "linux", "macos", "android", "ios",
    "vosk", "kaldi", "ffmpeg", "python", "pyside", "qt",
    "google", "yandex", "яндекс", "сбер", "microsoft", "telegram", "телеграм"
}

class Punctuator:
    """
    Интеллектуальный модуль локальной постобработки текста:
    расстановка заглавных букв, знаков препинания и пауз.
    """

    @staticmethod
    def _is_question(words: List[str]) -> bool:
        return any(w.rstrip(",").lower() in QUESTION_PARTICLES for w in words)

    @staticmethod
    def punctuate_words_with_timing(words: List[Dict[str, Any]],
                                     sentence_pause: float = 0.75,
                                     comma_pause: float = 0.35,
                                     paragraph_pause: Optional[float] = None) -> str:
        """
        Восстанавливает пунктуацию и регистр на основе таймингов слов Vosk.
        Используется для аудиофайлов и [v3] для записи с микрофона.
        paragraph_pause — пауза (с), после которой начинается новый абзац; None — без абзацев.
        """
        if not words:
            return ""
        # [v3] Parakeet ставит знаки и заглавные сам — оставляем его текст, добавляем только абзацы
        if any(str(w.get("word", "")).rstrip()[-1:] in ".,!?…" for w in words if w.get("word")):
            return Punctuator._join_punctuated(words, paragraph_pause)

        paragraphs = []
        sentences = []
        current_sentence = []

        for i, word_info in enumerate(words):
            word_str = str(word_info.get("word", "")).strip().lower()
            if not word_str:
                continue

            end = float(word_info.get("end", 0.0))

            current_sentence.append(word_str)

            # Проверяем паузу до следующего слова
            is_last_word = (i == len(words) - 1)
            pause_after = 0.0
            if not is_last_word:
                next_start = float(words[i + 1].get("start", end))
                pause_after = max(0.0, next_start - end)

            # Закрываем предложение при паузе >= sentence_pause или в конце записи
            if is_last_word or pause_after >= sentence_pause:
                end_punct = "?" if Punctuator._is_question(current_sentence) else "."
                sentences.append(Punctuator._format_single_sentence(current_sentence, end_punct))
                current_sentence = []
                if paragraph_pause is not None and pause_after >= paragraph_pause:
                    paragraphs.append(" ".join(sentences))
                    sentences = []
            elif pause_after >= comma_pause or (str(words[i + 1].get("word", "")).lower() in COMMA_WORDS
                                                and word_str not in NO_COMMA_AFTER):
                # Добавляем запятую перед союзами или при ощутимой паузе
                if not current_sentence[-1].endswith(","):
                    current_sentence[-1] += ","

        if sentences:
            paragraphs.append(" ".join(sentences))
        return "\n\n".join(p for p in paragraphs if p)

    @staticmethod
    def _join_punctuated(words: List[Dict[str, Any]], paragraph_pause: Optional[float]) -> str:
        """[v3] Текст модели со знаками: новый абзац — после конца предложения и длинной паузы."""
        out = ""
        for i, w in enumerate(words):
            word = str(w.get("word", "")).strip()
            if not word:
                continue
            if out:
                pause = float(w.get("start", 0)) - float(words[i - 1].get("end", 0))
                new_par = paragraph_pause is not None and pause >= paragraph_pause and out[-1] in ".!?…"
                out += "\n\n" if new_par else " "
            out += word
        return out

    @staticmethod
    def punctuate_plain_text(raw_text: str = "", chunks: Optional[List[str]] = None) -> str:
        """
        Восстанавливает пунктуацию и заглавные буквы для обычного текста (например, с микрофона).
        Если передан список фраз chunks, каждая фраза рассматривается как отдельное высказывание.
        """
        # Если переданы фрагменты Vosk-распознавания (chunks), форматируем каждый
        if chunks and len(chunks) > 0:
            formatted_chunks = []
            for chunk in chunks:
                chunk = chunk.strip()
                if not chunk:
                    continue
                words = chunk.split()
                end_mark = "?" if Punctuator._is_question(words) else "."
                formatted_chunks.append(Punctuator._format_single_sentence(words, end_mark))
            return " ".join(formatted_chunks)

        if not raw_text or not raw_text.strip():
            return ""

        # [v3] Абзацы сохраняются: в v2/v3.0 split() склеивал весь текст в один абзац
        paragraphs = [p.strip() for p in raw_text.splitlines() if p.strip()]
        return "\n\n".join(Punctuator._punctuate_paragraph(p) for p in paragraphs)

    @staticmethod
    def _punctuate_paragraph(paragraph: str) -> str:
        # [v3] Абзац уже со знаками — только чистка. Повторная расстановка поверх
        # старых знаков давала «удобно., а?»
        if re.search(r"[.!?]", paragraph):
            return Punctuator._normalize_paragraph(paragraph)

        # Иначе обрабатываем сплошной текст эвристиками
        words = paragraph.lower().split()
        sentences = []
        current_sentence = []

        for i, word in enumerate(words):
            current_sentence.append(word)

            # Ставим запятую перед союзами, если это не первое слово
            if i + 1 < len(words):
                next_w = words[i + 1]
                if (next_w in COMMA_WORDS and word not in NO_COMMA_AFTER and len(current_sentence) >= 3
                        and not current_sentence[-1].endswith(",")):
                    current_sentence[-1] += ","

            # Без таймингов границы предложений неизвестны — делим по длине
            if i == len(words) - 1 or len(current_sentence) >= 12:
                end_mark = "?" if Punctuator._is_question(current_sentence) else "."
                sentences.append(Punctuator._format_single_sentence(current_sentence, end_mark))
                current_sentence = []

        return " ".join(sentences)

    @staticmethod
    def _normalize_paragraph(text: str) -> str:
        """
        [v3] Чистит уже расставленные знаки: пробел перед знаком, двойные знаки,
        строчная буква после конца предложения.
        """
        text = re.sub(r"\s+([,.!?])", r"\1", text)
        text = re.sub(r",+([.!?])", r"\1", text)
        text = re.sub(r"([.!?])[.,!?]+", r"\1", text)
        text = re.sub(r"([.!?]\s+)(\w)", lambda m: m.group(1) + m.group(2).upper(), text)
        text = re.sub(r"\s{2,}", " ", text).strip().rstrip(",")
        if text:
            text = text[0].upper() + text[1:]
            if not text.endswith((".", "!", "?")):
                text += "."
        return text

    @staticmethod
    def _format_single_sentence(words: List[str], end_punctuation: str = ".") -> str:
        """
        Форматирует одиночное предложение: капитализация первого слова,
        заглавные буквы для имен собственных, закрывающий знак.
        """
        if not words:
            return ""

        formatted_words = []
        for i, w in enumerate(words):
            has_comma = w.endswith(",")
            clean_w = w.rstrip(",")

            # Первое слово с большой буквы
            if i == 0:
                clean_w = clean_w.capitalize()
            elif clean_w in PROPER_NAMES:
                clean_w = clean_w.capitalize()

            if has_comma:
                clean_w += ","

            formatted_words.append(clean_w)

        text = " ".join(formatted_words).strip()
        # Убираем запятую на конце перед точкой, если случайно оказалась
        text = text.rstrip(",")
        
        # Добавляем финальный знак
        if not text.endswith((".", "!", "?")):
            text += end_punctuation

        return text
