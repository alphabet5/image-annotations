# Image Annotation Desktop Application — Implementation Plan

## Project Overview

`image-annotate` is a Python desktop application for point-based image annotation. It provides a PySide6 GUI for interactively placing markers on images, stores annotations in a TSV file, and supports a CLI for batch rendering annotated images.

---

## Project Structure

```
image-annotations/
├── pyproject.toml
├── README.md
├── plan.md
├── src/
│   └── image_annotate/
│       ├── __init__.py
│       ├── __main__.py              # python -m image_annotate entry
│       ├── cli.py                   # click CLI definition
│       ├── models.py                # TypedDicts + MarkerShape enum (no class instances)
│       ├── tsv_io.py                # TSV read/write — all data as plain dicts
│       ├── renderer.py              # Pillow annotation renderer (headless)
│       ├── app.py                   # QApplication bootstrap, wires CLI -> GUI
│       ├── gui/
│       │   ├── __init__.py
│       │   ├── main_window.py       # QMainWindow, layout manager, undo stack
│       │   ├── image_canvas.py      # AnnotationCanvas(QGraphicsView) — core widget
│       │   ├── magnifier.py         # MagnifierOverlay — floating child QWidget
│       │   ├── config_panel.py      # ConfigPanel(QWidget) — right-side panel
│       │   ├── file_tree.py         # FileTreeWidget wrapping QFileSystemModel
│       │   ├── annotation_list.py   # AnnotationNameList(QListWidget) editable
│       │   └── dialogs.py           # About, error dialogs
│       └── utils/
│           ├── __init__.py
│           └── coord_utils.py       # Scale/mapping math utilities
```

---

## Architecture Overview

The application follows a **Model-View-Mediator** pattern:

```
CLI (click)
    |
    v
config dict (plain dict) <-----> TSV I/O (tsv_io.py)
    |
    v
MainWindow (main_window.py)  — holds undo stack
    |
    +-- AnnotationCanvas (image_canvas.py)   <-- QGraphicsView
    |       |-- QGraphicsScene
    |       |-- QGraphicsPixmapItem          (base image, at native resolution)
    |       |-- AnnotationItems              (per-annotation QGraphicsItems)
    |       |-- CrosshairOverlay             (live cursor lines)
    |       +-- MagnifierOverlay             (floating child QWidget)
    |
    +-- ConfigPanel (config_panel.py)        <-- QWidget in QSplitter
            |-- FileTreeWidget
            |-- MarkerOptionsGroup
            |-- MagnifierOptionsGroup
            |-- OutputPathGroup
            |-- AnnotationNameList
            |-- NotesField
            +-- ToggleOptions
```

**Signal flow:**
- `ConfigPanel` emits `config_changed(dict)` whenever any setting changes.
- `MainWindow` receives it and pushes the updated config into `AnnotationCanvas`.
- `AnnotationCanvas` emits `annotation_added(dict)` on left-click.
- `MainWindow` appends to undo stack, appends to TSV file.
- `AnnotationCanvas` emits `annotation_removed(str)` (annotation id) on right-click over a marker.
- `MainWindow` records removal in undo stack, rewrites TSV.
- Ctrl+Z in `MainWindow` pops the undo stack and reverses the last operation.
- `FileTreeWidget` emits `image_selected(Path)`; `MainWindow` loads the image and filters annotations.

---

## Data Models (`models.py`)

All data is represented as plain `dict` at runtime. `TypedDict` definitions are used for type annotations only — they are **never called as constructors**. Use plain dict literals everywhere.

```python
from typing import TypedDict
from enum import Enum


class MarkerShape(str, Enum):
    CROSS_X    = "X"   # diagonal cross
    CROSS_PLUS = "+"   # axis-aligned cross
    CIRCLE     = "O"   # circle


# ---- TypedDicts (type hints only — always construct as plain dict literals) ----

class MarkerConfig(TypedDict):
    shape: str          # MarkerShape value: "X", "+", or "O"
    color: str          # CSS hex color e.g. "#FF0000"
    size: int           # arm-length / radius in image pixels
    thickness: int      # line width in image pixels


class MagnifierConfig(TypedDict):
    enabled: bool
    size: int           # lens diameter in screen pixels
    zoom_factor: float  # image pixels shown per screen pixel inside lens
    offset_x: int       # pixels from cursor to lens top-left corner
    offset_y: int
    upscale: bool       # smooth bilinear upscaling in lens for sub-pixel accuracy


class Annotation(TypedDict):
    id: str             # uuid4 string
    image_file: str     # path as stored in TSV (relative when possible)
    annotation_name: str
    annotation_icon: str        # MarkerShape value snapshotted at creation time
    location_x: float           # ORIGINAL image coordinate (sub-pixel precision)
    location_y: float           # ORIGINAL image coordinate (sub-pixel precision)
    image_width: int            # total source image width in pixels
    image_height: int           # total source image height in pixels
    notes: str                  # session-only, not persisted in TSV


class AppConfig(TypedDict):
    images_dir: str             # str path (Path objects not JSON-serializable)
    annotations_file: str
    marker: MarkerConfig
    magnifier: MagnifierConfig
    show_labels: bool
    show_coordinates: bool
    active_annotation_name: str
    notes: str


# ---- Default factory functions (return plain dict literals) ----

def default_marker_config() -> dict:
    return {
        "shape": "X",
        "color": "#FF0000",
        "size": 12,
        "thickness": 2,
    }


def default_magnifier_config() -> dict:
    return {
        "enabled": True,
        "size": 150,
        "zoom_factor": 4.0,
        "offset_x": 20,
        "offset_y": 20,
        "upscale": True,
    }


def default_app_config(images_dir: str = ".", annotations_file: str = "annotations.tsv") -> dict:
    return {
        "images_dir": images_dir,
        "annotations_file": annotations_file,
        "marker": default_marker_config(),
        "magnifier": default_magnifier_config(),
        "show_labels": True,
        "show_coordinates": False,
        "active_annotation_name": "Point",
        "notes": "",
    }


def make_annotation(
    image_file: str,
    annotation_name: str,
    annotation_icon: str,
    location_x: float,
    location_y: float,
    image_width: int,
    image_height: int,
) -> dict:
    import uuid
    return {
        "id": str(uuid.uuid4()),
        "image_file": image_file,
        "annotation_name": annotation_name,
        "annotation_icon": annotation_icon,
        "location_x": location_x,
        "location_y": location_y,
        "image_width": image_width,
        "image_height": image_height,
        "notes": "",
    }
```

**Key design decisions:**
- `location_x/y` are `float` to support sub-pixel precision. When stored in TSV, written with enough decimal places to preserve accuracy (e.g. `f"{v:.4f}"`).
- `annotation_icon` is a snapshot of the marker shape at annotation time, so re-rendering is deterministic even if the default shape changes later.
- `notes` is intentionally excluded from TSV — it is session-only and keeps the format spec clean.
- All config and annotation data flows through the app as plain `dict` objects. `TypedDict` definitions exist only for IDE type checking.

---

## TSV I/O (`tsv_io.py`)

### TSV Column Order

```
image-file  annotation-name  annotation-icon  locationX(px)  locationY(px)  imageX(total width px)  imageY(total height px)
```

