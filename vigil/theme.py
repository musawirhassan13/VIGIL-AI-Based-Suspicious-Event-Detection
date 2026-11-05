"""VIGIL theme: palette, typography and the global stylesheet.

Drop .ttf/.otf files into assets/fonts/ (e.g. Bricolage Grotesque, IBM Plex Sans,
JetBrains Mono) and they are loaded automatically; otherwise system fallbacks are used.
"""
from pathlib import Path
from string import Template

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication


class Color:
    BG = "#1a1118"
    SIDEBAR = "#130c11"
    SURFACE = "#251b22"
    BORDER = "#3a2c37"
    INPUT = "#1a1118"
    INPUT_BORDER = "#4b3b47"
    TEXT = "#f2e7e2"
    MUTED = "#a99ba4"
    GOLD = "#e8b08a"
    PURPLE = "#7b48c2"
    PURPLE_HOVER = "#8c5ad3"
    TONAL = "#3a2849"
    TONAL_HOVER = "#4a3459"
    NAV_ACTIVE = "#3b2a45"
    ALERT = "#f58b78"      # alert bounding boxes
    NORMAL = "#c49cf0"     # normal bounding boxes
    VIDEO_TOP = "#2f2438"
    VIDEO_BOTTOM = "#14100f"
    CHIP = "#100b0e"


# kind -> (background, foreground)
BADGES = {
    "red": ("#5c2a2a", "#f2a396"),
    "purple": ("#3a2a4a", "#d6b8f6"),
    "green": ("#2b3b2b", "#a9d9a0"),
}

HEADING_FONTS = ["Bricolage Grotesque", "Space Grotesk", "Segoe UI Variable Display",
                 "Segoe UI", "Helvetica Neue", "Arial"]
BODY_FONTS = ["IBM Plex Sans", "Segoe UI", "Helvetica Neue", "Arial"]
MONO_FONTS = ["JetBrains Mono", "IBM Plex Mono", "Consolas", "Menlo", "Courier New"]


def _css(fams):
    return ", ".join(f'"{f}"' for f in fams)


def load_fonts() -> None:
    d = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    if d.is_dir():
        for f in [*d.glob("*.ttf"), *d.glob("*.otf")]:
            QFontDatabase.addApplicationFont(str(f))


def mono_font(px: int = 12, bold: bool = False) -> QFont:
    f = QFont()
    f.setFamilies(MONO_FONTS)
    f.setPixelSize(px)
    f.setBold(bold)
    return f


