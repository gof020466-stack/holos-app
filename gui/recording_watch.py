"""
[v3, 11.11.2026] Признак «идёт запись» и предупреждение «звук есть, текста нет».

Повод: 11.11.2026 20 минут диктовки шли через «продолжить запись»,
а по виду окна нельзя было понять, идёт ли распознавание.
Строка: ● 03:12 ▮▮▮▯▯▯  или  ⚠ … — подключается к любому MicTranscriptionWorker.
"""
import time
from PySide6.QtCore import QObject, QTimer, Signal

from core.voice_commands import beep

NO_AUDIO_S = 3        # нет ни одного блока звука — поток микрофона встал
SILENCE_S = 10        # блоки идут, но тишина — микрофон выключен или отключён
NO_TEXT_S = 15        # звук есть, текста нет — распознавание не идёт
LOUD_LEVEL = 0.2      # уровень «есть голос» (шкала MicTranscriptionWorker 0…1)
QUIET_LEVEL = 0.05    # ниже — тишина
BARS = 6


class RecordingWatch(QObject):
    """Раз в секунду отдаёт строку состояния записи и флаг «предупреждение»."""
    status_changed = Signal(str, bool)   # (текст строки, это предупреждение)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._warned = False

    def attach(self, worker):
        now = time.monotonic()
        self._start = self._last_block = self._last_sound = self._last_text = now
        self._loud_since_text = 0.0
        self._peak = 0.0
        self._warned = False
        self._paused_at = None      # [v3, 12.11.2026] время начала паузы
        self._paused_total = 0.0    # сумма пауз — в часы записи не входит
        worker.volume_changed.connect(self._on_volume)
        worker.partial_result.connect(self._on_text)
        worker.final_chunk.connect(self._on_text)
        self._timer.start()
        self._tick()

    def detach(self):
        self._timer.stop()

    def set_paused(self, paused: bool):
        """[v3, 12.11.2026] На паузе — «⏸ Пауза», без предупреждений о тишине."""
        now = time.monotonic()
        if paused and self._paused_at is None:
            self._paused_at = now
        elif not paused and self._paused_at is not None:
            self._paused_total += now - self._paused_at
            self._paused_at = None
            self._last_block = self._last_sound = self._last_text = now
            self._loud_since_text = 0.0
            self._warned = False
        self._tick()

    def _on_volume(self, v: float):
        now = time.monotonic()
        self._last_block = now
        self._peak = max(self._peak, v)
        if v > QUIET_LEVEL:
            self._last_sound = now
        if v > LOUD_LEVEL:
            self._loud_since_text += 0.05   # блок звука — 50 мс

    def _on_text(self, text: str):
        if text.strip():
            self._last_text = time.monotonic()
            self._loud_since_text = 0.0
            self._warned = False

    def _tick(self):
        now = time.monotonic()
        paused_now = (now - self._paused_at) if self._paused_at is not None else 0.0
        secs = int(now - self._start - self._paused_total - paused_now)
        clock = f"{secs // 60:02d}:{secs % 60:02d}"
        if self._paused_at is not None:
            p = int(paused_now)
            self.status_changed.emit(f"⏸ Пауза {p // 60:02d}:{p % 60:02d}  ·  записано {clock}  ·  "
                                     f"«продолжить запись» — дальше", False)
            return
        level = round(min(1.0, self._peak) * BARS)
        bars = "▮" * level + "▯" * (BARS - level)
        self._peak = 0.0
        warning = None
        if now - self._last_block > NO_AUDIO_S:
            warning = "микрофон не даёт звук — проверьте подключение"
        elif now - self._last_sound > SILENCE_S:
            warning = f"тишина {int(now - self._last_sound)} с — микрофон выключен?"
        elif now - self._last_text > NO_TEXT_S and self._loud_since_text >= 3:
            warning = f"звук есть, текста нет {int(now - self._last_text)} с — распознавание не идёт"
        if warning:
            if not self._warned:
                self._warned = True
                beep(True)
                beep(True)
            self.status_changed.emit(f"⚠ {clock}  {bars}  {warning}", True)
        else:
            self.status_changed.emit(f"● Запись {clock}  {bars}", False)