```python
import csv
from pathlib import Path
from typing import List

TSV_FIELDNAMES = [
    "image-file",
    "annotation-name",
    "annotation-icon",
    "locationX(px)",
    "locationY(px)",
    "imageX(total width px)",
    "imageY(total height px)",
]


def load_annotations(tsv_path: Path) -> list[dict]:
    """
    Returns a list of plain dicts matching the TSV columns.
    Returns empty list if file does not exist.
    Silently skips malformed rows.
    """
    rows: list[dict] = []
    if not tsv_path.exists():
        return rows
    with tsv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            try:
                rows.append({
                    "image_file": row["image-file"],
                    "annotation_name": row["annotation-name"],
                    "annotation_icon": row["annotation-icon"],
                    "location_x": float(row["locationX(px)"]),
                    "location_y": float(row["locationY(px)"]),
                    "image_width": int(row["imageX(total width px)"]),
                    "image_height": int(row["imageY(total height px)"]),
                    "id": row.get("id", ""),   # may not exist in older files
                    "notes": "",
                })
            except (KeyError, ValueError):
                continue  # skip corrupt rows
    return rows


def append_annotation(annotation: dict, tsv_path: Path) -> None:
    """
    Append a single annotation row to the TSV. Creates the file with header if needed.
    This is the fast path for the common case — no full rewrite required.
    """
    needs_header = not tsv_path.exists() or tsv_path.stat().st_size == 0
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    with tsv_path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=TSV_FIELDNAMES, delimiter="\t")
        if needs_header:
            writer.writeheader()
        writer.writerow(_annotation_to_row(annotation))


def save_annotations(annotations: list[dict], tsv_path: Path) -> None:
    """
    Full rewrite of the TSV. Used after undo/delete operations.
    Atomically writes via a temp file rename.
    """
    tmp_path = tsv_path.with_suffix(".tsv.tmp")
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    with tmp_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=TSV_FIELDNAMES, delimiter="\t")
        writer.writeheader()
        for ann in annotations:
            writer.writerow(_annotation_to_row(ann))
    tmp_path.replace(tsv_path)  # atomic rename on POSIX; best-effort on Windows


def _annotation_to_row(ann: dict) -> dict:
    return {
        "image-file": ann["image_file"],
        "annotation-name": ann["annotation_name"],
        "annotation-icon": ann["annotation_icon"],
        "locationX(px)": f"{ann['location_x']:.4f}",
        "locationY(px)": f"{ann['location_y']:.4f}",
        "imageX(total width px)": ann["image_width"],
        "imageY(total height px)": ann["image_height"],
    }
```

**Saving strategy:**
- **Adding** an annotation: `append_annotation()` — single-row append, no lock, no full rewrite.
- **Removing / undoing** an annotation: `save_annotations()` — atomic full rewrite via temp-file rename.
- This gives near-zero overhead on the common path (add) while being correct for mutations.

**Undo stack** (managed in `MainWindow`):

```python
# Each entry is one of:
#   ("add", annotation_dict)    — to undo: remove that annotation
#   ("remove", annotation_dict) — to undo: re-add that annotation
_undo_stack: list[tuple[str, dict]] = []

def _on_annotation_added(self, ann: dict):
    self._annotations.append(ann)
    self._undo_stack.append(("add", ann))
    append_annotation(ann, Path(self._config["annotations_file"]))

def _on_annotation_removed(self, ann_id: str):
    ann = next((a for a in self._annotations if a["id"] == ann_id), None)
    if ann:
        self._annotations = [a for a in self._annotations if a["id"] != ann_id]
        self._undo_stack.append(("remove", ann))
        save_annotations(self._annotations, Path(self._config["annotations_file"]))

def undo(self):
    if not self._undo_stack:
        return
    op, ann = self._undo_stack.pop()
    if op == "add":
        # Reverse an add: remove it
        self._annotations = [a for a in self._annotations if a["id"] != ann["id"]]
        self._canvas.remove_annotation(ann["id"])
        save_annotations(self._annotations, Path(self._config["annotations_file"]))
    elif op == "remove":
        # Reverse a remove: re-add it
        self._annotations.append(ann)
        self._canvas.add_annotation(ann)
        append_annotation(ann, Path(self._config["annotations_file"]))
```

Ctrl+Z is wired via `QShortcut(QKeySequence.Undo, self)` → `self.undo`.

**Edge cases handled:**
- Missing TSV at startup is not an error (first run).
- Corrupt rows are skipped rather than aborting the entire load.
- Atomic full-rewrite via rename prevents a half-written TSV on crash.
- `location_x/y` are stored as floats (`:.4f`) to preserve sub-pixel precision.

---

## Coordinate Mapping (`utils/coord_utils.py`)

With 1:1 zoom by default and `QGraphicsView` handling all transforms, scene coordinates directly equal original image pixel coordinates. `mapToScene()` handles the view→scene transform, giving us image coords for free.

`ScaleInfo` is still used by the magnifier to know the current zoom level, and by marker hit-testing.

```python
from dataclasses import dataclass


@dataclass
class ScaleInfo:
    """
    Describes the current zoom state of the canvas.

    scale_factor: current view zoom (1.0 = 100%, 2.0 = 200%, etc.)
      Obtained from view.transform().m11() after any zoom change.
    original_width/height: dimensions of the loaded image in pixels.
    """
    scale_factor: float = 1.0
    original_width: int = 0
    original_height: int = 0


def image_to_scene(img_x: float, img_y: float) -> tuple[float, float]:
    """
    Scene coordinates ARE image coordinates (pixmap placed at scene origin, no pixmap scaling).
    This is a no-op pass-through, here for documentation clarity.
    """
    return img_x, img_y


def scene_to_image(scene_x: float, scene_y: float, scale: ScaleInfo) -> tuple[float, float]:
    """
    Clamp scene coordinates to valid image bounds, returning float image coords.
    Since scene = image, this just clamps.
    """
    x = max(0.0, min(scene_x, float(scale.original_width - 1)))
    y = max(0.0, min(scene_y, float(scale.original_height - 1)))
    return x, y
```

**Image display approach (1:1 zoom by default):**

The `QGraphicsPixmapItem` is always placed at the scene origin at native resolution (no `fitInView`, no `setScale`). The `QGraphicsView` transform starts as identity (1:1). Zoom is achieved by calling `view.scale(factor, factor)`, which changes the view transform but not the scene. `mapToScene()` always gives image coordinates.

Scrollbars are set to `Qt.ScrollBarAsNeeded` — they appear when the image is larger than the viewport and disappear otherwise. No manual scroll bar management is needed.

---

## Image Canvas (`gui/image_canvas.py`)

