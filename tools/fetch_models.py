# Модели для сборки «Голоса» — из первоисточников, с проверкой каждого файла — 22.11.2026
#
# Зачем: сборка в GitHub Actions (условие SignPath) не видит D:\Apps\VOSK_BASE\models.
# Скрипт скачивает модели с сайтов авторов (tools/models_sources.json) и сверяет каждый файл
# по SHA256 со списком tools/models.lock.json — тем набором, что проверен на ПК разработчика.
# Лишние файлы архивов отбрасываются; не хватает файла или хеш другой — сборка падает.
#
#   python -X utf8 tools\fetch_models.py <папка>               — скачать и проверить
#   python -X utf8 tools\fetch_models.py --lock D:\Apps\VOSK_BASE\models — записать models.lock.json
import hashlib, json, os, shutil, sys, tarfile, tempfile, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.path.join(HERE, 'models_sources.json')
LOCK = os.path.join(HERE, 'models.lock.json')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def make_lock(models_dir):
    lock = {}
    for model in load(SOURCES):
        root = os.path.join(models_dir, model)
        files = {}
        for r, _, fs in os.walk(root):
            for n in fs:
                p = os.path.join(r, n)
                files[os.path.relpath(p, root).replace(os.sep, '/')] = sha256(p)
        lock[model] = dict(sorted(files.items()))
        print(f'{model}: {len(files)} файлов')
    with open(LOCK, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(lock, f, ensure_ascii=False, indent=1)
        f.write('\n')


def download(url, dest):
    print(f'   ← {url}', flush=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'holos-build'})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, 'wb') as f:
        shutil.copyfileobj(r, f, 1 << 20)


def unpack(archive, kind, into):
    if kind == 'zip':
        with zipfile.ZipFile(archive) as z:
            z.extractall(into)
    else:
        with tarfile.open(archive, 'r:*') as t:
            t.extractall(into, filter='data')


def fetch(out_dir):
    sources, lock = load(SOURCES), load(LOCK)
    os.makedirs(out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='holos-models-')
    bad = []
    try:
        for model, items in sources.items():
            print(f'==> {model}', flush=True)
            stage = os.path.join(tmp, 'stage', model)
            os.makedirs(stage, exist_ok=True)
            for i, it in enumerate(items):
                dl = os.path.join(tmp, f'{model}.{i}')
                download(it['url'], dl)
                if it['type'] == 'file':
                    target = os.path.join(stage, *it['to'].split('/'))
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    shutil.move(dl, target)
                    continue
                x = os.path.join(tmp, f'x{i}-{model}')
                unpack(dl, it['type'], x)
                os.remove(dl)
                src = os.path.join(x, *it.get('strip', '').split('/')) if it.get('strip') else x
                dst = os.path.join(stage, *it['to'].split('/')) if it.get('to') else stage
                shutil.copytree(src, dst, dirs_exist_ok=True)
                shutil.rmtree(x)
            final = os.path.join(out_dir, model)
            if os.path.exists(final):
                shutil.rmtree(final)
            for rel, want in lock[model].items():
                p = os.path.join(stage, *rel.split('/'))
                if not os.path.isfile(p):
                    bad.append(f'{model}/{rel}: нет файла')
                    continue
                if sha256(p) != want:
                    bad.append(f'{model}/{rel}: хеш другой')
                    continue
                t = os.path.join(final, *rel.split('/'))
                os.makedirs(os.path.dirname(t), exist_ok=True)
                shutil.move(p, t)
            print(f'   проверено файлов: {len(lock[model])}', flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('МОДЕЛИ НЕ СОВПАЛИ С ПРОВЕРЕННЫМ НАБОРОМ:\n  ' + '\n  '.join(bad))
    print('МОДЕЛИ ГОТОВЫ — все файлы совпали по SHA256')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--lock':
        make_lock(sys.argv[2])
    elif len(sys.argv) == 2:
        fetch(sys.argv[1])
    else:
        sys.exit(__doc__ or 'см. шапку файла')
