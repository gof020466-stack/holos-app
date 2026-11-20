import random
import math
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QBrush, QPen
from PySide6.QtCore import Qt, QTimer

class VolumeVisualizer(QWidget):
    def __init__(self, parent=None, num_bars: int = 24):
        super().__init__(parent)
        self.num_bars = num_bars  # [v3.2, Д8] узкая строка у кнопки «Запись» — меньше полос
        # Высоты полос в диапазоне от 0.0 до 1.0
        self.bar_heights = [0.0] * self.num_bars
        self.target_heights = [0.0] * self.num_bars
        
        # Счётчик кадров для красивой idle-анимации ("дыхания")
        self.idle_tick = 0
        
        # Таймер для плавной анимации спада (decay)
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._animate)
        self.animation_timer.start(25)  # 40 FPS

        # Минимальная высота полосы (чтобы полосы были красивыми и заметными даже при тишине)
        self.min_height = 0.15
        
        # Сеттинги цветов
        self.accent_color_start = QColor("#6366f1")  # Indigo
        self.accent_color_end = QColor("#a855f7")    # Purple

    def set_volume(self, volume: float):
        """
        Устанавливает текущий уровень громкости и генерирует новые целевые высоты.
        """
        # Ограничиваем громкость
        volume = min(1.0, max(0.0, volume))
        
        # Задаем новые целевые значения для полос с небольшим случайным разбросом
        for i in range(self.num_bars):
            # В центре полосы выше, по краям ниже (эффект колокола)
            dist_from_center = abs(i - (self.num_bars / 2)) / (self.num_bars / 2)
            bell_factor = 1.0 - (dist_from_center * 0.7)
            
            # Рандомизация для "живости"
            random_factor = random.uniform(0.8, 1.2)
            
            if volume > 0.02:
                target = volume * bell_factor * random_factor
                self.target_heights[i] = min(1.0, max(self.min_height, target))
            else:
                # Если громкости нет, создаем красивую медленную синусоидальную волну ожидания
                # (эффект "дыхания" как в голосовых ассистентах Siri/Google)
                phase = (i / self.num_bars) * 2.0 * math.pi
                wave = 0.5 + 0.5 * math.sin(self.idle_tick * 0.05 + phase)
                # Колебания в пределах 15% - 25% от высоты
                self.target_heights[i] = self.min_height * (1.0 + 0.6 * wave)

    def _animate(self):
        """
        Плавно приближает текущие значения к целевым (спад и подъем).
        """
        self.idle_tick += 1
        for i in range(self.num_bars):
            curr = self.bar_heights[i]
            target = self.target_heights[i]
            
            if curr < target:
                # Быстрый подъем
                self.bar_heights[i] += (target - curr) * 0.4
            else:
                # Плавный спад (decay)
                self.bar_heights[i] += (target - curr) * 0.15
                
            # Ограничиваем
            self.bar_heights[i] = min(1.0, max(self.min_height, self.bar_heights[i]))
            
            # Постепенно опускаем целевые высоты, если нет нового входящего звука
            self.target_heights[i] = max(self.min_height, self.target_heights[i] * 0.85)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()

        # Размеры полос
        spacing = 4 if width >= 300 else 3
        total_spacings = spacing * (self.num_bars - 1)
        bar_width = max(2, int((width - total_spacings) / self.num_bars))
        
        # Центрируем отрисовку по горизонтали
        actual_draw_width = (bar_width * self.num_bars) + (spacing * (self.num_bars - 1))
        start_x = int((width - actual_draw_width) / 2)

        # Градиент для заливки полос
        gradient = QLinearGradient(0, height, 0, 0)
        gradient.setColorAt(0, self.accent_color_start)
        gradient.setColorAt(1, self.accent_color_end)
        brush = QBrush(gradient)
        painter.setBrush(brush)
        painter.setPen(Qt.NoPen)

        # Рисуем симметричные скругленные полосы относительно центральной оси Y
        center_y = height / 2

        for i in range(self.num_bars):
            x = start_x + i * (bar_width + spacing)
            
            # Высота полосы
            bar_h = self.bar_heights[i] * height
            bar_h = max(4, bar_h)  # Минимальная высота в пикселях

            # Отрисовка со скруглением
            rect_y = center_y - (bar_h / 2)
            painter.drawRoundedRect(x, rect_y, bar_width, bar_h, bar_width / 2, bar_width / 2)

        painter.end()