```python
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QPen, QColor, QPixmap, QPainter, QTransform, QKeySequence
from PySide6.QtWidgets import QShortcut
from pathlib import Path
from ..models import MarkerShape, make_annotation
from ..utils.coord_utils import ScaleInfo, scene_to_image


class AnnotationCanvas(QGraphicsView):
    annotation_added   = Signal(dict)
    annotation_removed = Signal(str)    # emits annotation["id"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # Render quality — antialiasing for smooth markers and sub-pixel rendering
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setRenderHint(QPainter.TextAntialiasing, True)

        # 1:1 zoom by default; scrollbars appear only when image exceeds viewport
        self.setTransform(QTransform())
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.setMouseTracking(True)
        self.setCursor(Qt.BlankCursor)   # crosshair replaces OS cursor

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._scale_info: ScaleInfo = ScaleInfo()
        self._config: dict = {}
        self._annotations: list[dict] = []
        self._crosshair_items = []
        self._annotation_items: dict[str, list] = {}
        self._magnifier = None
        self._current_image_path: Path | None = None
        self._original_size: tuple[int, int] = (0, 0)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def load_image(self, path: Path) -> None:
        self._current_image_path = path
        pixmap = QPixmap(str(path))
        self._original_size = (pixmap.width(), pixmap.height())
        self._scale_info = ScaleInfo(
            scale_factor=self.transform().m11(),
            original_width=pixmap.width(),
            original_height=pixmap.height(),
        )

        self._scene.clear()
        self._annotation_items.clear()
        self._crosshair_items.clear()

        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._pixmap_item.setPos(0, 0)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())

        # Reset to 1:1 zoom on new image load
        self.setTransform(QTransform())
        self._init_crosshair()
        self._rebuild_annotation_graphics()

    def set_config(self, config: dict) -> None:
        self._config = config
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
        """Set absolute zoom factor (1.0 = 100%)."""
        self.setTransform(QTransform.fromScale(factor, factor))
        self._scale_info = ScaleInfo(
            scale_factor=factor,
            original_width=self._original_size[0],
            original_height=self._original_size[1],
        )

    # ------------------------------------------------------------------ #
    # Event Handling
    # ------------------------------------------------------------------ #

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            # Ctrl+scroll = zoom in/out
            delta = event.angleDelta().y()
            factor = 1.15 if delta > 0 else 1 / 1.15
            self.scale(factor, factor)
            self._scale_info = ScaleInfo(
                scale_factor=self.transform().m11(),
                original_width=self._original_size[0],
                original_height=self._original_size[1],
            )
            event.accept()
        else:
            # Normal scroll = pan (default QGraphicsView behavior)
            super().wheelEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        scene_pos = self.mapToScene(event.position().toPoint())
        self._update_crosshair(scene_pos)
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
        if event.button() == Qt.LeftButton:
            self._handle_left_click(scene_pos)
        elif event.button() == Qt.RightButton:
            self._handle_right_click(scene_pos)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        for item in self._crosshair_items:
            item.setVisible(False)
        if self._magnifier:
            self._magnifier.hide()

    # ------------------------------------------------------------------ #
    # Internal Helpers
    # ------------------------------------------------------------------ #

    def _init_crosshair(self):
        pen = QPen(QColor("#00FF00"), 1, Qt.DashLine)
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
            from pathlib import Path as _Path
            image_file = str(self._current_image_path.relative_to(
                _Path(self._config.get("images_dir", "."))
            ))
        except (ValueError, AttributeError):
            image_file = str(self._current_image_path)

        ann = make_annotation(
            image_file=image_file,
            annotation_name=self._config.get("active_annotation_name", "Point"),
            annotation_icon=self._config.get("marker", {}).get("shape", "X"),
            location_x=img_x,
            location_y=img_y,
            image_width=self._original_size[0],
            image_height=self._original_size[1],
        )
        self.add_annotation(ann)
        self.annotation_added.emit(ann)

    def _handle_right_click(self, scene_pos: QPointF):
        """Remove annotation nearest to right-click if within tolerance."""
        HIT_TOLERANCE = max(10, self._config.get("marker", {}).get("size", 12) / 2)
        best_id = None
        best_dist = float("inf")
        for ann in self._annotations:
            # Scene coords = image coords, so compare directly
            dist = ((ann["location_x"] - scene_pos.x()) ** 2
                    + (ann["location_y"] - scene_pos.y()) ** 2) ** 0.5
            if dist < HIT_TOLERANCE and dist < best_dist:
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
        marker_cfg = self._config.get("marker", {})
        items = _draw_marker_on_scene(
            self._scene,
            ann["location_x"], ann["location_y"],
            shape=ann["annotation_icon"],
            color=marker_cfg.get("color", "#FF0000"),
            size=marker_cfg.get("size", 12),
            thickness=marker_cfg.get("thickness", 2),
        )
        if self._config.get("show_labels"):
            txt = self._scene.addText(ann["annotation_name"])
            txt.setPos(ann["location_x"] + 4, ann["location_y"] + 4)
            txt.setDefaultTextColor(QColor(marker_cfg.get("color", "#FF0000")))
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


def _draw_marker_on_scene(scene, cx: float, cy: float,
                          shape: str, color: str, size: int, thickness: int) -> list:
    """
    Draw a marker at scene/image coordinates (cx, cy).
    Uses QPainter antialiasing (set on the QGraphicsView) for smooth sub-pixel rendering.
    'size' is the arm-length / radius in image pixels (scene pixels at 1:1 zoom).
    """
    pen = QPen(QColor(color), thickness)
    pen.setCapStyle(Qt.RoundCap)       # smooth line endpoints
    pen.setJoinStyle(Qt.RoundJoin)
    half = size / 2.0
    items = []

    if shape in ("X", MarkerShape.CROSS_X.value):
        l1 = scene.addLine(cx - half, cy - half, cx + half, cy + half, pen)
        l2 = scene.addLine(cx + half, cy - half, cx - half, cy + half, pen)
        l1.setZValue(11); l2.setZValue(11)
        items = [l1, l2]

    elif shape in ("+", MarkerShape.CROSS_PLUS.value):
        l1 = scene.addLine(cx - half, cy, cx + half, cy, pen)
        l2 = scene.addLine(cx, cy - half, cx, cy + half, pen)
        l1.setZValue(11); l2.setZValue(11)
        items = [l1, l2]

    elif shape in ("O", MarkerShape.CIRCLE.value):
        ellipse = scene.addEllipse(cx - half, cy - half, half * 2, half * 2, pen)
        ellipse.setZValue(11)
        items = [ellipse]

    return items
```

**Critical design notes:**
- **1:1 zoom by default**: The pixmap is placed at scene origin at native resolution. `setTransform(QTransform())` at load time resets any prior zoom.
- **Scene = image coordinates**: Since the pixmap item is never scaled, `mapToScene(viewport_point)` directly gives original image pixel coordinates. No separate coordinate transform function is needed for click handling.
- **Antialiasing**: `QPainter.Antialiasing` + `RoundCap` + `RoundJoin` on line items ensures markers render smoothly even at sub-pixel positions and fractional zoom levels.
- **Zoom**: Ctrl+scroll wheel. The view transform scales; scene coordinates (= image coordinates) are unchanged. `mapToScene()` always returns correct image coords.
- **Scroll/pan**: Native `QGraphicsView` behavior handles mouse scroll and two-finger trackpad swipe. `ScrollBarAsNeeded` shows/hides scroll bars automatically.
- Z-value layering: image=0, crosshair=10, markers+labels=11.
- `setCursor(Qt.BlankCursor)` hides the OS cursor so the crosshair visually replaces it.

