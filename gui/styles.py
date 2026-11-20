# modern stylesheets for the Windows 11 Fluent dark and light looks

DARK_THEME_STYLES = """
/* Главное окно */
QMainWindow {
    background-color: #121214;
}

/* Шрифты по умолчанию */
QWidget {
    font-family: 'Segoe UI', 'Segoe UI Variable', 'Inter', sans-serif;
    font-size: 13px;
    color: #e2e2e5;
}

/* Боковая панель меню */
QFrame#Sidebar {
    background-color: #1a1a1e;
    border-right: 1px solid #2d2d34;
}

/* Кнопки меню */
QPushButton.MenuButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: #a0a0ab;
    text-align: left;
    padding: 10px 15px;
    font-size: 14px;
    font-weight: 500;
}

QPushButton.MenuButton:hover {
    background-color: #2a2a30;
    color: #ffffff;
}

QPushButton.MenuButton:checked {
    background-color: #312e81; /* Deep indigo */
    color: #ffffff;
    border-left: 3px solid #6366f1; /* Neon indigo border indicator */
}

/* Обычные кнопки */
QPushButton.PrimaryButton {
    background-color: #4f46e5;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton.PrimaryButton:hover {
    background-color: #4338ca;
}

QPushButton.PrimaryButton:pressed {
    background-color: #3730a3;
}

QPushButton.PrimaryButton:disabled {
    background-color: #27272a;
    color: #71717a;
}

QPushButton.SecondaryButton {
    background-color: #27272a;
    color: #e4e4e7;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton.SecondaryButton:hover {
    background-color: #3f3f46;
    color: #ffffff;
}

QPushButton.SecondaryButton:pressed {
    background-color: #52525b;
}

QPushButton.SecondaryButton:disabled {
    background-color: #18181b;
    border-color: #27272a;
    color: #52525b;
}

QPushButton.DangerButton {
    background-color: #b91c1c;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton.DangerButton:hover {
    background-color: #991b1b;
}

QPushButton.DangerButton:pressed {
    background-color: #7f1d1d;
}

/* Текстовые поля ввода и редакторы */
QTextEdit, QLineEdit, QComboBox {
    background-color: #1a1a1e;
    border: 1px solid #2d2d34;
    border-radius: 6px;
    padding: 8px;
    color: #e2e2e5;
    selection-background-color: #6366f1;
}

QTextEdit:focus, QLineEdit:focus, QComboBox:focus {
    border: 1px solid #6366f1;
}

QComboBox::drop-down {
    border: none;
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
}

QComboBox QAbstractItemView {
    background-color: #1a1a1e;
    border: 1px solid #2d2d34;
    selection-background-color: #312e81;
    selection-color: #ffffff;
    outline: none;
}

/* Карточки контейнеров */
QFrame.CardFrame {
    background-color: #1a1a1e;
    border: 1px solid #2d2d34;
    border-radius: 8px;
}

QFrame.SubCardFrame {
    background-color: #212126;
    border: 1px solid #2d2d34;
    border-radius: 6px;
}

/* Заголовки */
QLabel.TitleLabel {
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
}

QLabel.SubtitleLabel {
    font-size: 13px;
    color: #a0a0ab;
}

QLabel.HeaderLabel {
    font-size: 15px;
    font-weight: 600;
    color: #ffffff;
}

/* Прогресс-бар */
QProgressBar {
    background-color: #27272a;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: transparent;
    height: 8px;
}

QProgressBar::chunk {
    background-color: #6366f1;
    border-radius: 4px;
}

/* Скроллбары */
QScrollBar:vertical {
    border: none;
    background: #121214;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #2d2d34;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #3f3f46;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}

QScrollBar:horizontal {
    border: none;
    background: #121214;
    height: 8px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #2d2d34;
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #3f3f46;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
}

/* Сплиттер */
QSplitter::handle {
    background-color: #2d2d34;
}

/* Список истории */
QListWidget#HistoryListWidget {
    background-color: transparent;
    border: none;
}

QListWidget#HistoryListWidget::item {
    background-color: #212126;
    border: 1px solid #2d2d34;
    border-radius: 6px;
    margin-bottom: 6px;
    padding: 10px;
    color: #e2e2e5;
}

QListWidget#HistoryListWidget::item:hover {
    background-color: #2d2d34;
}

QListWidget#HistoryListWidget::item:selected {
    background-color: #312e81;
    border-color: #6366f1;
    color: #ffffff;
}

/* Дополнительные стили для элементов загрузки и микрофона */
QFrame#DropArea {
    border: 2px dashed #3f3f46;
    background-color: #1a1a1e;
    border-radius: 12px;
}
QFrame#DropArea:hover {
    border-color: #6366f1;
    background-color: #202027;
}
QFrame#DropArea[dragged="true"] {
    border-color: #6366f1;
    background-color: #242430;
}
QLabel#DropAreaText {
    color: #a0a0ab;
    font-size: 14px;
    font-weight: 500;
}
QLabel#DropAreaFormat {
    color: #71717a;
    font-size: 11px;
}
QLabel#FileMetaLabel {
    color: #a0a0ab;
    font-size: 12px;
}
QLabel#TimeProgressLabel {
    color: #a0a0ab;
}
QPushButton#RemoveFileButton {
    background-color: #27272a;
    border-radius: 18px;
    border: none;
}
QPushButton#RemoveFileButton:hover {
    background-color: #3f3f46;
}
QLabel#MicStatusLabel {
    color: #a0a0ab;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#RecordButton {
    font-size: 14px;
    padding: 12px 24px;
    background-color: #4f46e5;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    font-weight: 600;
}
QPushButton#RecordButton:hover {
    background-color: #4338ca;
}
QPushButton#RecordButton[recording="true"] {
    background-color: #dc2626;
}
QPushButton#RecordButton[recording="true"]:hover {
    background-color: #b91c1c;
}
QFrame#ActiveModelCard {
    background-color: #1e1e24;
    border: 1px solid #312e81;
    border-radius: 8px;
}
QLabel#ActiveModelNameLabel {
    color: #a0a0ab;
    font-size: 13px;
}
QLabel#ModelsProgressLabel {
    color: #a0a0ab;
}
QListWidget#ModelsListWidget {
    background-color: #1a1a1e;
    border: 1px solid #2d2d34;
    border-radius: 8px;
    padding: 5px;
}
QListWidget#ModelsListWidget::item {
    background-color: #212126;
    border: 1px solid #2d2d34;
    border-radius: 6px;
    margin: 4px;
    padding: 12px;
    color: #e2e2e5;
}
QListWidget#ModelsListWidget::item:hover {
    background-color: #2d2d34;
    border-color: #3f3f46;
}
QListWidget#ModelsListWidget::item:selected {
    background-color: #312e81;
    border-color: #6366f1;
    color: #ffffff;
}

/* Диалоговые окна и предупреждения */
QDialog, QMessageBox {
    background-color: #1a1a1e;
}
QDialog QLabel, QMessageBox QLabel {
    color: #e2e2e5;
}
"""

