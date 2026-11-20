import math
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QTextEdit, QApplication)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QColor, QPainter, QBrush, QTextCursor
import qtawesome as qta
from core.settings import AppSettings

class MiniVolumeIndicator(QWidget):
    """
    Компактный индикатор уровня голоса (3 динамические полосы).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 18)
        self.volume = 0.0
        self.tick = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_anim)
        self.timer.start(35)

    def set_volume(self, vol: float):
        self.volume = max(0.0, min(1.0, vol))

    def _update_anim(self):
        self.tick += 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        bar_w = 4
        spacing = 3
        
        bars = 3
        start_x = (w - (bars * bar_w + (bars - 1) * spacing)) / 2
        
        color = QColor("#ef4444") if self.volume > 0.04 else QColor("#6366f1")
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        
        for i in range(bars):
            phase = i * 1.5
            wave = 0.3 + 0.2 * math.sin(self.tick * 0.15 + phase)
            bar_height = max(3.0, (self.volume * 0.85 + wave) * h * 0.85)
            bar_height = min(float(h), bar_height)
            
            x = start_x + i * (bar_w + spacing)
            y = (h - bar_height) / 2
            painter.drawRoundedRect(x, y, bar_w, bar_height, 2, 2)

class FloatingOverlay(QWidget):
    """
    Плавающий информативный оверлей (HUD).
    Показывает ПОЛНЫЙ надиктованный текст в реальном времени поверх всех окон без перехвата фокуса.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Окно поверх всех, без рамки, тип Tool, НЕ перехватывает фокус ввода!
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool | 
            Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        self.setFixedSize(680, 130)
        self._drag_offset = None  # [v3] окно перетаскивается мышью (31.10.2026)
        self.setCursor(Qt.SizeAllCursor)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)
        
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Корневая карточка со скруглением и темной стеклянной заливкой
        self.card = QFrame()
        self.card.setObjectName("OverlayCard")
        self.card.setStyleSheet("""
            QFrame#OverlayCard {
                background-color: rgba(18, 18, 22, 0.96);
                border: 1px solid #ef4444;
                border-radius: 16px;
            }
        """)
        
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(16, 10, 16, 12)
        card_layout.setSpacing(6)
        
        # Верхняя информационная строка
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        
        self.icon_label = QLabel()
        self.icon_label.setPixmap(qta.icon("fa5s.microphone", color="#ef4444").pixmap(16, 16))
        top_bar.addWidget(self.icon_label)
        
        self.volume_bar = MiniVolumeIndicator()
        top_bar.addWidget(self.volume_bar)
        
        self.lbl_status = QLabel("Идёт запись речи...")
        self.lbl_status.setStyleSheet("color: #ef4444; font-size: 12px; font-weight: 600;")
        top_bar.addWidget(self.lbl_status)
        
        top_bar.addStretch(1)
        
        self.lbl_badge = QLabel("F8 — завершить и вставить")
        self.lbl_badge.setStyleSheet("""
            background-color: #27272a;
            color: #d4d4d8;
            font-size: 11px;
            font-weight: 600;
            border-radius: 4px;
            padding: 3px 8px;
        """)
        top_bar.addWidget(self.lbl_badge)
        
        card_layout.addLayout(top_bar)
        
        # Область для отображения ПОЛНОГО надиктованного текста
        self.txt_display = QTextEdit()
        self.txt_display.setReadOnly(True)
        self.txt_display.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.txt_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.txt_display.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                border: none;
                color: #ffffff;
                font-size: 14px;
                line-height: 22px;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-weight: 500;
                padding: 0px;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 4px;
            }
            QScrollBar::handle:vertical {
                background: #52525b;
                border-radius: 2px;
            }
        """)
        # [v3] Тянуть окно можно и за текст: поле прокручивается само
        self.txt_display.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.txt_display.setPlaceholderText("Говорите в микрофон, надиктованный текст будет появляться здесь полностью...")
        card_layout.addWidget(self.txt_display, 1)
        
        main_layout.addWidget(self.card)

    def show_listening(self, hotkey_name: str = "F8"):
        """
        Открывает оверлей для новой сессии диктовки.
        """
        self.hide_timer.stop()
        # [v3, 03.11.2026] «Ассистент» останавливается сам по паузе
        self.lbl_badge.setText(f"пауза {AppSettings.get('assistant/silence'):g} с — отправить" if hotkey_name == "Ассистент"
                               else f"{hotkey_name} — завершить и вставить")
        self.icon_label.setPixmap(qta.icon("fa5s.microphone", color="#ef4444").pixmap(16, 16))
        self.lbl_status.setText("Ассистент слушает..." if hotkey_name == "Ассистент" else "Идёт запись речи...")
        self.lbl_status.setStyleSheet("color: #ef4444; font-size: 12px; font-weight: 600;")
        
        self.txt_display.clear()
        
        self.card.setStyleSheet("""
            QFrame#OverlayCard {
                background-color: rgba(18, 18, 22, 0.96);
                border: 1px solid #ef4444;
                border-radius: 16px;
            }
        """)
        self._reposition_top_center()
        self.show()

    def update_text(self, full_text: str):
        """
        Отображает ПОЛНЫЙ накопленный текст с момента старта диктовки с автоскроллом вниз.
        """
        if not full_text:
            return
        self.txt_display.setPlainText(full_text)
        # Автоматический скролл в конец, чтобы новые слова всегда были перед глазами
        cursor = self.txt_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.txt_display.setTextCursor(cursor)

    def set_volume(self, volume: float):
        self.volume_bar.set_volume(volume)

    def show_success(self, message: str = "Вставлено в окно!"):
        """
        Показывает статус успешной вставки и скрывает оверлей через 1.5 секунды.
        """
        self.icon_label.setPixmap(qta.icon("fa5s.check", color="#10b981").pixmap(16, 16))
        self.lbl_status.setText(f"✅ {message}")
        self.lbl_status.setStyleSheet("color: #10b981; font-size: 12px; font-weight: 600;")
        self.card.setStyleSheet("""
            QFrame#OverlayCard {
                background-color: rgba(18, 18, 22, 0.96);
                border: 1px solid #10b981;
                border-radius: 16px;
            }
        """)
        self.hide_timer.start(1600)

    def show_command(self, text: str, target: str):
        """
        [v3, 03.11.2026] «Ассистент, …» одним духом: показать, что услышано и куда ушло.
        """
        self.hide_timer.stop()
        self.lbl_badge.setText(target)
        self.icon_label.setPixmap(qta.icon("fa5s.check", color="#10b981").pixmap(16, 16))
        self.lbl_status.setText("✅ Ассистент услышал")
        self.lbl_status.setStyleSheet("color: #10b981; font-size: 12px; font-weight: 600;")
        self.txt_display.setPlainText(text)
        self.card.setStyleSheet("""
            QFrame#OverlayCard {
                background-color: rgba(18, 18, 22, 0.96);
                border: 1px solid #10b981;
                border-radius: 16px;
            }
        """)
        self._reposition_top_center()
        self.show()
        self.hide_timer.start(2500)

    def show_error(self, message: str):
        self.icon_label.setPixmap(qta.icon("fa5s.exclamation-circle", color="#ef4444").pixmap(16, 16))
        self.lbl_status.setText("Ошибка")
        self.lbl_status.setStyleSheet("color: #ef4444; font-size: 12px; font-weight: 600;")
        self.txt_display.setPlainText(message)
        self._reposition_top_center()
        self.show()
        self.hide_timer.start(3500)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        if self._drag_offset is not None:
            self._drag_offset = None
            AppSettings.set("overlay/pos", f"{self.x()},{self.y()}")

    def _reposition_top_center(self):
        """
        Размещает оверлей там, куда его перетащили; иначе — по центру верхней части основного экрана.
        """
        saved = str(AppSettings.get("overlay/pos") or "")
        if "," in saved:
            x, y = (int(v) for v in saved.split(",", 1))
            # Монитор отключили — место за экраном: тогда по центру
            if QApplication.screenAt(QPoint(x + self.width() // 2, y + 20)):
                self.move(x, y)
                return
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.geometry()
            x = (screen_geo.width() - self.width()) // 2
            y = 35 # Отступ сверху
            self.move(x, y)