---

## Magnifier Overlay (`gui/magnifier.py`)

A **child `QWidget` with no window frame** that floats inside the canvas viewport.

```python
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath


class MagnifierOverlay(QWidget):
    """
    Circular floating lens drawn as a child of the AnnotationCanvas viewport.
    Displays a zoomed region of the original QPixmap centered on the cursor.

    upscale=True:  SmoothPixmapTransform (bilinear interpolation) — helps place
                   points between pixels for sub-pixel accuracy.
    upscale=False: NearestNeighbor — sharp pixel grid, useful to see exact pixel
                   boundaries.
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # pass clicks through
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setWindowFlags(Qt.SubWindow)
        self._source_pixmap = None
        self._zoom_rect: QRect | None = None
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
        scene_pos: QPointF,        # scene coords = image coords
        pixmap_item,
        scale_info,
    ) -> None:
        if not pixmap_item:
            self.hide()
            return

        self._source_pixmap = pixmap_item.pixmap()

        # Region in original image pixels to show inside the lens.
        # scene_pos IS the image coordinate — no transform needed.
        cx, cy = scene_pos.x(), scene_pos.y()
        region_half = (self._size / 2) / self._zoom_factor
        self._zoom_rect = QRect(
            int(cx - region_half), int(cy - region_half),
            int(region_half * 2), int(region_half * 2),
        )

        # Position lens offset from cursor, clamped inside viewport
        lens_x = int(cursor_view_pos.x()) + self._offset_x
        lens_y = int(cursor_view_pos.y()) + self._offset_y
        vp = self.parent()
        lens_x = min(lens_x, vp.width() - self._size)
        lens_y = min(lens_y, vp.height() - self._size)
        self.move(lens_x, lens_y)
        self.resize(self._size, self._size)
        self.show()
        self.update()

    def paintEvent(self, event):
        if not self._source_pixmap or not self._zoom_rect:
            return
        painter = QPainter(self)

        # Upscale mode: smooth bilinear for sub-pixel accuracy;
        # Non-upscale: nearest-neighbor to show exact pixel grid.
        if self._upscale:
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        else:
            painter.setRenderHint(QPainter.SmoothPixmapTransform, False)

        # Clip rendering to circle
        path = QPainterPath()
        path.addEllipse(0, 0, self._size, self._size)
        painter.setClipPath(path)

        # Draw zoomed region scaled to fill the lens circle
        painter.drawPixmap(
            QRect(0, 0, self._size, self._size),
            self._source_pixmap,
            self._zoom_rect,
        )

        # Border ring
        painter.setClipping(False)
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.drawEllipse(1, 1, self._size - 2, self._size - 2)

        # Crosshair at lens center
        center = self._size // 2
        painter.setPen(QPen(QColor("#00FF00"), 1))
        painter.drawLine(center - 10, center, center + 10, center)
        painter.drawLine(center, center - 10, center, center + 10)
        painter.end()
```

**Design notes:**
- `WA_TransparentForMouseEvents` ensures clicks pass through to the canvas.
- It is a child of the **viewport widget** (not `QGraphicsView` itself), so `move()` coordinates are in viewport pixels — matching `event.position()` in `mouseMoveEvent`.
- `scene_pos` IS the image coordinate (since scene = image), so no `display_to_image` transform is needed.
- **Upscale toggle**: `SmoothPixmapTransform=True` uses bilinear interpolation when displaying the zoomed region, which produces smooth gradients between image pixels. This allows the user to judge where "between pixels" the actual point of interest lies, enabling sub-pixel accuracy. `SmoothPixmapTransform=False` shows the exact pixel grid, useful when you want to snap to exact pixel positions.

---

## Configuration Panel (`gui/config_panel.py`)

Lives in a `QSplitter` alongside the canvas. All changes emit `config_changed(dict)`.

### Widget Mapping

| Setting                      | Qt Widget                                                 |
|------------------------------|-----------------------------------------------------------|
| Marker shape                 | `QButtonGroup` with three `QRadioButton` ("X", "+", "O") |
| Marker color                 | `QPushButton` → opens `QColorDialog`; shows color swatch  |
| Marker size                  | `QSpinBox` (range 4–200, default 12) — image pixels       |
| Marker thickness             | `QSpinBox` (range 1–20, default 2)                        |
| Magnifier enable             | `QCheckBox`                                               |
| Magnifier size               | `QSlider` (horizontal, 50–400) + value `QLabel`           |
| Magnifier zoom               | `QDoubleSpinBox` (1.0–20.0, step 0.5)                    |
| Magnifier offset X/Y         | `QSpinBox` each (0–200)                                   |
| Magnifier upscale            | `QCheckBox` "Smooth upscaling (sub-pixel accuracy)"       |
| Output file path             | `QLineEdit` + browse `QPushButton`                        |
| Annotation names             | `AnnotationNameList` (see below)                          |
| Notes                        | `QPlainTextEdit`                                          |
| Show labels                  | `QCheckBox`                                               |
| Show coordinates             | `QCheckBox`                                               |

The **Magnifier upscale** toggle controls whether the lens uses bilinear interpolation (`SmoothPixmapTransform`) or nearest-neighbor when zooming in on image pixels. Smooth upscaling is useful when placing points between pixels (sub-pixel accuracy); nearest-neighbor is useful when you want to see exact pixel boundaries.

Every widget connects its change signal to a `_on_any_change` slot that assembles a fresh `dict` config and emits `config_changed`.

---

## Annotation Name List (`gui/annotation_list.py`)

```python
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView
from PySide6.QtCore import Qt, Signal


class AnnotationNameList(QListWidget):
    """
    Editable list of annotation name strings.
    Double-click or F2 to rename in place.
    The currently selected item determines the active annotation name.
    """

    active_name_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
        )
        self.currentTextChanged.connect(self.active_name_changed)
        self._add_default_names()

    def _add_default_names(self):
        for name in ["Point", "Feature", "Target"]:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.addItem(item)
        self.setCurrentRow(0)

    def add_name(self, name: str = "New annotation") -> None:
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.addItem(item)
        self.setCurrentItem(item)
        self.editItem(item)   # immediately enter edit mode

    def remove_selected(self) -> None:
        row = self.currentRow()
        if row >= 0 and self.count() > 1:  # always keep at least one
            self.takeItem(row)

    def get_names(self) -> list[str]:
        return [self.item(i).text() for i in range(self.count())]

    def populate_from_annotations(self, annotations: list[dict]) -> None:
        """
        Merge annotation names from TSV into the list (additive, no duplicates).
        Called when an image is loaded so that names from prior sessions reappear.
        """
        existing = set(self.get_names())
        for ann in annotations:
            if ann["annotation_name"] not in existing:
                item = QListWidgetItem(ann["annotation_name"])
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                self.addItem(item)
                existing.add(ann["annotation_name"])
```

**Annotation selection ↔ name update flow:**
1. User clicks an annotation marker on the canvas → canvas emits `annotation_selected(dict)` signal.
2. `MainWindow` finds the matching name in the list and calls `setCurrentRow()`.
3. When the user changes the list selection, `active_name_changed` fires → `config["active_annotation_name"]` updates.
4. If an annotation is currently selected and the user edits the list item text, a rename is applied to that annotation in memory and the TSV is re-saved.

