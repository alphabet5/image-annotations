from pathlib import Path

from PIL import Image as PILImage, ImageEnhance
from PySide6.QtCore import Qt, QObject, QPointF, QRunnable, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import (
    QColor, QCursor, QImage, QPainter, QPen, QPixmap, QTransform,
)
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsPixmapItem

from ..models import make_annotation
from ..utils.coord_utils import ScaleInfo, scene_to_image

# RAW formats decoded via rawpy
_RAW_EXTENSIONS = {".rw2"}



def _load_pil_image(path: Path) -> PILImage.Image:
    """
    Decode any supported format into an RGB PIL Image.  Thread-safe.
    - RW2: decoded via rawpy with LINEAR demosaicing (~4× faster than AHD, adequate for annotation)
    - Everything else (HEIC via pillow-heif, TIFF, JPEG, PNG, …): PIL
    """
    if path.suffix.lower() in _RAW_EXTENSIONS:
        import rawpy  # lazy import — only paid when opening a RAW file
        with rawpy.imread(str(path)) as raw:
            rgb_array = raw.postprocess(
                use_camera_wb=True,
                output_bps=8,
                demosaic_algorithm=rawpy.DemosaicAlgorithm.LINEAR,
                no_auto_bright=True,
                median_filter_passes=0,
            )
        return PILImage.fromarray(rgb_array)

    with PILImage.open(path) as img:
        return img.convert("RGB")  # forces pixel data into memory before context exits


def _apply_adjustments_to_pil(pil_image: PILImage.Image, config: dict) -> PILImage.Image:
    """
    Apply exposure/brightness/gamma adjustments.  Returns a PIL Image.
    Thread-safe — does not create any Qt objects.
    """
    adj = config.get("image_adjustments", {})
    exposure   = float(adj.get("exposure",   1.0))
    brightness = float(adj.get("brightness", 1.0))
    gamma      = float(adj.get("gamma",      1.0))

    img = pil_image

    linear = exposure * brightness
    if abs(linear - 1.0) > 1e-4:
        img = ImageEnhance.Brightness(img).enhance(linear)

    if abs(gamma - 1.0) > 1e-4:
        inv_gamma = 1.0 / max(gamma, 0.01)
        lut = [min(255, max(0, round((i / 255.0) ** inv_gamma * 255.0)))
               for i in range(256)]
        img = img.point(lut * 3)  # 3 identical channel LUTs for RGB

    return img


def _pil_to_pixmap(pil_image: PILImage.Image) -> QPixmap:
    """
    Convert a PIL Image to QPixmap via QImage (no intermediate encode/decode).
    Must be called on the main thread.
    """
    w, h = pil_image.size
    raw = pil_image.tobytes("raw", "RGB")
    qimage = QImage(raw, w, h, w * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimage)


def _apply_adjustments(pil_image: PILImage.Image, config: dict) -> QPixmap:
    """Apply adjustments and return a ready-to-display QPixmap.  Main thread only."""
    return _pil_to_pixmap(_apply_adjustments_to_pil(pil_image, config))


# ---------------------------------------------------------------------------
# Background image loader
# ---------------------------------------------------------------------------

class _LoaderSignals(QObject):
    """Carries results from a background _ImageLoader back to the main thread."""
    # raw_bytes: raw RGB bytes (w*h*3), ready to wrap in QImage on main thread
    # width, height: image dimensions
    # pil_image: decoded PIL image (retained for re-adjustment without re-decode)
    # seq: load sequence number — stale loads are discarded
    finished = Signal(bytes, int, int, object, int)
    failed   = Signal(str, int)


class _ImageLoader(QRunnable):
    """
    Loads and adjusts an image entirely off the main thread.
    All PIL / rawpy work happens here; QPixmap creation stays in the main thread.
    """
    def __init__(self, path: Path, config: dict, seq: int, signals: _LoaderSignals):
        super().__init__()
        self.setAutoDelete(True)
        self._path    = path
        self._config  = config
        self._seq     = seq
        self._signals = signals

    def run(self) -> None:
        try:
            pil_img = _load_pil_image(self._path)
            adj_pil = _apply_adjustments_to_pil(pil_img, self._config)
            w, h = adj_pil.size
            raw_bytes = adj_pil.tobytes("raw", "RGB")
            self._signals.finished.emit(raw_bytes, w, h, pil_img, self._seq)
        except Exception as exc:
            self._signals.failed.emit(str(exc), self._seq)


