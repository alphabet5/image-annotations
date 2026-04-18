from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class MagnifierOverlay(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setWindowFlags(Qt.WindowType.SubWindow)
        self._source_image: QImage | None = None
        self._source_pixmap_key: int = -1  # pixmap cache key, for change detection
        self._zoom_rectf: QRectF | None = None
        self._size: int = 150
        self._zoom_factor: float = 4.0
        self._offset_x: int = 20
        self._offset_y: int = 20
        self._upscale: bool = True
        self.hide()

    def set_config(self, config: dict) -> None:
        mag = config.get("magnifier", {})
        self._size = mag.get("size", 150)
        self._zoom_factor = mag.get("zoom_factor", 4.0)
        self._offset_x = mag.get("offset_x", 20)
        self._offset_y = mag.get("offset_y", 20)
        self._upscale = mag.get("upscale", True)
        self.resize(self._size, self._size)

    def update_from_cursor(
        self,
        cursor_view_pos: QPointF,
        scene_pos: QPointF,
        pixmap_item,
        scale_info,
    ) -> None:
        if not pixmap_item:
            self.hide()
            return

        pm = pixmap_item.pixmap()
        if pm.cacheKey() != self._source_pixmap_key:
            self._source_image = pm.toImage()
            self._source_pixmap_key = pm.cacheKey()

        cx, cy = scene_pos.x(), scene_pos.y()
        region_half = (self._size / 2) / self._zoom_factor
        self._zoom_rectf = QRectF(
            cx - region_half,
            cy - region_half,
            max(1.0, region_half * 2),
            max(1.0, region_half * 2),
        )

        lens_x = int(cursor_view_pos.x()) + self._offset_x
        lens_y = int(cursor_view_pos.y()) + self._offset_y
        vp = self.parent()
        lens_x = min(lens_x, vp.width() - self._size)
        lens_y = min(lens_y, vp.height() - self._size)
        lens_x = max(0, lens_x)
        lens_y = max(0, lens_y)
        self.move(lens_x, lens_y)
        self.resize(self._size, self._size)
        self.show()
        self.update()

    def paintEvent(self, event):
        if not self._source_image or not self._zoom_rectf:
            return
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform, self._upscale
        )

        path = QPainterPath()
        path.addEllipse(0, 0, self._size, self._size)
        painter.setClipPath(path)

        # drawImage with QRectF source supports sub-pixel sampling — the source
        # region shifts continuously rather than snapping to whole pixels.
        painter.drawImage(
            QRectF(0, 0, self._size, self._size),
            self._source_image,
            self._zoom_rectf,
        )

        painter.setClipping(False)
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.drawEllipse(1, 1, self._size - 2, self._size - 2)

        center = self._size // 2
        painter.setPen(QPen(QColor("#00FF00"), 1))
        painter.drawLine(center - 10, center, center + 10, center)
        painter.drawLine(center, center - 10, center, center + 10)
        painter.end()
