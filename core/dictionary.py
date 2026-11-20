"""
[v3] Словарь пользователя (29.10.2026): горячие слова для движка 0.54
и замены после распознавания («эф восемь» → «F8»).

Источник — заметка в базе Obsidian (её же читает Claude при чистке голосовых заметок):
  ## Таблица замен — строки «| вариант, вариант | что сказано |»
  ## Горячие слова — строки «- слово, слово»
Модель 0.54 знает только кириллицу: латиница («F8», «Obsidian») появляется только через замены.
"""
import os
import re
import struct
import logging
from typing import List, Tuple

from core.settings import AppSettings

logger = logging.getLogger("Dictionary")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

_cache = {"mtime": None, "replacements": [], "hotwords": []}


def _section(lines: List[str], title: str) -> List[str]:
    out, inside = [], False
    for line in lines:
        if line.startswith("## "):
            inside = line[3:].strip().lower().startswith(title)
            continue
        if inside:
            out.append(line.strip())
    return out


def _load():
    path = AppSettings.get("dict/path")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        if _cache["mtime"] is not None:
            logger.warning(f"Словарь не найден: {path}")
        _cache.update(mtime=None, replacements=[], hotwords=[])
        return
    if mtime == _cache["mtime"]:
        return
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    replacements: List[Tuple[re.Pattern, str]] = []
    for row in _section(lines, "таблица замен"):
        cells = [c.strip() for c in row.strip("|").split("|")] if row.startswith("|") else []
        if len(cells) < 2 or not cells[1] or set(cells[0]) <= set("-: ") or cells[0].lower() == "vosk":
            continue
        for variant in (v.strip() for v in cells[0].split(",")):
            if variant:
                # Между словами варианта VOSK мог поставить запятую или точку
                body = r"[\s,.]+".join(re.escape(w) for w in variant.split())
                replacements.append((re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE), cells[1]))
    # Длинные варианты первыми: «эф восемь» раньше «восемь»
    replacements.sort(key=lambda r: -len(r[0].pattern))

    hotwords = []
    for row in _section(lines, "горячие слова"):
        if row.startswith("- "):
            hotwords += [w.strip().lower() for w in row[2:].split(",") if w.strip()]

    _cache.update(mtime=mtime, replacements=replacements, hotwords=hotwords)
    logger.info(f"Словарь загружен: замен {len(replacements)}, горячих слов {len(hotwords)}")


def apply_replacements(text: str) -> str:
    """Замены после распознавания. Файл перечитывается, если его правили."""
    _load()
    for pattern, target in _cache["replacements"]:
        # Замена в начале предложения сохраняет заглавную букву
        text = pattern.sub(lambda m: target[:1].upper() + target[1:]
                           if m.group(0)[:1].isupper() and target[:1].islower() else target, text)
    return text


def _bpe_pieces(model_path: str) -> List[Tuple[str, float]]:
    """Части слов и их веса из bpe.model (protobuf SentencePiece) — без установки sentencepiece."""
    def varint(b, i):
        r = s = 0
        while True:
            c = b[i]
            i += 1
            r |= (c & 0x7F) << s
            s += 7
            if c < 0x80:
                return r, i

    b = open(model_path, "rb").read()
    i, out = 0, []
    while i < len(b):
        key, i = varint(b, i)
        field, wire = key >> 3, key & 7
        if wire == 2:
            n, i = varint(b, i)
            if field == 1:
                sub, j, piece, score = b[i:i + n], 0, None, 0.0
                while j < len(sub):
                    k, j = varint(sub, j)
                    if k & 7 == 2:
                        m, j = varint(sub, j)
                        if k >> 3 == 1:
                            piece = sub[j:j + m].decode("utf-8")
                        j += m
                    elif k & 7 == 5:
                        if k >> 3 == 2:
                            score = struct.unpack("<f", sub[j:j + 4])[0]
                        j += 4
                    elif k & 7 == 0:
                        _, j = varint(sub, j)
                if piece is not None:
                    out.append((piece, score))
            i += n
        elif wire == 0:
            _, i = varint(b, i)
        elif wire == 5:
            i += 4
        elif wire == 1:
            i += 8
    return out


def hotwords_options(model_dir: str) -> dict:
    """
    Параметры горячих слов для sherpa-onnx. Пусто — если слов нет или у модели нет bpe.model.
    Горячие слова применяются при загрузке модели: после правки списка модель перезагрузить.
    """
    _load()
    words = _cache["hotwords"]
    bpe_model = os.path.join(model_dir, "lang", "bpe.model")
    if not words or not os.path.isfile(bpe_model):
        return {}
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        name = os.path.basename(model_dir.rstrip("\\/"))
        vocab = os.path.join(DATA_DIR, f"{name}.bpe.vocab")
        if not os.path.isfile(vocab):
            with open(vocab, "w", encoding="utf-8") as f:
                for piece, score in _bpe_pieces(bpe_model):
                    f.write(f"{piece}\t{score}\n")
        hotwords = os.path.join(DATA_DIR, "hotwords.txt")
        with open(hotwords, "w", encoding="utf-8") as f:
            f.write("\n".join(words) + "\n")
        return dict(hotwords_file=hotwords, hotwords_score=AppSettings.get("dict/hotwords_score"),
                    modeling_unit="bpe", bpe_vocab=vocab)
    except Exception as e:
        logger.error(f"Горячие слова не подключены: {e}")
        return {}