# ---------------------------------------------------------------------------
# Canvas
# ---------------------------------------------------------------------------

class AnnotationCanvas(QGraphicsView):
    annotation_added  = Signal(dict)
    annotation_removed = Signal(str)
    zoom_changed      = Signal(float)
    cursor_moved      = Signal(float, float)
    image_loaded      = Signal(Path)   # fired after an async load completes
    load_failed       = Signal(str)    # fired when a load fails

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.BlankCursor)

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._pil_image:   PILImage.Image | None = None
        self._scale_info:  ScaleInfo = ScaleInfo()
        self._config:      dict = {}
        self._annotations: list[dict] = []
        self._crosshair_items:  list = []
        self._annotation_items: dict[str, list] = {}
        self._magnifier = None
        self._current_image_path: Path | None = None
        self._original_size: tuple[int, int] = (0, 0)

        # Async load tracking — incremented on every load_image call;
        # stale results (older seq) are silently discarded.
        self._load_seq:    int = 0
        self._pending_path: Path | None = None
        self._loader_signals = _LoaderSignals()
        self._loader_signals.finished.connect(self._on_image_loaded)
        self._loader_signals.failed.connect(self._on_image_load_failed)

        # Debounce timer: coalesces rapid slider changes into a single redraw
        self._adjust_timer = QTimer(self)
        self._adjust_timer.setSingleShot(True)
        self._adjust_timer.setInterval(80)
        self._adjust_timer.timeout.connect(self._reload_pixmap)

    def load_image(self, path: Path) -> None:
        """
        Begin loading an image asynchronously.  Returns immediately — the scene
        is updated later via _on_image_loaded once the background thread finishes.
        """
        self._load_seq += 1
        self._pending_path = path
        loader = _ImageLoader(path, dict(self._config), self._load_seq, self._loader_signals)
        QThreadPool.globalInstance().start(loader)

    @Slot(bytes, int, int, object, int)
    def _on_image_loaded(self, raw_bytes: bytes, width: int, height: int, pil_image: object, seq: int) -> None:
        """Main-thread slot called when the background loader finishes."""
        if seq != self._load_seq:
            return  # a newer load_image() call superseded this one

        path = self._pending_path
        if path is None:
            return

        self._pil_image = pil_image  # type: ignore[assignment]
        qimage = QImage(raw_bytes, width, height, width * 3, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage)

        if pixmap.isNull():
            self.load_failed.emit(f"Could not load image: {path}")
            return

        self._current_image_path = path
        self._original_size = (pixmap.width(), pixmap.height())

        self._scene.clear()
        self._annotation_items.clear()
        self._crosshair_items.clear()
        self._annotations.clear()

        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._pixmap_item.setPos(0, 0)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())

        self._scale_info = ScaleInfo(
            scale_factor=self.transform().m11(),
            original_width=pixmap.width(),
            original_height=pixmap.height(),
        )
        self._init_crosshair()
        self._rebuild_annotation_graphics()
        self._sync_cursor_overlays()

        self.image_loaded.emit(path)

    @Slot(str, int)
    def _on_image_load_failed(self, error: str, seq: int) -> None:
        if seq != self._load_seq:
            return
        self.load_failed.emit(error)

    def set_config(self, config: dict) -> None:
        old_adj = self._config.get("image_adjustments", {})
        self._config = config
        new_adj = config.get("image_adjustments", {})
        if new_adj != old_adj:
            self._adjust_timer.start()
        self._rebuild_annotation_graphics()
        if self._magnifier:
            self._magnifier.set_config(config)

    def set_annotations(self, annotations: list[dict]) -> None:
        self._annotations = annotations
        self._rebuild_annotation_graphics()

    def add_annotation(self, annotation: dict) -> None:
        self._annotations.append(annotation)
        self._draw_annotation(annotation)

    def remove_annotation(self, annotation_id: str) -> None:
        for item in self._annotation_items.pop(annotation_id, []):
            self._scene.removeItem(item)
        self._annotations = [a for a in self._annotations if a["id"] != annotation_id]

    def zoom_to(self, factor: float) -> None:
        self.setTransform(QTransform.fromScale(factor, factor))
        self._scale_info = ScaleInfo(
            scale_factor=factor,
            original_width=self._original_size[0],
            original_height=self._original_size[1],
        )

    def current_zoom(self) -> float:
        return self.transform().m11()

    # ------------------------------------------------------------------
    # Qt events
    # ------------------------------------------------------------------

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.15 if delta > 0 else 1 / 1.15
            self.scale(factor, factor)
            self._scale_info = ScaleInfo(
                scale_factor=self.transform().m11(),
                original_width=self._original_size[0],
                original_height=self._original_size[1],
            )
            self.zoom_changed.emit(self.transform().m11())
        else:
            super().wheelEvent(event)
        # Always consume — prevent propagation to the config panel's QScrollArea
        event.accept()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        scene_pos = self.mapToScene(event.position().toPoint())
        self._update_crosshair(scene_pos)
        if self._original_size[0] > 0:
            self.cursor_moved.emit(scene_pos.x(), scene_pos.y())
        if self._config.get("magnifier", {}).get("enabled") and self._magnifier:
            self._magnifier.update_from_cursor(
                cursor_view_pos=event.position(),
                scene_pos=scene_pos,
                pixmap_item=self._pixmap_item,
                scale_info=self._scale_info,
            )

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if not self._pixmap_item:
            return
        scene_pos = self.mapToScene(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton:
            self._handle_left_click(scene_pos)
        elif event.button() == Qt.MouseButton.RightButton:
            self._handle_right_click(scene_pos)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        for item in self._crosshair_items:
            item.setVisible(False)
        if self._magnifier:
            self._magnifier.hide()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reload_pixmap(self) -> None:
        """Re-apply current adjustments and update the scene. Runs on the main thread."""
        if self._current_image_path is None or self._pixmap_item is None:
            return

        if self._pil_image is None:
            self._pil_image = _load_pil_image(self._current_image_path)
        pixmap = _apply_adjustments(self._pil_image, self._config)

        if pixmap.isNull():
            return

        self._pixmap_item.setPixmap(pixmap)
        self._original_size = (pixmap.width(), pixmap.height())
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self._scale_info = ScaleInfo(
            scale_factor=self.transform().m11(),
            original_width=pixmap.width(),
            original_height=pixmap.height(),
        )

    def _sync_cursor_overlays(self) -> None:
        """
        If the mouse is already inside the viewport when an image finishes loading,
        update crosshair and magnifier immediately without waiting for a mouse move.
        """
        viewport = self.viewport()
        local = viewport.mapFromGlobal(QCursor.pos())
        if not viewport.rect().contains(local):
            return
        scene_pos = self.mapToScene(local)
        self._update_crosshair(scene_pos)
        if self._config.get("magnifier", {}).get("enabled") and self._magnifier:
            self._magnifier.update_from_cursor(
                cursor_view_pos=QPointF(local),
                scene_pos=scene_pos,
                pixmap_item=self._pixmap_item,
                scale_info=self._scale_info,
            )

    def _init_crosshair(self):
        pen = QPen(QColor("#00FF00"), 1, Qt.PenStyle.DashLine)
        sr = self._scene.sceneRect()
        h = self._scene.addLine(sr.left(), 0, sr.right(), 0, pen)
        v = self._scene.addLine(0, sr.top(), 0, sr.bottom(), pen)
        h.setZValue(10)
        v.setZValue(10)
        self._crosshair_items = [h, v]

    def _update_crosshair(self, scene_pos: QPointF):
        if not self._crosshair_items:
            return
        h, v = self._crosshair_items
        sr = self._scene.sceneRect()
        h.setLine(sr.left(), scene_pos.y(), sr.right(), scene_pos.y())
        v.setLine(scene_pos.x(), sr.top(), scene_pos.x(), sr.bottom())
        h.setVisible(True)
        v.setVisible(True)

    def _handle_left_click(self, scene_pos: QPointF):
        img_x, img_y = scene_to_image(scene_pos.x(), scene_pos.y(), self._scale_info)
        try:
            image_file = str(
                self._current_image_path.relative_to(
                    Path(self._config.get("images_dir", "."))
                )
            )
        except (ValueError, AttributeError):
            image_file = str(self._current_image_path)

        active_name = self._config.get("active_annotation_name", "Point")
        styles = self._config.get("annotation_styles", {})
        style = styles.get(active_name, {})
        color = style.get("color", "#FF0000")

        ann = make_annotation(
            image_file=image_file,
            annotation_name=active_name,
            location_x=img_x,
            location_y=img_y,
            image_width=self._original_size[0],
            image_height=self._original_size[1],
            annotation_color=color,
        )
        self.add_annotation(ann)
        self.annotation_added.emit(ann)

    def _handle_right_click(self, scene_pos: QPointF):
        active_name = self._config.get("active_annotation_name", "Point")
        styles = self._config.get("annotation_styles", {})
        style = styles.get(active_name, {})
        marker_size = style.get("size", 12)
        tolerance = max(10.0, marker_size / 2.0)

        best_id = None
        best_dist = float("inf")
        for ann in self._annotations:
            dist = (
                (ann["location_x"] - scene_pos.x()) ** 2
                + (ann["location_y"] - scene_pos.y()) ** 2
            ) ** 0.5
            if dist < tolerance and dist < best_dist:
                best_dist = dist
                best_id = ann["id"]
        if best_id:
            self.remove_annotation(best_id)
            self.annotation_removed.emit(best_id)

    def _rebuild_annotation_graphics(self):
        for items in self._annotation_items.values():
            for item in items:
                self._scene.removeItem(item)
        self._annotation_items.clear()
        for ann in self._annotations:
            self._draw_annotation(ann)

    def _draw_annotation(self, ann: dict):
        styles = self._config.get("annotation_styles", {})
        name = ann["annotation_name"]
        style = styles.get(name, {})

        color = style.get("color") or ann.get("annotation_color", "#FF0000")
        shape = style.get("shape", "X")
        size = style.get("size", 12)
        thickness = style.get("thickness", 2)

        items = _draw_marker_on_scene(
            self._scene,
            ann["location_x"], ann["location_y"],
            shape=shape, color=color, size=size, thickness=thickness,
        )
        if self._config.get("show_labels"):
            txt = self._scene.addText(ann["annotation_name"])
            txt.setPos(ann["location_x"] + 4, ann["location_y"] + 4)
            txt.setDefaultTextColor(QColor(color))
            txt.setZValue(11)
            items.append(txt)
        if self._config.get("show_coordinates"):
            coord_str = f"({ann['location_x']:.1f}, {ann['location_y']:.1f})"
            coord_txt = self._scene.addText(coord_str)
            y_offset = 4 + (14 if self._config.get("show_labels") else 0)
            coord_txt.setPos(ann["location_x"] + 4, ann["location_y"] + y_offset)
            coord_txt.setDefaultTextColor(QColor("#FFFF00"))
            coord_txt.setZValue(11)
            items.append(coord_txt)
        self._annotation_items[ann["id"]] = items


def _draw_marker_on_scene(
    scene,
    cx: float,
    cy: float,
    shape: str,
    color: str,
    size: int,
    thickness: int,
) -> list:
    pen = QPen(QColor(color), thickness)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    half = size / 2.0
    items = []

    if shape == "X":
        l1 = scene.addLine(cx - half, cy - half, cx + half, cy + half, pen)
        l2 = scene.addLine(cx + half, cy - half, cx - half, cy + half, pen)
        l1.setZValue(11)
        l2.setZValue(11)
        items = [l1, l2]

    elif shape == "+":
        l1 = scene.addLine(cx - half, cy, cx + half, cy, pen)
        l2 = scene.addLine(cx, cy - half, cx, cy + half, pen)
        l1.setZValue(11)
        l2.setZValue(11)
        items = [l1, l2]

    elif shape == "O":
        ellipse = scene.addEllipse(cx - half, cy - half, half * 2, half * 2, pen)
        ellipse.setZValue(11)
        items = [ellipse]

    return items