_QSS = """
* { font-family: $BODY; font-size: 13px; color: $TEXT; }
QLabel { background: transparent; }
#Root { background: $BG; }

/* ---------- Sidebar ---------- */
#Sidebar { background: $SIDEBAR; border-right: 1px solid $BORDER; }
QLabel[role="logo"] { color: $GOLD; font-family: $HEAD; font-size: 24px; font-weight: 700; }
QPushButton#NavItem { text-align: left; padding: 11px 14px; border: none; border-radius: 8px;
    background: transparent; color: $MUTED; font-size: 14px; }
QPushButton#NavItem:hover { background: rgba(255,255,255,0.04); color: $TEXT; }
QPushButton#NavItem:checked { background: $NAV_ACTIVE; color: $TEXT; }
QLabel[role="sidefoot"] { color: $MUTED; font-size: 12px; }

/* ---------- Typography roles ---------- */
QLabel[role="pagetitle"] { font-family: $HEAD; font-size: 28px; font-weight: 700; }
QLabel[role="pagesub"] { color: $MUTED; font-size: 13px; }
QLabel[role="cardtitle"] { font-family: $HEAD; font-size: 16px; font-weight: 700; }
QLabel[role="statlabel"] { color: $MUTED; font-size: 13px; }
QLabel[role="statvalue"] { color: $GOLD; font-family: $HEAD; font-size: 32px; font-weight: 700; }
QLabel[role="rowtitle"] { font-size: 14px; font-weight: 700; }
QLabel[role="muted"] { color: $MUTED; font-size: 13px; }
QLabel[role="note"] { color: $MUTED; font-size: 13px; }
QLabel[role="fieldlabel"] { color: $MUTED; font-size: 13px; }
QLabel[role="th"] { color: $MUTED; font-size: 13px; font-weight: 700; }
QLabel[role="cell"] { font-size: 14px; }
QLabel[role="cellmuted"] { color: $MUTED; font-size: 14px; }
QLabel[role="mono"] { font-family: $MONO; font-size: 13px; }
QLabel[role="monomuted"] { font-family: $MONO; font-size: 13px; color: $MUTED; }

/* ---------- Badges ---------- */
QLabel[role="badge"] { border: 1px solid transparent; border-radius: 11px; padding: 3px 10px; font-size: 12px; }
$BADGES

/* ---------- Surfaces ---------- */
QFrame#Card { background: $SURFACE; border: 1px solid $BORDER; border-radius: 14px; }
QFrame#ListRow { background: transparent; border: none; border-bottom: 1px solid $BORDER; }
QFrame#ListRow[last="true"] { border-bottom: none; }
QFrame#TableHeader { background: transparent; border: none; border-bottom: 1px solid $BORDER; }
QFrame#TableRow { background: transparent; border: none; border-bottom: 1px solid $BORDER; }
QFrame#TableRow:hover { background: rgba(255,255,255,0.03); }
QFrame#TableRow[selected="true"] { background: rgba(123,72,194,0.14); }

/* ---------- Buttons ---------- */
QPushButton[variant="primary"], QPushButton[variant="tonal"] {
    border: none; border-radius: 8px; padding: 11px 18px; font-size: 14px; font-weight: 700; }
QPushButton[variant="primary"] { background: $PURPLE; color: #ffffff; }
QPushButton[variant="primary"]:hover { background: $PURPLE_HOVER; }
QPushButton[variant="primary"]:pressed { background: #6a3bb0; }
QPushButton[variant="tonal"] { background: $TONAL; color: $TEXT; }
QPushButton[variant="tonal"]:hover { background: $TONAL_HOVER; }
QPushButton[variant="tonal"]:pressed { background: #332241; }
QPushButton[size="sm"] { padding: 9px 16px; }

/* ---------- Inputs ---------- */
QLineEdit, QComboBox, QSpinBox { background: $INPUT; border: 1px solid $INPUT_BORDER; border-radius: 8px;
    padding: 10px 12px; font-family: $MONO; font-size: 14px; selection-background-color: $PURPLE; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid $PURPLE; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView { background: $SURFACE; border: 1px solid $BORDER;
    selection-background-color: $NAV_ACTIVE; outline: none; }
QCheckBox { spacing: 10px; background: transparent; font-size: 14px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px;
    border: 1px solid $INPUT_BORDER; background: $INPUT; }
QCheckBox::indicator:checked { background: $PURPLE; border-color: $PURPLE; }
QSlider::groove:horizontal { height: 6px; border-radius: 3px; background: $INPUT; }
QSlider::sub-page:horizontal { background: $PURPLE; border-radius: 3px; }
QSlider::handle:horizontal { background: $GOLD; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }
QToolTip { background: $SURFACE; color: $TEXT; border: 1px solid $BORDER; padding: 4px 8px; }
"""


def build_qss() -> str:
    mapping = {k: v for k, v in vars(Color).items() if k.isupper()}
    mapping.update(HEAD=_css(HEADING_FONTS), BODY=_css(BODY_FONTS), MONO=_css(MONO_FONTS))
    mapping["BADGES"] = "\n".join(
        f'QLabel[role="badge"][kind="{k}"] {{ background: {bg}; color: {fg}; border-color: {bg}; }}'
        for k, (bg, fg) in BADGES.items())
    return Template(_QSS).safe_substitute(mapping)


def apply(app: QApplication) -> None:
    load_fonts()
    font = QFont()
    font.setFamilies(BODY_FONTS)
    font.setPixelSize(13)
    app.setFont(font)
    pal = app.palette()
    pal.setColor(QPalette.Window, QColor(Color.BG))
    pal.setColor(QPalette.WindowText, QColor(Color.TEXT))
    pal.setColor(QPalette.Base, QColor(Color.INPUT))
    pal.setColor(QPalette.Text, QColor(Color.TEXT))
    app.setPalette(pal)
    app.setStyleSheet(build_qss())