LIGHT_THEME_STYLES = """
/* Главное окно */
QMainWindow {
    background-color: #f3f3f7;
}

/* Шрифты по умолчанию */
QWidget {
    font-family: 'Segoe UI', 'Segoe UI Variable', 'Inter', sans-serif;
    font-size: 13px;
    color: #1c1c1e;
}

/* Боковая панель меню */
QFrame#Sidebar {
    background-color: #eaeaea;
    border-right: 1px solid #d2d2d7;
}

/* Кнопки меню */
QPushButton.MenuButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: #55555d;
    text-align: left;
    padding: 10px 15px;
    font-size: 14px;
    font-weight: 500;
}

QPushButton.MenuButton:hover {
    background-color: #dadada;
    color: #1c1c1e;
}

QPushButton.MenuButton:checked {
    background-color: #e0e0ff;
    color: #4f46e5;
    border-left: 3px solid #6366f1;
}

/* Обычные кнопки */
QPushButton.PrimaryButton {
    background-color: #4f46e5;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton.PrimaryButton:hover {
    background-color: #4338ca;
}

QPushButton.PrimaryButton:pressed {
    background-color: #3730a3;
}

QPushButton.PrimaryButton:disabled {
    background-color: #e5e5ea;
    color: #aeaea3;
}

QPushButton.SecondaryButton {
    background-color: #ffffff;
    color: #1c1c1e;
    border: 1px solid #d2d2d7;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton.SecondaryButton:hover {
    background-color: #f2f2f7;
    color: #000000;
}

QPushButton.SecondaryButton:pressed {
    background-color: #e5e5ea;
}

QPushButton.SecondaryButton:disabled {
    background-color: #fcfcfc;
    border-color: #e5e5ea;
    color: #c7c7cc;
}

QPushButton.DangerButton {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton.DangerButton:hover {
    background-color: #b91c1c;
}

QPushButton.DangerButton:pressed {
    background-color: #991b1b;
}

/* Текстовые поля ввода и редакторы */
QTextEdit, QLineEdit, QComboBox {
    background-color: #ffffff;
    border: 1px solid #d2d2d7;
    border-radius: 6px;
    padding: 8px;
    color: #1c1c1e;
    selection-background-color: #c7d2fe;
    selection-color: #4f46e5;
}

QTextEdit:focus, QLineEdit:focus, QComboBox:focus {
    border: 1px solid #6366f1;
}

QComboBox::drop-down {
    border: none;
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #d2d2d7;
    selection-background-color: #e0e0ff;
    selection-color: #4f46e5;
    outline: none;
}

/* Карточки контейнеров */
QFrame.CardFrame {
    background-color: #ffffff;
    border: 1px solid #d2d2d7;
    border-radius: 8px;
}

QFrame.SubCardFrame {
    background-color: #f5f5f7;
    border: 1px solid #e5e5ea;
    border-radius: 6px;
}

/* Заголовки */
QLabel.TitleLabel {
    font-size: 22px;
    font-weight: 700;
    color: #000000;
}

QLabel.SubtitleLabel {
    font-size: 13px;
    color: #68686e;
}

QLabel.HeaderLabel {
    font-size: 15px;
    font-weight: 600;
    color: #000000;
}

/* Прогресс-бар */
QProgressBar {
    background-color: #e5e5ea;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: transparent;
    height: 8px;
}

QProgressBar::chunk {
    background-color: #6366f1;
    border-radius: 4px;
}

/* Скроллбары */
QScrollBar:vertical {
    border: none;
    background: #f3f3f7;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #c7c7cc;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #aeaeae;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}

QScrollBar:horizontal {
    border: none;
    background: #f3f3f7;
    height: 8px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #c7c7cc;
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #aeaeae;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
}

/* Сплиттер */
QSplitter::handle {
    background-color: #d2d2d7;
}

/* Список истории */
QListWidget#HistoryListWidget {
    background-color: transparent;
    border: none;
}

QListWidget#HistoryListWidget::item {
    background-color: #ffffff;
    border: 1px solid #d2d2d7;
    border-radius: 6px;
    margin-bottom: 6px;
    padding: 10px;
    color: #1c1c1e;
}

QListWidget#HistoryListWidget::item:hover {
    background-color: #f2f2f7;
}

QListWidget#HistoryListWidget::item:selected {
    background-color: #e0e0ff;
    border-color: #6366f1;
    color: #4f46e5;
}

/* Дополнительные стили для элементов загрузки и микрофона */
QFrame#DropArea {
    border: 2px dashed #c7c7cc;
    background-color: #ffffff;
    border-radius: 12px;
}
QFrame#DropArea:hover {
    border-color: #6366f1;
    background-color: #f2f2f7;
}
QFrame#DropArea[dragged="true"] {
    border-color: #6366f1;
    background-color: #e0e0ff;
}
QLabel#DropAreaText {
    color: #55555d;
    font-size: 14px;
    font-weight: 500;
}
QLabel#DropAreaFormat {
    color: #8e8e93;
    font-size: 11px;
}
QLabel#FileMetaLabel {
    color: #55555d;
    font-size: 12px;
}
QLabel#TimeProgressLabel {
    color: #55555d;
}
QPushButton#RemoveFileButton {
    background-color: #e5e5ea;
    border-radius: 18px;
    border: none;
}
QPushButton#RemoveFileButton:hover {
    background-color: #d1d1d6;
}
QLabel#MicStatusLabel {
    color: #55555d;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#RecordButton {
    font-size: 14px;
    padding: 12px 24px;
    background-color: #4f46e5;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    font-weight: 600;
}
QPushButton#RecordButton:hover {
    background-color: #4338ca;
}
QPushButton#RecordButton[recording="true"] {
    background-color: #dc2626;
}
QPushButton#RecordButton[recording="true"]:hover {
    background-color: #b91c1c;
}
QFrame#ActiveModelCard {
    background-color: #e0e0ff;
    border: 1px solid #c7d2fe;
    border-radius: 8px;
}
QLabel#ActiveModelNameLabel {
    color: #55555d;
    font-size: 13px;
}
QLabel#ModelsProgressLabel {
    color: #55555d;
}
QListWidget#ModelsListWidget {
    background-color: #ffffff;
    border: 1px solid #d2d2d7;
    border-radius: 8px;
    padding: 5px;
}
QListWidget#ModelsListWidget::item {
    background-color: #f5f5f7;
    border: 1px solid #e5e5ea;
    border-radius: 6px;
    margin: 4px;
    padding: 12px;
    color: #1c1c1e;
}
QListWidget#ModelsListWidget::item:hover {
    background-color: #e5e5ea;
    border-color: #d2d2d7;
}
QListWidget#ModelsListWidget::item:selected {
    background-color: #e0e0ff;
    border-color: #6366f1;
    color: #4f46e5;
}

/* Диалоговые окна и предупреждения */
QDialog, QMessageBox {
    background-color: #f3f3f7;
}
QDialog QLabel, QMessageBox QLabel {
    color: #1c1c1e;
}
"""