---

## File Tree (`gui/file_tree.py`)

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView
from PySide6.QtCore import Signal, QModelIndex
from PySide6.QtGui import QFileSystemModel
from pathlib import Path


class FileTreeWidget(QWidget):
    image_selected = Signal(Path)

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif", ".webp"}

    def __init__(self, root: Path, parent=None):
        super().__init__(parent)
        self._model = QFileSystemModel()
        self._model.setNameFilters(["*.png", "*.jpg", "*.jpeg", "*.tiff",
                                    "*.tif", "*.bmp", "*.gif", "*.webp"])
        self._model.setNameFilterDisables(False)  # hide non-matching files entirely
        self._model.setRootPath(str(root))

        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setRootIndex(self._model.index(str(root)))
        self._tree.hideColumn(1)  # Size
        self._tree.hideColumn(2)  # Type
        self._tree.hideColumn(3)  # Date Modified
        self._tree.activated.connect(self._on_item_activated)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree)

    def set_root(self, path: Path) -> None:
        self._model.setRootPath(str(path))
        self._tree.setRootIndex(self._model.index(str(path)))

    def _on_item_activated(self, index: QModelIndex) -> None:
        path = Path(self._model.filePath(index))
        if path.suffix.lower() in self.SUPPORTED_EXTENSIONS and path.is_file():
            self.image_selected.emit(path)
```

`QFileSystemModel` loads directories in a background thread so the UI never blocks on large folders.

---

## Annotation Renderer (`renderer.py`)

Used by the `generate-images` CLI command. Operates entirely on Pillow images — no Qt dependency.

```python
from PIL import Image, ImageDraw
from pathlib import Path


def render_annotations_onto_image(
    image_path: Path,
    annotations: list[dict],
    output_path: Path,
    marker_size: int = 12,
    marker_color: tuple = (255, 0, 0, 255),
    marker_thickness: int = 2,
    show_labels: bool = True,
    show_coordinates: bool = False,
) -> None:
    """
    Draw annotation markers onto a copy of the image and save to output_path.
    All coordinates are in original image pixels (float) — no scaling needed.
    """
    with Image.open(image_path).convert("RGBA") as img:
        draw = ImageDraw.Draw(img)

        for ann in annotations:
            cx, cy = ann["location_x"], ann["location_y"]
            half = marker_size
            shape = ann["annotation_icon"]

            if shape == "X":
                draw.line([(cx - half, cy - half), (cx + half, cy + half)],
                          fill=marker_color, width=marker_thickness)
                draw.line([(cx + half, cy - half), (cx - half, cy + half)],
                          fill=marker_color, width=marker_thickness)
            elif shape == "+":
                draw.line([(cx - half, cy), (cx + half, cy)],
                          fill=marker_color, width=marker_thickness)
                draw.line([(cx, cy - half), (cx, cy + half)],
                          fill=marker_color, width=marker_thickness)
            elif shape == "O":
                draw.ellipse([(cx - half, cy - half), (cx + half, cy + half)],
                             outline=marker_color, width=marker_thickness)

            label_x = cx + half + 2
            if show_labels:
                draw.text((label_x, cy), ann["annotation_name"], fill=marker_color)
            if show_coordinates:
                y_offset = cy + 14 if show_labels else cy
                draw.text((label_x, y_offset), f"({cx:.1f},{cy:.1f})",
                          fill=(255, 255, 0, 255))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path))
```

---

## CLI (`cli.py`)

```python
import click
from pathlib import Path


@click.group(invoke_without_command=True)
@click.option("--annotations", "annotations_path", default="annotations.tsv",
              type=click.Path(), show_default=True,
              help="Output TSV file for annotations.")
@click.option("--images", "images_dir", default=".",
              type=click.Path(exists=True, file_okay=False),
              show_default=True,
              help="Folder to load in file tree (defaults to cwd).")
@click.pass_context
def cli(ctx, annotations_path, images_dir):
    """Image annotation tool."""
    ctx.ensure_object(dict)
    ctx.obj["annotations"] = Path(annotations_path)
    ctx.obj["images"] = Path(images_dir)
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command("ui")
@click.pass_context
def launch_ui(ctx):
    """Launch the graphical annotation interface."""
    from .app import launch_gui
    launch_gui(
        images_dir=ctx.obj["images"],
        annotations_file=ctx.obj["annotations"],
    )


@cli.command("generate-images")
@click.option("--format", "filename_template",
              default="{{image_file_no_ext}}-annotated.png",
              show_default=True,
              help="Jinja2 template for output filename. "
                   "Variables: image_file, image_file_no_ext, imageX, imageY")
@click.pass_context
def generate_images(ctx, filename_template):
    """Render annotations onto copies of images and save to disk."""
    from jinja2 import Template
    from .tsv_io import load_annotations
    from .renderer import render_annotations_onto_image
    from collections import defaultdict
    from PIL import Image

    tsv_path = ctx.obj["annotations"]
    annotations = load_annotations(tsv_path)

    by_image: dict[str, list] = defaultdict(list)
    for ann in annotations:
        by_image[ann["image_file"]].append(ann)

    template = Template(filename_template)

    for image_file, anns in by_image.items():
        img_path = Path(image_file)
        if not img_path.exists():
            click.echo(f"WARNING: image not found: {image_file}", err=True)
            continue

        with Image.open(img_path) as img:
            iw, ih = img.size

        out_name = template.render(
            image_file=image_file,
            image_file_no_ext=img_path.stem,
            imageX=iw,
            imageY=ih,
        )
        out_path = img_path.parent / out_name
        render_annotations_onto_image(img_path, anns, out_path)
        click.echo(f"Saved: {out_path}")
```

### CLI Usage Examples

```bash
# Launch GUI with defaults (cwd as image dir, annotations.tsv as output)
image-annotate ui

# Launch GUI specifying paths
image-annotate --annotations ./project.tsv --images ./photos/ ui

# Render annotated images using default filename pattern
image-annotate --annotations annotations.tsv generate-images

# Render with custom filename template
image-annotate --annotations annotations.tsv generate-images \
  --format "{{image_file_no_ext}}-{{imageX}}x{{imageY}}y-annotated.png"
```

---

## Main Window (`gui/main_window.py`)

```python
from PySide6.QtWidgets import QMainWindow, QSplitter, QStatusBar
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from pathlib import Path
from ..models import default_app_config
from ..tsv_io import load_annotations, append_annotation, save_annotations
from .image_canvas import AnnotationCanvas
from .config_panel import ConfigPanel
from .magnifier import MagnifierOverlay


