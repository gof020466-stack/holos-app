"""
[v3.2, 18.11.2026] Общие элементы настроек (Д5, образец — Meetily):
строка «заголовок + пояснение + переключатель справа» и сворачиваемый блок «Как пользоваться».
"""
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QWidget, QToolButton
from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QPainter, QColor


class ToggleSwitch(QCheckBox):
    """Переключатель вместо флажка. Это тот же QCheckBox: isChecked, toggled, setChecked — как раньше."""

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(QSize(44, 24))

    def sizeHint(self):
        return QSize(44, 24)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        track = QColor("#4f46e5" if on else "#52525b")
        if not self.isEnabled():
            track.setAlpha(110)
        r = QRectF(0, 0, self.width(), self.height())
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.width() - d - 3 if on else 3
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, 3, d, d))
        p.end()


class SettingRow(QFrame):
    """Заголовок, одна строка пояснения, справа — переключатель или другой элемент."""

    def __init__(self, title: str, description: str, control: QWidget, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(16)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("SettingTitle")
        self.lbl_title.setWordWrap(True)
        texts.addWidget(self.lbl_title)
        if description:
            self.lbl_desc = QLabel(description)
            self.lbl_desc.setObjectName("SettingDesc")
            self.lbl_desc.setWordWrap(True)
            texts.addWidget(self.lbl_desc)
        lay.addLayout(texts, 1)
        lay.addWidget(control, 0, Qt.AlignVCenter)
        self.control = control


def section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("SettingSection")
    return lbl


class Collapsible(QWidget):
    """Кнопка-заголовок и содержимое под ней; по умолчанию свёрнуто."""

    def __init__(self, title: str, content: QWidget, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.button = QToolButton()
        self.button.setText(title)
        self.button.setObjectName("CollapsibleButton")
        self.button.setCheckable(True)
        self.button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.button.setArrowType(Qt.RightArrow)
        self.button.toggled.connect(self._toggle)
        self.content = content
        content.setVisible(False)
        lay.addWidget(self.button)
        lay.addWidget(content)

    def _toggle(self, opened: bool):
        self.button.setArrowType(Qt.DownArrow if opened else Qt.RightArrow)
        self.content.setVisible(opened)
