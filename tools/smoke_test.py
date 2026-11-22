# Проба собранной программы — 22.11.2026
# Запуск — Python из сборки: <сборка>\Holos\runtime\python.exe -X utf8 tools\smoke_test.py <сборка>\Holos\app
# Проверяет: библиотеки грузятся из runtime; Qt стартует без экрана; GigaAM распознаёт образец модели.
import os, sys

app = os.path.abspath(sys.argv[1])
sys.path.insert(0, app)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy, soundfile, sherpa_onnx, vosk, onnxruntime, onnx_asr, srt, requests, qtawesome  # noqa: F401
from PySide6.QtWidgets import QApplication
qa = QApplication([])
print('библиотеки и Qt — ОК')

giga = os.path.join(app, 'models', 'sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16')
rec = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=os.path.join(giga, 'encoder.int8.onnx'), decoder=os.path.join(giga, 'decoder.onnx'),
    joiner=os.path.join(giga, 'joiner.onnx'), tokens=os.path.join(giga, 'tokens.txt'),
    num_threads=2, sample_rate=16000, model_type='nemo_transducer', decoding_method='greedy_search')
audio, sr = soundfile.read(os.path.join(giga, 'test_wavs', 'example.wav'), dtype='float32')
s = rec.create_stream()
s.accept_waveform(sr, audio)
rec.decode_stream(s)
text = s.result.text.strip()
print('GigaAM:', text)
if len(text) < 10:
    sys.exit('ПРОБА НЕ ПРОШЛА: GigaAM не распознал образец')
import onnxruntime as ort
print('onnxruntime:', ort.__version__)
print('ПРОБА ПРОШЛА')
