"""Live-view widgets: LiveTile (frame display) and MonitoringButton (Start/Stop toggle)."""
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QImage, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import theme
from .theme import Color
from .widgets import Button, set_props


class LiveTile(QWidget):
    """Shows the latest QImage (aspect-preserved) or the themed placeholder, plus a caption chip."""

    def __init__(self, caption: str = "", min_height: int = 140):
        super().__init__()
        self._caption = caption
        self._message = ""
        self._image: QImage | None = None
        self.setMinimumHeight(min_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    @property
    def has_frame(self) -> bool:
        return self._image is not None

    def set_caption(self, text: str) -> None:
        if text != self._caption:
            self._caption = text
            self.update()

    def set_message(self, text: str) -> None:
        self._message = text
        self.update()

    def set_frame(self, image: QImage) -> None:
        self._image = image
        self.update()

    def clear_frame(self) -> None:
        if self._image is not None:
            self._image = None
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect())
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(r, 10, 10)
        p.setClipPath(clip)
        if self._image is None:
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, QColor(Color.VIDEO_TOP))
            g.setColorAt(1, QColor(Color.VIDEO_BOTTOM))
            p.fillRect(r, g)
        else:
            p.fillRect(r, QColor("#0c080b"))
            w, h = self._image.width(), self._image.height()
            if w and h:
                s = min(r.width() / w, r.height() / h)
                tw, th = w * s, h * s
                p.drawImage(QRectF(r.x() + (r.width() - tw) / 2, r.y() + (r.height() - th) / 2, tw, th),
                            self._image)
        p.restore()

        if self._message and self._image is None:
            p.setPen(QColor(Color.MUTED))
            p.setFont(self.font())
            p.drawText(r.adjusted(16, 16, -16, -16), Qt.AlignCenter | Qt.TextWordWrap, self._message)

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


class MonitoringButton(Button):
    """Start/Stop toggle bound to a LiveManager; stays in sync across every page that has one."""
    no_cameras = Signal()

    def __init__(self, manager):
        super().__init__("Start Monitoring")
        self._mgr = manager
        self.clicked.connect(self._on_click)
        manager.monitoring_changed.connect(self._sync)
        self._sync(manager.is_running)

    def _on_click(self) -> None:
        if self._mgr.is_running:
            self._mgr.stop()
        elif self._mgr.start() == 0:
            self.no_cameras.emit()

    def _sync(self, running: bool) -> None:
        self.setText("Stop Monitoring" if running else "Start Monitoring")
        set_props(self, variant="tonal" if running else "primary")