class MainWindow(QMainWindow):
    def __init__(self, config: dict):
        super().__init__()
        self.setWindowTitle("Image Annotate")
        self._config = config
        self._annotations: list[dict] = []
        self._undo_stack: list[tuple[str, dict]] = []

        # Load all existing annotations at startup
        self._annotations = load_annotations(Path(config["annotations_file"]))

        # Widgets
        self._canvas = AnnotationCanvas(self)
        self._magnifier = MagnifierOverlay(self._canvas.viewport())
        self._canvas._magnifier = self._magnifier
        self._magnifier.set_config(config)
        self._config_panel = ConfigPanel(config, self)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._canvas)
        splitter.addWidget(self._config_panel)
        splitter.setStretchFactor(0, 3)   # canvas gets ~75%
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar())

        # Ctrl+Z undo
        undo_shortcut = QShortcut(QKeySequence.Undo, self)
        undo_shortcut.activated.connect(self._undo)

        self._connect_signals()

    def _connect_signals(self):
        self._config_panel.config_changed.connect(self._on_config_changed)
        self._config_panel.file_tree.image_selected.connect(self._on_image_selected)
        self._canvas.annotation_added.connect(self._on_annotation_added)
        self._canvas.annotation_removed.connect(self._on_annotation_removed)

    @Slot(dict)
    def _on_config_changed(self, config: dict):
        self._config = config
        self._canvas.set_config(config)

    @Slot(Path)
    def _on_image_selected(self, path: Path):
        self._canvas.load_image(path)
        img_anns = [a for a in self._annotations
                    if Path(a["image_file"]).resolve() == path.resolve()]
        self._canvas.set_annotations(img_anns)
        self._config_panel.annotation_list.populate_from_annotations(img_anns)
        self.statusBar().showMessage(
            f"Loaded: {path.name}  ({len(img_anns)} existing annotations)"
        )

    @Slot(dict)
    def _on_annotation_added(self, ann: dict):
        self._annotations.append(ann)
        self._undo_stack.append(("add", ann))
        append_annotation(ann, Path(self._config["annotations_file"]))
        self.statusBar().showMessage(
            f"Added: ({ann['location_x']:.1f}, {ann['location_y']:.1f})  '{ann['annotation_name']}'"
        )

    @Slot(str)
    def _on_annotation_removed(self, ann_id: str):
        ann = next((a for a in self._annotations if a["id"] == ann_id), None)
        if ann:
            self._annotations = [a for a in self._annotations if a["id"] != ann_id]
            self._undo_stack.append(("remove", ann))
            save_annotations(self._annotations, Path(self._config["annotations_file"]))

    def _undo(self):
        if not self._undo_stack:
            self.statusBar().showMessage("Nothing to undo.")
            return
        op, ann = self._undo_stack.pop()
        if op == "add":
            self._annotations = [a for a in self._annotations if a["id"] != ann["id"]]
            self._canvas.remove_annotation(ann["id"])
            save_annotations(self._annotations, Path(self._config["annotations_file"]))
            self.statusBar().showMessage(f"Undid add: '{ann['annotation_name']}'")
        elif op == "remove":
            self._annotations.append(ann)
            self._canvas.add_annotation(ann)
            append_annotation(ann, Path(self._config["annotations_file"]))
            self.statusBar().showMessage(f"Undid remove: '{ann['annotation_name']}'")
```

---

## Application Bootstrap (`app.py`)

```python
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from .models import default_app_config
from .gui.main_window import MainWindow


def launch_gui(images_dir: Path, annotations_file: Path) -> None:
    config = default_app_config(
        images_dir=str(images_dir),
        annotations_file=str(annotations_file),
    )
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("image-annotate")
    window = MainWindow(config)
    window.resize(1400, 900)
    window.show()
    sys.exit(app.exec())
```

---

## Packaging (`pyproject.toml`)

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "image-annotate"
version = "0.1.0"
description = "Point annotation tool for images with PySide6 GUI"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = [
    "PySide6>=6.6",
    "Pillow>=10.4",
    "click>=8.1",
    "Jinja2>=3.1",
]

[project.scripts]
image-annotate = "image_annotate.cli:cli"

[project.optional-dependencies]
dev = [
    "pytest>=7",
    "pytest-qt>=4",
    "black",
    "ruff",
    "mypy",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-dir]
"" = "src"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.mypy]
python_version = "3.11"
strict = true
```

### Installing for Development

```bash
pip install -e ".[dev]"
# Then run:
image-annotate ui
```

---

## Edge Cases and Key Decisions

### Coordinate System

With 1:1 zoom by default and the pixmap placed at scene origin, `mapToScene(viewport_pos)` directly yields image pixel coordinates as `float`. No custom transform math is needed for click handling. The `ScaleInfo.scale_factor` (from `view.transform().m11()`) is used only by the magnifier to compute the zoom region size.

**Path normalization:** `image_file` in the TSV stores a relative path when the image is under `images_dir`, or an absolute path otherwise. On load, resolve both sides (`Path.resolve()`) before comparing to handle `./photo.jpg` vs `photo.jpg`.

### Sub-pixel Precision

- `location_x/y` are stored as `float` in the TSV (formatted `:.4f` — four decimal places).
- At zoom levels >1:1, a single screen pixel represents a fraction of an image pixel. The crosshair position, reported via `mapToScene()`, naturally gives sub-pixel coordinates.
- The magnifier's **upscale** toggle enables bilinear interpolation when zooming in on image content, making it visually easier to judge where between pixels the point should be placed.
- Marker rendering uses `QPainter.Antialiasing` + `RoundCap`/`RoundJoin` to draw smoothly at fractional scene coordinates.

### Saving Strategy

- **Add**: `append_annotation()` — single row appended, no rewrite. Efficient for the common path.
- **Remove or undo**: `save_annotations()` — atomic full rewrite via temp-file rename.
- Undo stack holds `("add", dict)` or `("remove", dict)` tuples. Ctrl+Z reverses the last operation.

### Annotation Name List ↔ Existing Annotations

- Names are **additive**: loading a new image merges names from its TSV annotations into the list without removing names from the current session.
- If an annotation is selected on the canvas and the user changes the list selection, that annotation's name is updated in memory and the TSV is re-saved.
- `populate_from_annotations()` is always called after loading a new image.

### Marker Rendering at Different Zoom Levels

Since `QGraphicsItem` objects live in scene space (= image space), they naturally scale with the view zoom. At 2× zoom, a 12-image-pixel marker appears 24 screen pixels wide. This is the desired behavior — markers stay visually proportional to the image content.

For the Pillow renderer (`renderer.py`), markers are drawn at full image resolution using literal pixel measurements — no scaling applied.

### Large Images

At 1:1 zoom, large images show scrollbars and are navigated by panning. There is no memory overhead from downsampling. For extremely large images (e.g., 20000×20000), the full-res `QPixmap` is held in memory; `QGraphicsView` clips rendering to the visible viewport region so painting is always efficient regardless of image size.

### Right-Click Deletion Hit Testing

`HIT_TOLERANCE = max(10, marker_size / 2)` is in image/scene pixels. This scales proportionally with the marker size, so larger markers are easier to right-click-remove.

---

## Implementation Sequence

