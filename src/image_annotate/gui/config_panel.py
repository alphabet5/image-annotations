from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .annotation_list import AnnotationNameList
from .file_tree import FileTreeWidget
from ..utils.metadata import KNOWN_METADATA_FIELDS

METADATA_LABELS: dict[str, str] = {
    "photo_timestamp": "Photo timestamp",
    "camera_make":     "Camera make",
    "camera_model":    "Camera model",
    "gps_latitude":    "GPS latitude",
    "gps_longitude":   "GPS longitude",
}


class ConfigPanel(QWidget):
    config_changed = Signal(dict)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._suppress_signals = False

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        images_dir = Path(config.get("images_dir", "."))
        image_files_raw = config.get("image_files")
        image_files = [Path(p) for p in image_files_raw] if image_files_raw else None
        self.file_tree = FileTreeWidget(images_dir, files=image_files, parent=self)
        self.file_tree.setMinimumHeight(200)
        layout.addWidget(self.file_tree)

        layout.addWidget(self._build_notes_group())
        layout.addWidget(self._build_annotation_names_group(config))
        layout.addWidget(self._build_magnifier_group(config))
        layout.addWidget(self._build_adjustments_group(config))
        layout.addWidget(self._build_metadata_group(config))
        layout.addWidget(self._build_output_group(config))
        layout.addWidget(self._build_display_group(config))
        layout.addStretch()

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.setMinimumWidth(520)

    # ------------------------------------------------------------------
    # Group builders
    # ------------------------------------------------------------------

    def _build_notes_group(self) -> QGroupBox:
        group = QGroupBox("Notes")
        layout = QVBoxLayout(group)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Notes for this image…")
        self.notes_edit.setMaximumHeight(80)
        layout.addWidget(self.notes_edit)
        return group

    def _build_annotation_names_group(self, config: dict) -> QGroupBox:
        group = QGroupBox("Annotations")
        layout = QVBoxLayout(group)

        # Header row: Name | Shape | Color | Size | Thick
        header = QHBoxLayout()
        header.setSpacing(3)
        header.addSpacing(20)  # align with radio button
        lbl_name = QLabel("Name")
        lbl_name.setMinimumWidth(60)
        header.addWidget(lbl_name)
        header.addWidget(QLabel("Shp"))
        header.addWidget(QLabel("Col"))
        header.addWidget(QLabel("Sz"))
        header.addWidget(QLabel("Th"))
        layout.addLayout(header)

        self.annotation_list = AnnotationNameList(self)
        self.annotation_list.active_name_changed.connect(self._on_any_change)
        self.annotation_list.styles_changed.connect(self._on_any_change)
        layout.addWidget(self.annotation_list)

        return group

    def _build_magnifier_group(self, config: dict) -> QGroupBox:
        group = QGroupBox("Magnifier")
        layout = QVBoxLayout(group)
        mag = config.get("magnifier", {})

        self._mag_enabled = QCheckBox("Enabled")
        self._mag_enabled.setChecked(mag.get("enabled", True))
        self._mag_enabled.toggled.connect(self._on_any_change)
        layout.addWidget(self._mag_enabled)

        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Size:"))
        self._mag_size = QSlider(Qt.Orientation.Horizontal)
        self._mag_size.setRange(50, 400)
        self._mag_size.setValue(mag.get("size", 150))
        self._mag_size_label = QLabel(str(self._mag_size.value()))
        self._mag_size.valueChanged.connect(lambda v: self._mag_size_label.setText(str(v)))
        self._mag_size.valueChanged.connect(self._on_any_change)
        size_layout.addWidget(self._mag_size)
        size_layout.addWidget(self._mag_size_label)
        layout.addLayout(size_layout)

        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        self._mag_zoom = QDoubleSpinBox()
        self._mag_zoom.setRange(1.0, 20.0)
        self._mag_zoom.setSingleStep(0.5)
        self._mag_zoom.setValue(mag.get("zoom_factor", 4.0))
        self._mag_zoom.valueChanged.connect(self._on_any_change)
        zoom_layout.addWidget(self._mag_zoom)
        layout.addLayout(zoom_layout)

        offset_layout = QHBoxLayout()
        offset_layout.addWidget(QLabel("Offset X:"))
        self._mag_offset_x = QSpinBox()
        self._mag_offset_x.setRange(0, 200)
        self._mag_offset_x.setValue(mag.get("offset_x", 20))
        self._mag_offset_x.valueChanged.connect(self._on_any_change)
        offset_layout.addWidget(self._mag_offset_x)
        offset_layout.addWidget(QLabel("Y:"))
        self._mag_offset_y = QSpinBox()
        self._mag_offset_y.setRange(0, 200)
        self._mag_offset_y.setValue(mag.get("offset_y", 20))
        self._mag_offset_y.valueChanged.connect(self._on_any_change)
        offset_layout.addWidget(self._mag_offset_y)
        layout.addLayout(offset_layout)

        self._mag_upscale = QCheckBox("Smooth upscaling (sub-pixel)")
        self._mag_upscale.setChecked(mag.get("upscale", True))
        self._mag_upscale.toggled.connect(self._on_any_change)
        layout.addWidget(self._mag_upscale)

        return group

    def _build_adjustments_group(self, config: dict) -> QGroupBox:
        group = QGroupBox("Image Adjustments")
        layout = QVBoxLayout(group)
        adj = config.get("image_adjustments", {})

        exp_row = QHBoxLayout()
        exp_row.addWidget(QLabel("Exposure (×):"))
        self._adj_exposure = QDoubleSpinBox()
        self._adj_exposure.setRange(0.1, 4.0)
        self._adj_exposure.setSingleStep(0.1)
        self._adj_exposure.setDecimals(2)
        self._adj_exposure.setValue(adj.get("exposure", 1.0))
        self._adj_exposure.valueChanged.connect(self._on_any_change)
        exp_row.addWidget(self._adj_exposure)
        layout.addLayout(exp_row)

        bri_row = QHBoxLayout()
        bri_row.addWidget(QLabel("Brightness (×):"))
        self._adj_brightness = QDoubleSpinBox()
        self._adj_brightness.setRange(0.1, 3.0)
        self._adj_brightness.setSingleStep(0.05)
        self._adj_brightness.setDecimals(2)
        self._adj_brightness.setValue(adj.get("brightness", 1.0))
        self._adj_brightness.valueChanged.connect(self._on_any_change)
        bri_row.addWidget(self._adj_brightness)
        layout.addLayout(bri_row)

        gam_row = QHBoxLayout()
        gam_row.addWidget(QLabel("Gamma:"))
        self._adj_gamma = QDoubleSpinBox()
        self._adj_gamma.setRange(0.1, 5.0)
        self._adj_gamma.setSingleStep(0.1)
        self._adj_gamma.setDecimals(2)
        self._adj_gamma.setValue(adj.get("gamma", 1.0))
        self._adj_gamma.valueChanged.connect(self._on_any_change)
        gam_row.addWidget(self._adj_gamma)
        layout.addLayout(gam_row)

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._reset_adjustments)
        layout.addWidget(reset_btn)

        return group

    def _reset_adjustments(self):
        self._suppress_signals = True
        self._adj_exposure.setValue(1.0)
        self._adj_brightness.setValue(1.0)
        self._adj_gamma.setValue(1.0)
        self._suppress_signals = False
        self._on_any_change()

    def _build_metadata_group(self, config: dict) -> QGroupBox:
        group = QGroupBox("Metadata fields (saved to TSV)")
        layout = QVBoxLayout(group)
        enabled = set(config.get("metadata_fields", ["photo_timestamp"]))
        self._metadata_checks: dict[str, QCheckBox] = {}
        for field, label in METADATA_LABELS.items():
            cb = QCheckBox(label)
            cb.setChecked(field in enabled)
            cb.toggled.connect(self._on_any_change)
            self._metadata_checks[field] = cb
            layout.addWidget(cb)
        return group

    def _build_output_group(self, config: dict) -> QGroupBox:
        group = QGroupBox("Output file")
        layout = QVBoxLayout(group)
        lbl = QLabel(config.get("annotations_file", "annotations.tsv"))
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(lbl)
        return group

    def _build_display_group(self, config: dict) -> QGroupBox:
        group = QGroupBox("Display")
        layout = QVBoxLayout(group)
        self._show_labels = QCheckBox("Show labels")
        self._show_labels.setChecked(config.get("show_labels", True))
        self._show_labels.toggled.connect(self._on_any_change)
        layout.addWidget(self._show_labels)

        self._show_coords = QCheckBox("Show coordinates")
        self._show_coords.setChecked(config.get("show_coordinates", False))
        self._show_coords.toggled.connect(self._on_any_change)
        layout.addWidget(self._show_coords)
        return group

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def populate_annotation_styles(self, styles: dict) -> None:
        """Load annotation styles from config into the annotation list widget."""
        self._suppress_signals = True
        self.annotation_list.populate_from_config(styles)
        self._suppress_signals = False

    # ------------------------------------------------------------------
    # Signal handler
    # ------------------------------------------------------------------

    def _on_any_change(self, *_):
        if self._suppress_signals:
            return
        config = {
            "images_dir": self._config.get("images_dir", "."),
            "annotations_file": self._config.get("annotations_file", "annotations.tsv"),
            "annotation_styles": self.annotation_list.get_styles(),
            "magnifier": {
                "enabled": self._mag_enabled.isChecked(),
                "size": self._mag_size.value(),
                "zoom_factor": self._mag_zoom.value(),
                "offset_x": self._mag_offset_x.value(),
                "offset_y": self._mag_offset_y.value(),
                "upscale": self._mag_upscale.isChecked(),
            },
            "image_adjustments": {
                "exposure":   self._adj_exposure.value(),
                "brightness": self._adj_brightness.value(),
                "gamma":      self._adj_gamma.value(),
            },
            "show_labels": self._show_labels.isChecked(),
            "show_coordinates": self._show_coords.isChecked(),
            "active_annotation_name": self.annotation_list.get_active_name(),
            "metadata_fields": [
                f for f, cb in self._metadata_checks.items() if cb.isChecked()
            ],
            "zoom": self._config.get("zoom", 1.0),
        }
        self._config = config
        self.config_changed.emit(config)
