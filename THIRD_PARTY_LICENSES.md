# Third-party licenses / Лицензии сторонних компонентов

«Голос» (Holos) is MIT-licensed (see `LICENSE`). It uses the models and libraries below. Each keeps its own license; the authors are credited here and on the program's "About" page.

«Голос» распространяется по MIT (`LICENSE`). Модели и библиотеки ниже — под своими лицензиями; авторы указаны здесь и на странице «О программе».

## Speech models / Модели

Models are not stored in this repository. The full installer ships them unchanged (converted to ONNX by the projects named below).

| Model | Author | License | Source |
|---|---|---|---|
| GigaAM v3 (RNNT, punctuation) | GigaChat Team (Sber) | MIT | https://github.com/salute-developers/GigaAM — ONNX by k2-fsa/sherpa-onnx |
| Parakeet Ultra | Moondream, based on NVIDIA Parakeet TDT 0.6B v3 | CC BY 4.0 | https://huggingface.co/moondream/parakeet-ultra — ONNX: https://huggingface.co/mrfakename/parakeet-ultra-ONNX |
| Parakeet TDT 0.6B v3 (base of Parakeet Ultra) | NVIDIA | CC BY 4.0 | https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3 |
| vosk-model-ru-0.54, vosk-model-small-streaming-ru-0.54 | Alpha Cephei | Apache 2.0 | https://alphacephei.com/vosk/models |
| vosk-model-small-ru-0.22 | Alpha Cephei | Apache 2.0 | https://alphacephei.com/vosk/models |
| pyannote segmentation 3.0 | CNRS (pyannote) | MIT | https://huggingface.co/pyannote/segmentation-3.0 — ONNX by k2-fsa/sherpa-onnx |
| ERes2Net base (speech_eres2net_base_sv_zh-cn_3dspeaker_16k) | Alibaba DAMO Academy (3D-Speaker) | Apache 2.0 | https://modelscope.cn/models/iic/speech_eres2net_base_sv_zh-cn_3dspeaker_16k |

CC BY 4.0: https://creativecommons.org/licenses/by/4.0/ — no changes were made to the model weights.

## Libraries / Библиотеки

| Library | License |
|---|---|
| PySide6, Shiboken6 (Qt for Python) | LGPL-3.0 — https://www.qt.io/licensing |
| sherpa-onnx (k2-fsa) | Apache 2.0 |
| onnx-asr (istupakov) | MIT |
| ONNX Runtime (Microsoft) | MIT |
| vosk (Alpha Cephei) | Apache 2.0 |
| requests | Apache 2.0 |
| PyAudioWPatch | Apache 2.0 |
| sounddevice | MIT |
| QtAwesome (icons: Font Awesome Free — icons CC BY 4.0, fonts SIL OFL 1.1) | MIT |
| srt | MIT |
| keyboard | MIT |
| soundfile | BSD 3-Clause |
| NumPy | BSD 3-Clause |

## Programs / Программы

| Program | License | Note |
|---|---|---|
| FFmpeg 9.0 (`bin\ffmpeg.exe` in the installer, LGPL build by FFmpeg-Builds) | LGPL-3.0 | Separate program, called as a process, not linked; license text — `bin\LICENSE-ffmpeg.txt`. Source: https://ffmpeg.org, build scripts: https://github.com/BtbN/FFmpeg-Builds |

| Microsoft Visual C++ runtime (`runtime\msvcp140*.dll`) | Microsoft Visual C++ Redistributable license | Redistributable files, unchanged; needed by ONNX Runtime on Windows without Visual C++ installed |

Apache 2.0: https://www.apache.org/licenses/LICENSE-2.0 · MIT: https://opensource.org/license/mit · LGPL-3.0: https://www.gnu.org/licenses/lgpl-3.0.html