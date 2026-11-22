# Сборка установщика «Голос» (Holos) для Windows — 12.11.2026
#
# Что делает:
#   1) runtime\  — копия Python 3.13 без site-packages + библиотеки программы (pip --target);
#   2) app\      — исходники программы (без data, tools, __pycache__);
#   3) app\models — рабочий набор моделей из D:\Apps\VOSK_BASE\models;
#   4) app\bin\ffmpeg.exe — для записи звука и аудиофайлов;
#   5) ISCC (Inno Setup) → dist\Holos-Setup-<версия>.exe.
# Установка — в %LOCALAPPDATA%\Programs\Holos, без прав администратора; данные — в app\data.
# Запуск: python -X utf8 tools\build_installer.py   (интернет нужен для pip)
import os, shutil, subprocess, sys, glob

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# [22.11.2026] Пути — из переменных среды для сборки в GitHub Actions (.github/workflows/build.yml);
# без них — как на ПК разработчика
BUILD = os.environ.get('HOLOS_BUILD') or r'D:\Apps\holos-build'
STAGE = os.path.join(BUILD, 'Holos')
PY = os.path.dirname(sys.executable)
MODELS_SRC = os.environ.get('HOLOS_MODELS') or r'D:\Apps\VOSK_BASE\models'
MODELS = ['sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16', 'vosk-model-small-streaming-ru-0.54',
          'vosk-model-small-ru-0.22', 'diarization', 'parakeet-ultra-onnx']
PACKAGES = ['PySide6==6.11.1', 'vosk==0.3.45', 'sherpa-onnx==2.0.1', 'sounddevice==0.5.2', 'soundfile==0.13.1',
            'numpy==2.3.3', 'requests==2.32.5', 'QtAwesome==1.4.2', 'srt==3.5.3', 'keyboard==0.13.5',
            'onnx-asr==0.12.0', 'onnxruntime==1.31.1', 'PyAudioWPatch==0.2.12.9']
ISCC = os.environ.get('HOLOS_ISCC') or os.path.expandvars(r'%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe')

# Части Qt, которых программа не использует (Core, Gui, Widgets, Network, Multimedia — нужны)
QT_DROP = ['Qt6WebEngine*', 'QtWebEngineProcess*', 'Qt6Quick3D*', 'Qt63D*', 'Qt6Pdf*', 'Qt6Designer*', 'Qt6Charts*',
           'Qt6DataVisualization*', 'Qt6Graphs*', 'Qt6Location*', 'Qt6Bluetooth*', 'Qt6Sensors*', 'Qt6SerialPort*',
           'Qt6RemoteObjects*', 'Qt6Scxml*', 'Qt6SpatialAudio*', 'Qt6TextToSpeech*', 'Qt6WebView*', 'Qt6VirtualKeyboard*',
           'Qt6ShaderTools*', 'Qt6Help*', 'Qt6Test*', 'Qt6Positioning*', 'Qt6Nfc*', 'Qt6HttpServer*', 'Qt63D*',
           'designer.exe', 'linguist.exe', 'assistant.exe', 'lupdate.exe', 'lrelease.exe', 'qmlls.exe', 'qmllint.exe',
           'qmlformat.exe', 'balsam.exe', 'balsamui.exe', 'qsb.exe', 'svgtoqml.exe', 'pyside6-*.exe']
QT_DROP_DIRS = ['examples', 'translations', 'resources', 'qml', 'include', 'doc', 'typesystems', 'glue', 'scripts']


def step(t):
    print('==>', t, flush=True)


def size_mb(path):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(path) for f in fs) / 2**20


def build_runtime():
    rt = os.path.join(STAGE, 'runtime')
    step('Python → runtime')
    skip = {'site-packages', 'test', 'idlelib', 'tkinter', 'turtledemo', 'ensurepip', '__pycache__'}
    shutil.copytree(PY, rt, ignore=lambda d, names: [n for n in names if n in skip or n in ('Scripts', 'Doc', 'include', 'libs', 'tcl', 'Tools')])
    sp = os.path.join(rt, 'Lib', 'site-packages')
    os.makedirs(sp, exist_ok=True)
    step('библиотеки (pip)')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-warn-script-location', '--disable-pip-version-check', '-q',
                    '--target', sp, *PACKAGES], check=True)
    for d in glob.glob(os.path.join(sp, '*', '__pycache__')) + glob.glob(os.path.join(sp, 'bin')):
        shutil.rmtree(d, ignore_errors=True)
    qt = os.path.join(sp, 'PySide6')
    for pat in QT_DROP:
        for f in glob.glob(os.path.join(qt, pat)):
            os.remove(f) if os.path.isfile(f) else shutil.rmtree(f)
    for d in QT_DROP_DIRS:
        shutil.rmtree(os.path.join(qt, d), ignore_errors=True)
    # [22.11.2026] Проба в песочнице Windows: на чистой системе onnxruntime (Parakeet) не грузится —
    # нет msvcp140*.dll (Visual C++). Python везёт только vcruntime140*. Кладём их рядом с python.exe.
    for n in ('msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll'):
        src = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', n)
        if not os.path.isfile(src):
            sys.exit(f'Нет {src}: поставьте Visual C++ Redistributable x64 на ПК сборки')
        shutil.copy2(src, rt)
    print(f'   runtime: {size_mb(rt):.0f} МБ')