| Phase | Scope | Notes |
|-------|-------|-------|
| 1 | `models.py`, `tsv_io.py`, `coord_utils.py`, `pyproject.toml` | No Qt — fully testable with pytest |
| 2 | `image_canvas.py` — load image at 1:1, crosshair, scroll/zoom, left-click annotation | Minimal QApp harness |
| 3 | `file_tree.py`, `annotation_list.py`, `config_panel.py`, `main_window.py` | Wire all signals |
| 4 | `magnifier.py` — upscale toggle, integrate into canvas | |
| 5 | Undo stack in `main_window.py` — Ctrl+Z, append vs rewrite logic | |
| 6 | `cli.py`, `app.py`, `__main__.py` | Wire entry point |
| 7 | `renderer.py` — wire to `generate-images` command | Pillow only |
| 8 | Polish: status bar messages, Delete key, arrow-key image stepping, `QSettings` persistence | |

---

## Detailed Task List

### Phase 1 — Foundation (no Qt required) ✅

**Project scaffold**
- [x] Create `pyproject.toml` with all dependencies (`PySide6`, `Pillow`, `click`, `Jinja2`) and `[project.scripts]` entry point
- [x] Create `src/image_annotate/__init__.py`
- [x] Create `src/image_annotate/__main__.py` (`from .cli import cli; cli()`)
- [x] Create `src/image_annotate/utils/__init__.py`

**`models.py`**
- [x] Define `MarkerShape(str, Enum)` with `CROSS_X = "X"`, `CROSS_PLUS = "+"`, `CIRCLE = "O"`
- [x] Define `MarkerConfig` TypedDict (`shape`, `color`, `size`, `thickness`)
- [x] Define `MagnifierConfig` TypedDict (`enabled`, `size`, `zoom_factor`, `offset_x`, `offset_y`, `upscale`)
- [x] Define `Annotation` TypedDict with `location_x: float`, `location_y: float` (sub-pixel precision)
- [x] Define `AppConfig` TypedDict
- [x] Write `default_marker_config() -> dict` factory
- [x] Write `default_magnifier_config() -> dict` factory (includes `upscale: True`)
- [x] Write `default_app_config(images_dir, annotations_file) -> dict` factory
- [x] Write `make_annotation(...) -> dict` factory (generates `uuid4` id)

**`tsv_io.py`**
- [x] Define `TSV_FIELDNAMES` list matching the spec column order
- [x] Write `load_annotations(tsv_path) -> list[dict]` — returns empty list for missing file, skips corrupt rows, parses `location_x/y` as `float`
- [x] Write `append_annotation(annotation, tsv_path)` — single-row append, writes header if file is new/empty
- [x] Write `save_annotations(annotations, tsv_path)` — atomic full rewrite via `.tsv.tmp` rename
- [x] Write `_annotation_to_row(ann) -> dict` helper — formats `location_x/y` as `:.4f`

**`utils/coord_utils.py`**
- [x] Define `ScaleInfo` dataclass (`scale_factor: float`, `original_width: int`, `original_height: int`)
- [x] Write `scene_to_image(scene_x, scene_y, scale) -> tuple[float, float]` — clamps to image bounds, returns float
- [x] Write `image_to_scene(img_x, img_y) -> tuple[float, float]` — pass-through (scene = image coords)

**Tests**
- [x] `test_tsv_io.py`: round-trip write/read, missing-file returns `[]`, corrupt rows are skipped, float coords preserved
- [x] `test_coord_utils.py`: clamp at boundary, clamp below 0, in-bounds passthrough

---

### Phase 2 — Image Canvas ✅

**`gui/__init__.py`**
- [x] Create empty `src/image_annotate/gui/__init__.py`

**`gui/image_canvas.py`**
- [x] Subclass `QGraphicsView`, set render hints: `Antialiasing`, `SmoothPixmapTransform`, `TextAntialiasing`
- [x] Set 1:1 default transform (`setTransform(QTransform())`), `ScrollBarAsNeeded` on both axes
- [x] Set `setMouseTracking(True)` and `setCursor(Qt.BlankCursor)`
- [x] Implement `load_image(path)` — load `QPixmap` at native resolution, place at scene origin, reset transform to 1:1, rebuild crosshair and annotation graphics
- [x] Implement `_init_crosshair()` — two `QGraphicsLineItem` objects (dashed green, Z=10) spanning full scene rect
- [x] Implement `_update_crosshair(scene_pos)` — reposition h/v lines to cursor position, make visible
- [x] Implement `leaveEvent` — hide crosshair lines and magnifier
- [x] Implement `mouseMoveEvent` — update crosshair, forward to magnifier if enabled
- [x] Implement `wheelEvent` — Ctrl+scroll scales view transform (zoom), plain scroll pans (default behavior)
- [x] Implement `zoom_to(factor)` — set absolute view transform scale
- [x] Implement `mousePressEvent` — route left/right click
- [x] Implement `_handle_left_click(scene_pos)` — call `scene_to_image()` for clamped float coords, build annotation dict via `make_annotation()`, emit `annotation_added`
- [x] Implement `_handle_right_click(scene_pos)` — find nearest annotation within `max(10, marker_size/2)` image-pixel tolerance, emit `annotation_removed`
- [x] Implement `set_annotations(list[dict])` — replace list, call `_rebuild_annotation_graphics()`
- [x] Implement `add_annotation(dict)` — append to list, call `_draw_annotation()`
- [x] Implement `remove_annotation(id)` — remove `QGraphicsItem`s from scene, remove from list
- [x] Implement `_rebuild_annotation_graphics()` — clear all annotation items, redraw from list
- [x] Implement `_draw_annotation(dict)` — draw marker + optional label + optional coordinates
- [x] Implement `_draw_marker_on_scene()` — X (two diagonal lines), + (two axis lines), O (ellipse); all with `RoundCap`/`RoundJoin` pen for antialiased endpoints
- [x] Implement `set_config(dict)` — store config, rebuild annotation graphics, forward to magnifier

---

### Phase 3 — Config Panel & Main Window ✅

**`gui/file_tree.py`**
- [x] Create `FileTreeWidget(QWidget)` wrapping `QTreeView` + `QFileSystemModel`
- [x] Set name filters for supported image extensions, `setNameFilterDisables(False)` to hide non-images
- [x] Hide Size, Type, Date Modified columns
- [x] Emit `image_selected(Path)` signal on `activated` (file double-click / Enter)
- [x] Implement `set_root(path)` to change the displayed directory

**`gui/annotation_list.py`**
- [x] Create `AnnotationNameList(QListWidget)` with `DoubleClicked | EditKeyPressed` edit triggers
- [x] Emit `active_name_changed(str)` signal wired to `currentTextChanged`
- [x] Add default items ("Point", "Feature", "Target") with `Qt.ItemIsEditable` flag; select first row
- [x] Implement `add_name(name)` — add item, select it, immediately enter edit mode
- [x] Implement `remove_selected()` — remove current row (guard: always keep at least one item)
- [x] Implement `get_names() -> list[str]`
- [x] Implement `populate_from_annotations(list[dict])` — additive merge of unique names from annotations

