import logging
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
)

from ..tsv_io import load_annotations, save_annotations
from ..utils.metadata import read_photo_metadata
from .config_panel import ConfigPanel
from .dialogs import AboutDialog
from .image_canvas import AnnotationCanvas
from .magnifier import MagnifierOverlay

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, config: dict):
        super().__init__()
        self.setWindowTitle("image-annotate")
        self._config = config
        self._annotations: list[dict] = []
        self._current_image_path: Path | None = None

        # Load annotations and determine annotation styles
        try:
            self._annotations, session_config = load_annotations(
                Path(config["annotations_file"])
            )
            header_styles = session_config.get("annotation_styles", {})
            used_names = {ann["annotation_name"] for ann in self._annotations}

            if used_names:
                # Build styles only for names that actually appear in data rows.
                # Style details come from the header when available; otherwise defaults.
                styles: dict = {}
                for name in used_names:
                    styles[name] = header_styles.get(name, {
                        "shape": "X",
                        "color": "#FF0000",
                        "size": 12,
                        "thickness": 2,
                    })
                config["annotation_styles"] = styles
            elif header_styles:
                # No data rows but header has styles (user configured before annotating)
                config["annotation_styles"] = header_styles
            else:
                # Truly empty / new file — offer a single starter annotation
                from ..models import DEFAULT_STYLES
                first_name = next(iter(DEFAULT_STYLES))
                config["annotation_styles"] = {first_name: dict(DEFAULT_STYLES[first_name])}

            if "zoom" in session_config:
                config["zoom"] = session_config["zoom"]
            if "show_labels" in session_config:
                config["show_labels"] = session_config["show_labels"]
            if "show_coordinates" in session_config:
                config["show_coordinates"] = session_config["show_coordinates"]
            if "metadata_fields" in session_config:
                config["metadata_fields"] = session_config["metadata_fields"]
        except Exception as e:
            QMessageBox.warning(self, "Load error", f"Could not load annotations:\n{e}")

        self._zoom_level: float = config.get("zoom", 1.0)

        self._canvas = AnnotationCanvas(self)
        self._magnifier = MagnifierOverlay(self._canvas.viewport())
        self._canvas._magnifier = self._magnifier
        self._magnifier.set_config(config)

        self._config_panel = ConfigPanel(config, self)
        self._config_panel.populate_annotation_styles(config.get("annotation_styles", {}))

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._canvas)
        splitter.addWidget(self._config_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([880, 520])
        self.setCentralWidget(splitter)

        self._status = QStatusBar()
        self.setStatusBar(self._status)

        self._connect_signals()
        self._setup_shortcuts()
        self._restore_settings()

    def _connect_signals(self):
        self._config_panel.config_changed.connect(self._on_config_changed)
        self._config_panel.file_tree.image_selected.connect(self._on_image_selected)
        self._canvas.annotation_added.connect(self._on_annotation_added)
        self._canvas.annotation_removed.connect(self._on_annotation_removed)
        self._canvas.zoom_changed.connect(self._on_zoom_changed)
        self._canvas.cursor_moved.connect(self._on_cursor_moved)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence.StandardKey.Undo, self).activated.connect(self._undo)
        QShortcut(QKeySequence("Ctrl+0"), self).activated.connect(
            lambda: self._canvas.zoom_to(1.0)
        )
        QShortcut(QKeySequence("+"), self).activated.connect(
            lambda: self._canvas.zoom_to(self._canvas.current_zoom() * 1.1)
        )
        QShortcut(QKeySequence("-"), self).activated.connect(
            lambda: self._canvas.zoom_to(self._canvas.current_zoom() / 1.1)
        )
        QShortcut(QKeySequence("Right"), self).activated.connect(self._next_image)
        QShortcut(QKeySequence("Left"), self).activated.connect(self._prev_image)

    @Slot(dict)
    def _on_config_changed(self, config: dict):
        self._config = config
        self._zoom_level = config.get("zoom", self._zoom_level)
        self._canvas.set_config(config)

    @Slot(Path)
    def _on_image_selected(self, path: Path):
        self._current_image_path = path
        log.debug("image selected: %s", path.resolve())
        try:
            self._canvas.load_image(path)
        except Exception as e:
            QMessageBox.warning(self, "Image error", f"Could not open image:\n{e}")
            return

        # Apply stored zoom (preserves zoom across image switches)
        self._canvas.zoom_to(self._zoom_level)

        # Reload full annotation list from TSV
        try:
            self._annotations, _ = load_annotations(Path(self._config["annotations_file"]))
        except Exception:
            pass

        images_dir = Path(self._config.get("images_dir", "."))
        log.debug("images_dir: %s", Path(images_dir).resolve())
        log.debug("total annotations in TSV: %d", len(self._annotations))

        img_anns = []
        for a in self._annotations:
            candidate = (images_dir / a["image_file"]).resolve()
            match = candidate == path.resolve()
            log.debug("  %s  →  %s  match=%s", a["image_file"], candidate, match)
            if match:
                img_anns.append(a)
        log.debug("annotations matched for this image: %d", len(img_anns))

        self._canvas.set_annotations(img_anns)
        self._canvas.set_config(self._config)
        self._config_panel.annotation_list.populate_from_annotations(img_anns)

        n = len(img_anns)
        pct = int(self._zoom_level * 100)
        self._status.showMessage(f"{path.name}  —  {n} annotation(s)  |  zoom {pct}%")

    @Slot(dict)
    def _on_annotation_added(self, ann: dict):
        # Attach photo metadata for enabled fields
        if self._current_image_path:
            try:
                meta = read_photo_metadata(self._current_image_path)
                for field in self._config.get("metadata_fields", []):
                    ann[field] = meta.get(field, "")
            except Exception as exc:
                log.debug("metadata read failed: %s", exc)

        self._annotations.append(ann)
        try:
            save_annotations(
                self._annotations,
                Path(self._config["annotations_file"]),
                session_config=self._config,
            )
        except Exception as e:
            QMessageBox.warning(self, "Save error", f"Could not write annotations:\n{e}")
        self._status.showMessage(
            f"Added '{ann['annotation_name']}' at "
            f"({ann['location_x']:.1f}, {ann['location_y']:.1f})"
        )

    @Slot(str)
    def _on_annotation_removed(self, ann_id: str):
        self._annotations = [a for a in self._annotations if a["id"] != ann_id]
        try:
            save_annotations(
                self._annotations,
                Path(self._config["annotations_file"]),
                session_config=self._config,
            )
        except Exception as e:
            QMessageBox.warning(self, "Save error", f"Could not write annotations:\n{e}")
        self._status.showMessage("Removed annotation")

    def _undo(self):
        """Remove the last annotation in the TSV for the currently-selected image."""
        if not self._current_image_path:
            self._status.showMessage("No image selected.")
            return

        images_dir = Path(self._config.get("images_dir", "."))
        try:
            rel = str(self._current_image_path.relative_to(images_dir))
        except ValueError:
            rel = str(self._current_image_path)

        # Find last annotation that belongs to the current image
        last_ann = None
        for ann in reversed(self._annotations):
            if ann["image_file"] == rel:
                last_ann = ann
                break

        if last_ann is None:
            self._status.showMessage("No annotations to undo for this image.")
            return

        self._annotations = [a for a in self._annotations if a["id"] != last_ann["id"]]
        self._canvas.remove_annotation(last_ann["id"])
        try:
            save_annotations(
                self._annotations,
                Path(self._config["annotations_file"]),
                session_config=self._config,
            )
        except Exception as e:
            QMessageBox.warning(self, "Save error", f"Could not write annotations:\n{e}")
        self._status.showMessage(f"Undid: '{last_ann['annotation_name']}'")

    @Slot(float)
    def _on_zoom_changed(self, factor: float):
        self._zoom_level = factor
        self._config["zoom"] = factor
        pct = int(factor * 100)
        name = self._current_image_path.name if self._current_image_path else ""
        self._status.showMessage(f"{name}  |  zoom {pct}%")

    @Slot(float, float)
    def _on_cursor_moved(self, x: float, y: float):
        pct = int(self._canvas.current_zoom() * 100)
        name = self._current_image_path.name if self._current_image_path else ""
        self._status.showMessage(f"{name}  |  x={x:.1f}  y={y:.1f}  |  zoom {pct}%")

    def _next_image(self):
        self._config_panel.file_tree._tree.setCurrentIndex(
            self._config_panel.file_tree._tree.indexBelow(
                self._config_panel.file_tree._tree.currentIndex()
            )
        )
        idx = self._config_panel.file_tree._tree.currentIndex()
        self._config_panel.file_tree._on_item_activated(idx)

    def _prev_image(self):
        self._config_panel.file_tree._tree.setCurrentIndex(
            self._config_panel.file_tree._tree.indexAbove(
                self._config_panel.file_tree._tree.currentIndex()
            )
        )
        idx = self._config_panel.file_tree._tree.currentIndex()
        self._config_panel.file_tree._on_item_activated(idx)

    def _restore_settings(self):
        from PySide6.QtCore import QSettings
        s = QSettings("image-annotate", "image-annotate")
        geom = s.value("geometry")
        if geom:
            self.restoreGeometry(geom)

    def closeEvent(self, event):
        from PySide6.QtCore import QSettings
        s = QSettings("image-annotate", "image-annotate")
        s.setValue("geometry", self.saveGeometry())

        # Persist session config (styles, zoom, display settings) to TSV on close,
        # even if no annotation was added/removed in this session.
        tsv_path = Path(self._config.get("annotations_file", "annotations.tsv"))
        if self._annotations or tsv_path.exists():
            try:
                save_annotations(
                    self._annotations,
                    tsv_path,
                    session_config=self._config,
                )
            except Exception as e:
                log.warning("Could not save session config on close: %s", e)

        super().closeEvent(event)

    def show_about(self):
        AboutDialog(self).exec()