# [v3.2, 18.11.2026] Новые элементы: кнопка записи в меню (Д1), источники (Ф1), настройки (Д5), «облако» (Ф2)
_EXTRA = """
QPushButton#SidebarRecord {
    background-color: #dc2626; color: #ffffff; border: none; border-radius: 8px;
    padding: 11px 14px; font-size: 14px; font-weight: 700; text-align: left;
}
QPushButton#SidebarRecord:hover { background-color: #b91c1c; }
QPushButton#SidebarRecord[recording="true"] { background-color: #7f1d1d; border: 2px solid #ef4444; }
QPushButton#SidebarFile {
    background-color: transparent; color: %(muted)s; border: 1px solid %(line)s; border-radius: 8px;
    padding: 9px 14px; font-size: 13px; font-weight: 600; text-align: left;
}
QPushButton#SidebarFile:hover { background-color: %(hover)s; color: %(text)s; }
QPushButton#SourceButton {
    background-color: %(card)s; color: %(muted)s; border: 1px solid %(line)s; border-radius: 16px;
    padding: 7px 14px; font-weight: 600;
}
QPushButton#SourceButton:hover { color: %(text)s; }
QPushButton#SourceButton:checked { background-color: #4f46e5; color: #ffffff; border-color: #4f46e5; }
QPushButton#CloudButton {
    background-color: transparent; color: #f59e0b; border: 1px solid #f59e0b; border-radius: 6px;
    padding: 8px 14px; font-weight: 600;
}
QPushButton#CloudButton:hover { background-color: rgba(245, 158, 11, 0.12); }
QPushButton#CloudButton:disabled { color: #71717a; border-color: #52525b; }
QFrame#SettingRow { background-color: %(card)s; border: 1px solid %(line)s; border-radius: 8px; }
QLabel#SettingTitle { font-size: 14px; font-weight: 600; color: %(text)s; background: transparent; border: none; }
QLabel#SettingDesc { font-size: 12px; color: %(muted)s; background: transparent; border: none; }
QLabel#SettingSection { font-size: 12px; font-weight: 700; color: #6366f1; padding-top: 10px; }
QToolButton#CollapsibleButton { border: none; background: transparent; color: %(text)s; font-weight: 600; font-size: 14px; }
QTabWidget#SettingsTabs::pane { border: none; }
QTabBar::tab {
    background: transparent; color: %(muted)s; padding: 8px 16px; border: none;
    border-bottom: 2px solid transparent; font-weight: 600;
}
QTabBar::tab:selected { color: %(text)s; border-bottom: 2px solid #6366f1; }
QTabBar::tab:hover { color: %(text)s; }
QWidget#SettingsPage { background: transparent; }
"""
DARK_THEME_STYLES += _EXTRA % {"text": "#e4e4e7", "muted": "#a0a0ab", "line": "#2d2d34", "card": "#1a1a1e",
                               "hover": "#2a2a30"}
LIGHT_THEME_STYLES += _EXTRA % {"text": "#1c1c1e", "muted": "#55555d", "line": "#d4d4d8", "card": "#ffffff",
                                "hover": "#ececf0"}