**`gui/config_panel.py`**
- [x] Wrap entire panel in `QScrollArea` so it is navigable on small screens
- [x] **Marker group** (`QGroupBox`): shape radio buttons (X / + / O), color picker button with swatch, size `QSpinBox` (4–200), thickness `QSpinBox` (1–20)
- [x] **Magnifier group** (`QGroupBox`): enable `QCheckBox`, size `QSlider` (50–400) + `QLabel`, zoom `QDoubleSpinBox` (1.0–20.0 step 0.5), offset X/Y `QSpinBox` (0–200), upscale `QCheckBox` ("Smooth upscaling (sub-pixel)")
- [x] **Output group**: output path `QLineEdit` + browse `QPushButton` (opens `QFileDialog`)
- [x] **Annotation names section**: embed `AnnotationNameList`, add "+" and "−" buttons below it
- [x] **Notes**: `QPlainTextEdit`
- [x] **Display toggles**: "Show labels" `QCheckBox`, "Show coordinates" `QCheckBox`
- [x] Connect all widget signals to `_on_any_change` slot
- [x] `_on_any_change()` — assemble fresh config dict from all widget values, emit `config_changed(dict)`
- [x] Expose `self.file_tree`, `self.annotation_list` as attributes for `MainWindow` to connect to
- [x] Define `config_changed = Signal(dict)`

**`gui/main_window.py`**
- [x] `QMainWindow` with horizontal `QSplitter` (canvas left, config panel right)
- [x] Set splitter stretch factors 3:1 (canvas gets ~75%)
- [x] Add `QStatusBar`
- [x] On init, load all existing annotations from TSV via `load_annotations()`
- [x] Wire `ConfigPanel.config_changed` → `_on_config_changed`
- [x] Wire `FileTreeWidget.image_selected` → `_on_image_selected`
- [x] Wire `AnnotationCanvas.annotation_added` → `_on_annotation_added`
- [x] Wire `AnnotationCanvas.annotation_removed` → `_on_annotation_removed`
- [x] `_on_image_selected(path)` — call `canvas.load_image()`, filter annotations by resolved path, call `canvas.set_annotations()` and `annotation_list.populate_from_annotations()`, update status bar
- [x] `_on_annotation_added(dict)` — append to `_annotations`, push `("add", ann)` onto undo stack, call `append_annotation()`, update status bar
- [x] `_on_annotation_removed(id)` — remove from `_annotations`, push `("remove", ann)` onto undo stack, call `save_annotations()`, update status bar
- [x] `_undo()` — pop undo stack; if `"add"`: remove annotation + `save_annotations()`; if `"remove"`: re-add annotation + `append_annotation()`; update status bar
- [x] Wire `QShortcut(QKeySequence.Undo, self)` → `_undo()`

---

### Phase 4 — Magnifier ✅

**`gui/magnifier.py`**
- [x] Create `MagnifierOverlay(QWidget)` as child of canvas viewport
- [x] Set `WA_TransparentForMouseEvents` (clicks pass through), `WA_NoSystemBackground`, `Qt.SubWindow` flag
- [x] Implement `set_config(dict)` — update `_size`, `_zoom_factor`, `_offset_x/y`, `_upscale`; call `resize()`
- [x] Implement `update_from_cursor(cursor_view_pos, scene_pos, pixmap_item, scale_info)`:
  - Use `scene_pos.x()/y()` directly as image coordinates (no transform needed)
  - Compute `zoom_rect` as `QRect` centered on cursor in source pixmap coords
  - Compute lens position with offset, clamp to viewport bounds
  - Call `show()` + `update()`
- [x] Implement `paintEvent`:
  - Set `SmoothPixmapTransform` hint based on `_upscale` flag
  - Clip painter to circular `QPainterPath`
  - `drawPixmap(dest_rect, source_pixmap, zoom_rect)` to fill the lens
  - Draw white border ring (unclipped)
  - Draw green center crosshair lines
- [x] Integrate into `image_canvas.py` `mouseMoveEvent` (already stubbed in Phase 2)

---

### Phase 5 — CLI & Entry Point ✅

**`cli.py`**
- [x] Define `@click.group` `cli` with `--annotations` (default `annotations.tsv`) and `--images` (default `.`) options, stored in `ctx.obj`
- [x] Define `ui` subcommand — calls `launch_gui(images_dir, annotations_file)`
- [x] Define `generate-images` subcommand with `--format` Jinja2 template option (default `{{image_file_no_ext}}-annotated.png`)
- [x] `generate-images` implementation: load TSV, group by image file, render each via `render_annotations_onto_image()`, print saved paths

**`app.py`**
- [x] `launch_gui(images_dir, annotations_file)` — build `default_app_config()` dict, create `QApplication`, instantiate `MainWindow`, `window.resize(1400, 900)`, `window.show()`, `sys.exit(app.exec())`

**Smoke tests**
- [x] `image-annotate --help` shows expected options
- [x] `image-annotate ui --help` shows expected options
- [x] `image-annotate generate-images --help` shows expected options

---

### Phase 6 — Annotation Renderer ✅

**`renderer.py`**
- [x] `render_annotations_onto_image(image_path, annotations, output_path, ...)` — open image as RGBA, draw each annotation marker (X / + / O) using `ImageDraw`, handle float coords by rounding to nearest pixel for line endpoints
- [x] Draw optional label text (`ann["annotation_name"]`) offset right of marker
- [x] Draw optional coordinate text (`(x.x, y.y)`) below label if both enabled, or at same offset if label disabled
- [x] Create output parent directories if needed, save output image
- [x] Wire into `generate-images` CLI subcommand
- [x] Manual test: generate annotated image from a sample TSV and verify output visually

---

### Phase 7 — Polish ✅

**UX improvements**
- [x] Status bar: show current zoom % on zoom change
- [x] Status bar: show cursor image coordinates (x, y) on `mouseMoveEvent` while inside image bounds
- [x] Delete key shortcut: remove the most-recently-added annotation for the current image (or implement selection + Delete)
- [x] Arrow key navigation: Left/Right (or Up/Down) move to previous/next image in the file tree
- [x] "Reset Zoom" action: Ctrl+0 resets view transform to 1:1
- [x] Zoom controls: `+` / `-` keys to step zoom by 10%

**Persistence**
- [x] Use `QSettings` to persist on exit and restore on startup:
  - Last used `images_dir`
  - Last used `annotations_file` path
  - Window geometry and splitter position
  - All `AppConfig` values (marker shape/color/size, magnifier settings, toggles)

**Error handling**
- [x] Show `QMessageBox.warning` if an image file cannot be opened (corrupt, permissions)
- [x] Show `QMessageBox.warning` if the TSV cannot be written (disk full, permissions)
- [x] Gracefully skip unreadable images in `generate-images` CLI (already partially handled — add user-visible error count summary)

**`gui/dialogs.py`**
- [x] About dialog: app name, version, brief description

---

## Critical Files Summary

| File | Role |
|------|------|
| `src/image_annotate/models.py` | Data contracts (TypedDicts + factory functions); no class instances |
| `src/image_annotate/tsv_io.py` | Append-only add, atomic full rewrite for mutations |
| `src/image_annotate/gui/image_canvas.py` | 1:1 zoom, scroll/pan, antialiased markers, click handling |
| `src/image_annotate/gui/magnifier.py` | Floating zoom lens with upscale toggle |
| `src/image_annotate/gui/main_window.py` | Undo stack, signal wiring, config dispatch |
| `src/image_annotate/cli.py` | Public interface and entry point |
| `src/image_annotate/renderer.py` | Headless Pillow renderer for batch image export |
