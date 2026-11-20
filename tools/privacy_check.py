"""
Проверка на личное перед публикацией кода или релиза (20.11.2026).

Поиск по тексту не видит картинок и других нетекстовых файлов: снимок окна
с личной надиктовкой однажды ушёл в открытый репозиторий именно так.
Поэтому скрипт делает две вещи:
  1) ищет личные строки во всех текстовых файлах под git;
  2) перечисляет ВСЕ нетекстовые файлы — каждый человек или Claude открывает
     глазами и пишет в отчёт «открыт, личного нет».
Без второго списка, пройденного целиком, публиковать нельзя.

Запуск: python -X utf8 tools\\privacy_check.py [папка]   (по умолчанию — корень репозитория)
Личные строки — в файле tools\\privacy_patterns.txt рядом (в git не входит).
"""
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..'))
PATTERNS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'privacy_patterns.txt')
GENERIC = [
    r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}',   # почта
    r'\+?\d[\d \-()]{9,}\d',                           # телефон
    r'[A-Za-z]:\\Users\\',                             # путь профиля Windows
]


def tracked_files():
    out = subprocess.run(['git', '-C', ROOT, 'ls-files', '-z'], capture_output=True)
    if out.returncode == 0 and out.stdout:
        return [f for f in out.stdout.decode('utf-8').split('\0') if f]
    files = []
    for d, _, names in os.walk(ROOT):
        if '.git' in d.split(os.sep):
            continue
        files += [os.path.relpath(os.path.join(d, n), ROOT) for n in names]
    return files


def is_text(path):
    with open(path, 'rb') as f:
        chunk = f.read(8192)
    if b'\0' in chunk:
        return False
    try:
        chunk.decode('utf-8')
        return True
    except UnicodeDecodeError as e:
        # кусок обрезан посреди многобайтной буквы — это всё ещё текст
        return e.start >= len(chunk) - 3 and len(chunk) == 8192


def main():
    personal = []
    if os.path.exists(PATTERNS_FILE):
        with open(PATTERNS_FILE, encoding='utf-8') as f:
            personal = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    else:
        print(f'! Нет {PATTERNS_FILE} — проверяются только почта, телефоны, пути профиля.')
    rx = re.compile('|'.join(GENERIC + [r'\b' + re.escape(p) + r'\b' for p in personal]), re.IGNORECASE)

    hits, binaries = [], []
    for rel in tracked_files():
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            continue
        if not is_text(path):
            binaries.append((rel, os.path.getsize(path)))
            continue
        with open(path, encoding='utf-8', errors='replace') as f:
            for i, line in enumerate(f, 1):
                m = rx.search(line)
                if m:
                    hits.append(f'{rel}:{i}: {m.group(0)}')

    print(f'== Личные строки в тексте: {len(hits)}')
    for h in hits:
        print('  ' + h)
    print(f'== Нетекстовые файлы — открыть КАЖДЫЙ глазами: {len(binaries)}')
    for rel, size in binaries:
        print(f'  [ ] {rel}  ({size // 1024} КБ)')
    return 1 if hits else 0


if __name__ == '__main__':
    sys.exit(main())
