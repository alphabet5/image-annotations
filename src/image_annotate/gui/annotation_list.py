from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class AnnotationRow(QWidget):
    selected = Signal(str)            # annotation name when this row is activated
    style_changed = Signal(str, dict) # (name, new_style)
    name_changed = Signal(str, str)   # (old_name, new_name)

    def __init__(self, name: str, style: dict, parent=None):
        super().__init__(parent)
        self._name = name
        self._color = style.get("color", "#FF0000")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(3)

        self._select_btn = QRadioButton()
        self._select_btn.toggled.connect(
            lambda checked: self.selected.emit(self._name) if checked else None
        )
        layout.addWidget(self._select_btn)

        self._name_edit = QLineEdit(name)
        self._name_edit.setMinimumWidth(60)
        self._name_edit.editingFinished.connect(self._on_name_changed)
        layout.addWidget(self._name_edit)

        self._shape_combo = QComboBox()
        self._shape_combo.addItems(["X", "+", "O"])
        self._shape_combo.setCurrentText(style.get("shape", "X"))
        self._shape_combo.setFixedWidth(42)
        self._shape_combo.currentTextChanged.connect(self._emit_style)
        layout.addWidget(self._shape_combo)

        self._color_btn = QPushButton()
        self._color_btn.setFixedWidth(26)
        self._color_btn.setFixedHeight(22)
        self._apply_color(self._color)
        self._color_btn.clicked.connect(self._pick_color)
        layout.addWidget(self._color_btn)

        self._size_spin = QSpinBox()
        self._size_spin.setRange(4, 200)
        self._size_spin.setValue(style.get("size", 12))
        self._size_spin.setFixedWidth(50)
        self._size_spin.setToolTip("Size (px)")
        self._size_spin.valueChanged.connect(self._emit_style)
        layout.addWidget(self._size_spin)

        self._thick_spin = QSpinBox()
        self._thick_spin.setRange(1, 20)
        self._thick_spin.setValue(style.get("thickness", 2))
        self._thick_spin.setFixedWidth(40)
        self._thick_spin.setToolTip("Thickness")
        self._thick_spin.valueChanged.connect(self._emit_style)
        layout.addWidget(self._thick_spin)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_name(self) -> str:
        return self._name

    def get_style(self) -> dict:
        return {
            "shape": self._shape_combo.currentText(),
            "color": self._color,
            "size": self._size_spin.value(),
            "thickness": self._thick_spin.value(),
        }

    def set_active(self, active: bool) -> None:
        self._select_btn.setChecked(active)

    def is_active(self) -> bool:
        return self._select_btn.isChecked()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self._color), self, "Pick color")
        if color.isValid():
            self._color = color.name()
            self._apply_color(self._color)
            self._emit_style()

    def _apply_color(self, hex_color: str):
        self._color_btn.setStyleSheet(
            f"background-color: {hex_color}; border: 1px solid #888;"
        )

    def _emit_style(self, *_):
        self.style_changed.emit(self._name, self.get_style())

    def _on_name_changed(self):
        new_name = self._name_edit.text().strip()
        if not new_name:
            self._name_edit.setText(self._name)
            return
        if new_name != self._name:
            old = self._name
            self._name = new_name
            self.name_changed.emit(old, new_name)


class AnnotationNameList(QWidget):
    active_name_changed = Signal(str)
    styles_changed = Signal(dict)   # full {name: style} dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[AnnotationRow] = []
        self._styles: dict[str, dict] = {}

        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)

        self._rows_widget = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setSpacing(1)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll = QScrollArea()
        scroll.setWidget(self._rows_widget)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(100)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 2, 0, 0)
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(28)
        add_btn.setToolTip("Add annotation type")
        add_btn.clicked.connect(lambda: self.add_name())
        remove_btn = QPushButton("−")
        remove_btn.setFixedWidth(28)
        remove_btn.setToolTip("Remove selected annotation type")
        remove_btn.clicked.connect(self.remove_selected)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll)
        outer.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_name(self, name: str = "New annotation", style: dict | None = None) -> None:
        """Add a new row, deduplicating the name if necessary."""
        existing = set(self.get_names())
        base = name
        n = 1
        while name in existing:
            name = f"{base} {n}"
            n += 1
        style = style or {"shape": "X", "color": "#FF0000", "size": 12, "thickness": 2}
        self._add_row(name, style)
        self._emit_styles()

    def remove_selected(self) -> None:
        if len(self._rows) <= 1:
            return
        for i, row in enumerate(self._rows):
            if row.is_active():
                self._btn_group.removeButton(row._select_btn)
                self._styles.pop(row.get_name(), None)
                self._rows.pop(i)
                row.deleteLater()
                # Select adjacent row
                select_idx = min(i, len(self._rows) - 1)
                if self._rows:
                    self._rows[select_idx].set_active(True)
                self._emit_styles()
                return

    def get_names(self) -> list[str]:
        return [r.get_name() for r in self._rows]

    def get_active_name(self) -> str:
        for row in self._rows:
            if row.is_active():
                return row.get_name()
        if self._rows:
            return self._rows[0].get_name()
        return "Point"

    def get_styles(self) -> dict[str, dict]:
        # Rebuild from live rows (authoritative)
        return {r.get_name(): r.get_style() for r in self._rows}

    def set_active_name(self, name: str) -> None:
        for row in self._rows:
            if row.get_name() == name:
                row.set_active(True)
                return

    def populate_from_config(self, annotation_styles: dict) -> None:
        """Rebuild rows from a styles dict (called at startup / session restore)."""
        # Clear existing rows
        for row in self._rows:
            self._btn_group.removeButton(row._select_btn)
            row.deleteLater()
        self._rows.clear()
        self._styles.clear()

        for name, style in annotation_styles.items():
            self._add_row(name, dict(style), emit=False)

        if self._rows:
            self._rows[0].set_active(True)
        self._emit_styles()

    def populate_from_annotations(self, annotations: list[dict]) -> None:
        """Add rows for annotation names not already listed (from TSV rows)."""
        existing = set(self.get_names())
        added = False
        for ann in annotations:
            name = ann["annotation_name"]
            if name not in existing:
                style = {
                    "shape": "X",
                    "color": ann.get("annotation_color", "#FF0000"),
                    "size": 12,
                    "thickness": 2,
                }
                self._add_row(name, style, emit=False)
                existing.add(name)
                added = True
        if added:
            if self._rows and not any(r.is_active() for r in self._rows):
                self._rows[0].set_active(True)
            self._emit_styles()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _add_row(self, name: str, style: dict, emit: bool = True) -> None:
        row = AnnotationRow(name, style, self._rows_widget)
        self._btn_group.addButton(row._select_btn)
        row.selected.connect(self.active_name_changed)
        row.style_changed.connect(self._on_style_changed)
        row.name_changed.connect(self._on_name_changed)
        self._rows.append(row)
        self._rows_layout.addWidget(row)
        self._styles[name] = dict(style)
        if len(self._rows) == 1:
            row.set_active(True)
        if emit:
            self._emit_styles()

    def _on_style_changed(self, name: str, style: dict):
        self._styles[name] = style
        self._emit_styles()

    def _on_name_changed(self, old_name: str, new_name: str):
        if old_name in self._styles:
            self._styles[new_name] = self._styles.pop(old_name)
        self._emit_styles()

    def _emit_styles(self):
        self.styles_changed.emit(self.get_styles())