def build_app():
    app = os.path.join(STAGE, 'app')
    step('программа → app')
    os.makedirs(app)
    for n in ['core', 'gui', 'utils']:
        shutil.copytree(os.path.join(SRC, n), os.path.join(app, n), ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for n in ['main.py', 'LICENSE', 'THIRD_PARTY_LICENSES.md', 'README.md', 'requirements.txt']:
        if os.path.exists(os.path.join(SRC, n)):
            shutil.copy2(os.path.join(SRC, n), app)
    step('модели → app\\models')
    for m in MODELS:
        shutil.copytree(os.path.join(MODELS_SRC, m), os.path.join(app, 'models', m))
    # [20.11.2026] Только сборка LGPL: GPL-сборка требует выкладывать её исходники (THIRD_PARTY_LICENSES.md).
    # Источник: FFmpeg-Builds, вариант win64-lgpl; ffmpeg.exe и LICENSE-ffmpeg.txt — в FFMPEG_DIR.
    step('ffmpeg (LGPL) → app\\bin')
    ff = os.environ.get('HOLOS_FFMPEG') or os.path.join(BUILD, 'ffmpeg-lgpl', 'ffmpeg.exe')
    if not os.path.isfile(ff):
        sys.exit(f'Нет {ff}: скачайте ffmpeg win64-lgpl (FFmpeg-Builds) или задайте HOLOS_FFMPEG')
    conf = subprocess.run([ff, '-hide_banner', '-version'], capture_output=True, text=True).stdout
    if '--enable-gpl' in conf:
        sys.exit(f'{ff} — сборка GPL; нужна LGPL')
    os.makedirs(os.path.join(app, 'bin'))
    shutil.copy2(ff, os.path.join(app, 'bin', 'ffmpeg.exe'))
    lic = os.path.join(os.path.dirname(ff), 'LICENSE-ffmpeg.txt')
    if os.path.isfile(lic):
        shutil.copy2(lic, os.path.join(app, 'bin'))
    print(f'   app: {size_mb(app):.0f} МБ')


def check_no_personal():
    # [22.11.2026] В установку идёт версия без каких-либо записей. Сборка падает,
    # если в app есть data, база, настройки, журнал или звук вне образцов моделей (test.wav, test_wavs)
    bad = []
    app = os.path.join(STAGE, 'app')
    for root, dirs, files in os.walk(app):
        rel = os.path.relpath(root, app)
        if 'data' in rel.split(os.sep):
            bad.append(rel)
        for f in files:
            low = f.lower()
            in_models = rel.split(os.sep)[0] == 'models'
            if low.endswith(('.db', '.sqlite', '.ini', '.log', '.kdbx')) or (
                    low.endswith(('.wav', '.mp3', '.ogg', '.flac', '.m4a', '.webm', '.opus')) and not in_models):
                bad.append(os.path.join(rel, f))
    if bad:
        sys.exit('ЛИЧНОЕ В СБОРКЕ — установщик не собран:\n  ' + '\n  '.join(bad))
    print('   личного в app нет (data, база, настройки, журнал, записи)')


def build_setup(test=False):
    check_no_personal()
    # [18.11.2026] модели отдельно: полный Holos-Setup и Holos-Update без моделей — из одной папки сборки
    iss = os.path.join(SRC, 'installer', 'holos.iss')
    out = os.path.join(BUILD, 'dist-test' if test else 'dist')
    extra = ['/DTest=1'] if test else []
    for name, flags in (('полный (с моделями)', []), ('обновление (без моделей)', ['/DUpdate=1'])):
        step(f'установщик (Inno Setup): {name}')
        subprocess.run([ISCC, '/Q', f'/DStage={STAGE}', f'/DOut={out}', *extra, *flags, iss], check=True)
    for f in glob.glob(os.path.join(out, '*.exe')):
        print(f'   {f}: {os.path.getsize(f) / 2**20:.0f} МБ')


if __name__ == '__main__':
    # --setup-only — только установщики из готовой папки сборки; --test — отдельный AppId «Holos-Test» для проверки
    test = '--test' in sys.argv
    if '--setup-only' not in sys.argv:
        if os.path.exists(STAGE):
            shutil.rmtree(STAGE)
        os.makedirs(STAGE)
        build_runtime()
        build_app()
    build_setup(test)
    print('ГОТОВО')
