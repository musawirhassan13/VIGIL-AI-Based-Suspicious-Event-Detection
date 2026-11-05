"""Reusable VIGIL UI components."""
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from . import theme
from .theme import Color


def set_props(w: QWidget, **props) -> None:
    """Set dynamic properties and re-evaluate the stylesheet."""
    for k, v in props.items():
        w.setProperty(k, v)
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def label(text: str = "", role: str | None = None, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if role:
        lbl.setProperty("role", role)
    lbl.setWordWrap(wrap)
    return lbl


def labeled(text: str, widget: QWidget) -> QWidget:
    """Field label stacked above an input widget."""
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    lay.addWidget(label(text, "fieldlabel"))
    lay.addWidget(widget)
    return box


class Button(QPushButton):
    def __init__(self, text: str, variant: str = "primary", size: str = "md"):
        super().__init__(text)
        self.setProperty("variant", variant)   # primary | tonal
        self.setProperty("size", size)          # md | sm
        self.setCursor(Qt.PointingHandCursor)


class Badge(QLabel):
    def __init__(self, text: str, kind: str = "purple"):
        super().__init__(text)
        self.setProperty("role", "badge")
        self.setProperty("kind", kind)          # red | purple | green
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def set_kind(self, kind: str, text: str | None = None) -> None:
        if text is not None:
            self.setText(text)
        set_props(self, kind=kind)


class Card(QFrame):
    def __init__(self, title: str | None = None, margins=(20, 18, 20, 18), spacing: int = 12):
        super().__init__()
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(*margins)
        self.body.setSpacing(spacing)
        if title:
            self.body.addWidget(label(title, "cardtitle"))


class StatCard(Card):
    def __init__(self, text: str, value: str):
        super().__init__(margins=(18, 16, 18, 16), spacing=2)
        self.body.addWidget(label(text, "statlabel"))
        self.body.addWidget(label(value, "statvalue"))


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 8)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label(title, "pagetitle"))
        self.subtitle = label(subtitle, "pagesub")
        col.addWidget(self.subtitle)
        self._lay.addLayout(col, 1)

    def add_action(self, widget: QWidget) -> None:
        self._lay.addWidget(widget, 0, Qt.AlignTop)


class Page(QWidget):
    """Base page: padded vertical layout with a PageHeader on top."""

    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(32, 32, 32, 28)
        self.root.setSpacing(16)
        self.header = PageHeader(title, subtitle)
        self.root.addWidget(self.header)


class ListRow(QFrame):
    """Two-line row (title + subtitle) with an optional widget on the right."""

    def __init__(self, title: str, subtitle: str, right: QWidget | None = None,
                 mono_sub: bool = False, last: bool = False):
        super().__init__()
        self.setObjectName("ListRow")
        self.setProperty("last", last)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 12)
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(label(title, "rowtitle"))
        col.addWidget(label(subtitle, "monomuted" if mono_sub else "muted"))
        lay.addLayout(col, 1)
        if right is not None:
            lay.addWidget(right, 0, Qt.AlignVCenter)


class _Row(QFrame):
    clicked = Signal()

    def mousePressEvent(self, e):
        self.clicked.emit()
        super().mousePressEvent(e)


class Table(QWidget):
    """Lightweight table. columns = [(header, stretch, label_role)]; cells are str or QWidget."""
    row_clicked = Signal(int)

    def __init__(self, columns):
        super().__init__()
        self._cols = columns
        self._rows: list[_Row] = []
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)
        head = QFrame()
        head.setObjectName("TableHeader")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(4, 10, 4, 10)
        for text, stretch, _ in columns:
            lbl = label(text, "th")
            lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            hl.addWidget(lbl, stretch)
        self._lay.addWidget(head)
        self._lay.addStretch(1)

    def add_row(self, cells) -> None:
        idx = len(self._rows)
        row = _Row()
        row.setObjectName("TableRow")
        row.setProperty("selected", False)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(4, 12, 4, 12)
        for (_, stretch, role), cell in zip(self._cols, cells):
            if isinstance(cell, str):
                w = label(cell, role)
            else:
                w = QWidget()
                c = QHBoxLayout(w)
                c.setContentsMargins(0, 0, 0, 0)
                c.addWidget(cell)
                c.addStretch(1)
            w.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            rl.addWidget(w, stretch)
        row.clicked.connect(lambda i=idx: self.row_clicked.emit(i))
        self._rows.append(row)
        self._lay.insertWidget(self._lay.count() - 1, row)

    def select(self, index: int) -> None:
        for i, r in enumerate(self._rows):
            set_props(r, selected=(i == index))


class VideoView(QWidget):
    """Painted placeholder for a video frame: gradient, fake detection boxes, caption chip."""

    def __init__(self, caption: str = "", boxes=(), min_height: int = 140):
        super().__init__()
        self._caption = caption
        self._boxes = list(boxes)
        self.setMinimumHeight(min_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_caption(self, text: str) -> None:
        self._caption = text
        self.update()

    def set_boxes(self, boxes) -> None:
        self._boxes = list(boxes)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor(Color.VIDEO_TOP))
        g.setColorAt(1, QColor(Color.VIDEO_BOTTOM))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(r, 10, 10)
        p.setBrush(Qt.NoBrush)
        for x, y, w, h, kind in self._boxes:
            p.setPen(QPen(QColor(Color.ALERT if kind == "alert" else Color.NORMAL), 2))
            p.drawRoundedRect(QRectF(r.x() + x * r.width(), r.y() + y * r.height(),
                                     w * r.width(), h * r.height()), 2, 2)
        if self._caption:
            font = theme.mono_font(12)
            p.setFont(font)
            tw = QFontMetrics(font).horizontalAdvance(self._caption)
            chip = QRectF(r.left() + 9, r.bottom() - 33, tw + 20, 24)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(Color.CHIP))
            p.drawRoundedRect(chip, 4, 4)
            p.setPen(QColor(Color.TEXT))
            p.drawText(chip, Qt.AlignCenter, self._caption)


class TimelineBar(QWidget):
    """Analysis progress bar with event markers."""

    def __init__(self, progress: float = 0.0, markers=()):
        super().__init__()
        self._progress = progress
        self._markers = list(markers)
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1d1419"))
        p.drawRoundedRect(r, 8, 8)
        p.setBrush(QColor(Color.NAV_ACTIVE))
        p.drawRoundedRect(QRectF(r.x(), r.y(), r.width() * self._progress, r.height()), 8, 8)
        p.setBrush(QColor(Color.ALERT))
        for m in self._markers:
            p.drawRoundedRect(QRectF(r.x() + r.width() * m - 1.5, r.center().y() - 13, 3, 26), 1.5, 1.5)
