# plan3.md — Feature Additions, Redesign, and Bug Fixes

This plan covers all requested changes. Items are organised by module. All previously-planned fixes in plan2.md are superseded or incorporated here where they overlap.

---

## Todo list

Tasks are ordered by dependency: data model and I/O first, then widgets, then integration.

### models.py
- [x] Add `AnnotationStyle` TypedDict (`shape`, `color`, `size`, `thickness`)
- [x] Remove `MarkerConfig` TypedDict and `default_marker_config()`
- [x] Replace `marker: MarkerConfig` field in `AppConfig` with `annotation_styles: dict[str, AnnotationStyle]`
- [x] Add `zoom: float` field to `AppConfig`
- [x] Add `metadata_fields: list[str]` field to `AppConfig`
- [x] Remove `notes: str` from `Annotation` TypedDict
- [x] Remove `notes: str` from `AppConfig` TypedDict
- [x] Add `DEFAULT_STYLES` constant dict with styles for Point / Feature / Target
- [x] Update `default_app_config()` to use `annotation_styles`, `zoom`, `metadata_fields`; remove `marker` and `notes`
- [x] Update `make_annotation()` to remove `annotation_icon` parameter; keep `annotation_color` for backwards-compat

### utils/metadata.py (new file)
- [x] Create `utils/metadata.py`
- [x] Define `KNOWN_METADATA_FIELDS` dict mapping field names to EXIF tag names (`photo_timestamp`, `camera_make`, `camera_model`, `gps_latitude`, `gps_longitude`)
- [x] Implement `read_photo_metadata(image_path: Path) -> dict[str, str]` using `PIL.Image` and `PIL.ExifTags`
- [x] Handle GPS rational tuples → decimal degrees conversion
- [x] Return empty dict silently on any EXIF read failure

### tsv_io.py
- [x] Remove `annotation-icon` from `TSV_FIELDNAMES` / `BASE_FIELDNAMES`
- [x] Add `KNOWN_METADATA_FIELDS` import from `utils/metadata.py` (or redefine locally)
- [x] Update `_annotation_to_row()` to drop `annotation-icon`; accept `metadata_fields: list[str]` and write those columns
- [x] Change `save_annotations()` signature to accept `session_config: dict | None`
- [x] In `save_annotations()`: write `# image-annotate-session` comment line first
- [x] In `save_annotations()`: write one `# annotation-style\t<name>\t<shape>\t<color>\t<size>\t<thickness>` line per annotation style
- [x] In `save_annotations()`: write `# zoom\t<value>` line
- [x] In `save_annotations()`: write `# metadata-fields\t<f1>\t<f2>…` line when fields are configured
- [x] In `save_annotations()`: compute `fieldnames = BASE_FIELDNAMES + enabled_metadata_fields`
- [x] Change `load_annotations()` to return `tuple[list[dict], dict]` (rows + session_config)
- [x] In `load_annotations()`: pre-pass to split `#`-prefixed comment lines from data lines
- [x] In `load_annotations()`: parse `# annotation-style` rows into `session_config["annotation_styles"]`
- [x] In `load_annotations()`: parse `# zoom` row into `session_config["zoom"]`
- [x] In `load_annotations()`: parse `# metadata-fields` row into `session_config["metadata_fields"]`
- [x] In `load_annotations()`: pass data lines to `csv.DictReader` via `io.StringIO`
- [x] In `load_annotations()`: parse legacy `annotation-icon` column via `_parse_legacy_color()` helper (backwards-compat)
- [x] Update `append_annotation()` — removed in favour of full `save_annotations()` on every write
- [x] Update all callers of `load_annotations` to unpack the returned tuple

### gui/annotation_list.py (full rewrite)
- [x] Delete `AnnotationNameList(QListWidget)` class
- [x] Create `AnnotationRow(QWidget)` with signals: `selected(str)`, `style_changed(str, dict)`, `name_changed(str, str)`
- [x] In `AnnotationRow.__init__`: add `QRadioButton` for row selection
- [x] In `AnnotationRow.__init__`: add `QLineEdit` for name (editable)
- [x] In `AnnotationRow.__init__`: add `QComboBox` for shape (`X`, `+`, `O`)
- [x] In `AnnotationRow.__init__`: add `QPushButton` color swatch (opens `QColorDialog`)
- [x] In `AnnotationRow.__init__`: add `QSpinBox` for size (range 4–200, tooltip "Size (px)")
- [x] In `AnnotationRow.__init__`: add `QSpinBox` for thickness (range 1–20, tooltip "Thickness")
- [x] Implement `AnnotationRow.get_style() -> dict`
- [x] Implement `AnnotationRow.get_name() -> str`
- [x] Implement `AnnotationRow.set_active(bool)` (sets radio button state)
- [x] Implement `AnnotationRow._pick_color()` (color dialog → update swatch → emit style_changed)
- [x] Implement `AnnotationRow._on_name_changed()` (strip whitespace, emit name_changed if changed)
- [x] Create `AnnotationNameList(QWidget)` container with signals: `active_name_changed(str)`, `styles_changed(dict)`
- [x] In `AnnotationNameList.__init__`: `QButtonGroup(exclusive=True)` for radio buttons
- [x] In `AnnotationNameList.__init__`: scrollable inner area for rows
- [x] In `AnnotationNameList.__init__`: `+` / `−` buttons below scroll area
- [x] Implement `AnnotationNameList.add_name(name, style)` — deduplicates name, calls `_add_row`
- [x] Implement `AnnotationNameList._add_row(name, style)` — creates `AnnotationRow`, wires signals, auto-selects first row
- [x] Implement `AnnotationNameList.remove_selected()` — guard against removing last row; select row[0] after removal
- [x] Implement `AnnotationNameList.get_names() -> list[str]`
- [x] Implement `AnnotationNameList.get_active_name() -> str`
- [x] Implement `AnnotationNameList.get_styles() -> dict[str, dict]`
- [x] Implement `AnnotationNameList.populate_from_config(annotation_styles: dict)` — add/update rows from config dict
- [x] Implement `AnnotationNameList.populate_from_annotations(annotations: list[dict])` — add rows for names not already listed (uses legacy color as fallback style color)
- [x] Implement `AnnotationNameList._on_style_changed(name, style)` — update `_styles` dict, emit `styles_changed`
- [x] Implement `AnnotationNameList._on_name_changed(old, new)` — rename key in `_styles`, emit `styles_changed`

### gui/config_panel.py
- [x] Remove `_build_marker_group()` and its call in `__init__`
- [x] Remove all `_shape_group`, `_color_btn`, `_marker_size`, `_marker_thickness` attributes
- [x] Remove `_build_notes_group()` and its call in `__init__`
- [x] Remove `_notes` attribute
- [x] Rewrite `_build_output_group()` to use a read-only `QLabel` (no `QLineEdit`, no browse button)
- [x] Add `_build_metadata_group()` with a `QCheckBox` per `KNOWN_METADATA_FIELDS` entry
- [x] Wire `annotation_list.styles_changed` → `_on_any_change` in `__init__`
- [x] Wire `annotation_list.active_name_changed` → `_on_any_change` in `__init__`
- [x] Update `_on_any_change()`: read `annotation_styles` from `annotation_list.get_styles()`
- [x] Update `_on_any_change()`: read `active_annotation_name` from `annotation_list.get_active_name()`
- [x] Update `_on_any_change()`: read `metadata_fields` from checked metadata checkboxes
- [x] Update `_on_any_change()`: remove all references to removed fields (`marker`, `notes`, output path)
- [x] Remove `_pick_color()`, `_update_color_btn()`, `_browse_output()` methods
- [x] Remove `QButtonGroup`, `QPlainTextEdit`, and `QFileDialog` imports if no longer used
- [x] Add `populate_annotation_styles(styles: dict)` method that calls `annotation_list.populate_from_config()`

### gui/image_canvas.py
- [x] In `load_image()`: remove `self.setTransform(QTransform())` line (zoom reset)
- [x] In `load_image()`: update `_scale_info` using current `self.transform().m11()` instead of assuming 1.0
- [x] In `_draw_annotation()`: resolve `shape`, `color`, `size`, `thickness` from `self._config["annotation_styles"][ann["annotation_name"]]` with fallback to `ann.get("annotation_color")`
- [x] In `_draw_annotation()`: remove read of `ann["annotation_icon"]`
- [x] In `_handle_left_click()`: look up active name's style from `self._config["annotation_styles"]` for color
- [x] In `_handle_left_click()`: remove `annotation_icon` argument from `make_annotation()` call
- [x] In `_handle_right_click()`: update hit-test tolerance to use `annotation_styles` size instead of global `marker.size`

### gui/file_tree.py
- [x] Replace `self._tree.activated.connect(self._on_item_activated)` with `self._tree.clicked.connect(self._on_item_activated)`
- [x] Optionally also keep `activated` connection for keyboard Enter-key navigation

### gui/main_window.py
- [x] Update `load_annotations` call in `__init__` to unpack `(annotations, session_config)` tuple
- [x] Merge `session_config["annotation_styles"]` into app config at startup (TSV comments → defaults)
- [x] Merge `session_config["zoom"]` into app config at startup
- [x] Merge `session_config["metadata_fields"]` into app config at startup
- [x] Add `self._zoom_level: float` instance variable, initialised from `config.get("zoom", 1.0)`
- [x] Call `self._config_panel.populate_annotation_styles(config["annotation_styles"])` after creating config panel
- [x] In `_on_image_selected()`: call `self._canvas.zoom_to(self._zoom_level)` after `load_image()`
- [x] In `_on_image_selected()`: unpack `(annotations, _)` from `load_annotations()` call
- [x] In `_on_image_selected()`: fix path match: `(images_dir / a["image_file"]).resolve() == path.resolve()`
- [x] In `_on_zoom_changed()`: store `factor` in `self._zoom_level` and `self._config["zoom"]`
- [x] In `_on_annotation_added()`: call `read_photo_metadata()` on current image; attach enabled fields to `ann` dict
- [x] In `_on_annotation_added()`: replace `append_annotation()` call with `save_annotations(..., session_config=self._config)` (to keep comment header fresh)
- [x] In `_on_annotation_removed()`: update `save_annotations()` call to pass `session_config=self._config`
- [x] Replace `_undo()` with current-image-scoped implementation: scan `self._annotations` in reverse for matching `image_file`; remove that entry; call `save_annotations` with `session_config`
- [x] Remove `_undo_stack` attribute (no longer needed)
- [x] Update `_on_config_changed()` to sync `self._zoom_level` from config

### Integration / cross-cutting
- [x] Verify `renderer.py` (`render_annotations_onto_image`) still works without `annotation_icon` — update to resolve shape from a passed-in styles dict or derive from annotation name
- [x] Update `generate-images` CLI command to load annotation styles from TSV session config and pass to renderer
- [x] Audit all remaining references to `ann["annotation_icon"]`, `ann["notes"]`, `config["marker"]`, `config["notes"]` and remove or migrate
- [x] Add `piexif` or confirm `Pillow` EXIF support is sufficient (no new dependency needed if using `img._getexif()`)
- [ ] Manual smoke test: launch with no args → opens UI with defaults
- [ ] Manual smoke test: open TSV with existing annotations → annotations appear on image at correct positions
- [ ] Manual smoke test: add annotation → TSV written with comment header + no `annotation-icon` column
- [ ] Manual smoke test: re-open app → zoom, styles, metadata field prefs restored from TSV comments
- [ ] Manual smoke test: Ctrl+Z → removes last annotation for current image only; other images unchanged
- [ ] Manual smoke test: single-click image in file tree → image loads
- [ ] Manual smoke test: switch image → zoom level unchanged

---

## Overview of changes

| Area | Change type |
|------|-------------|
| `cli.py` | Default to `ui` when no subcommand; keep `[command] [args]` form |
| `models.py` | Replace global `MarkerConfig` with per-name `AnnotationStyle`; remove `notes` |
| `tsv_io.py` | Remove `annotation-icon` column; add metadata columns; write/read comment header |
| `annotation_list.py` | Full redesign: table-style rows with inline shape/color/size/thickness selectors |
| `config_panel.py` | Remove Marker group; remove Notes group; read-only Output; add Metadata Fields group |
| `image_canvas.py` | Resolve annotation styles from config instead of stored icon; zoom persistence |
| `main_window.py` | Zoom persistence; Ctrl+Z scoped to current image; pass styles into canvas |
| `file_tree.py` | Single-click activation |

---

## 1. `cli.py` — Default to `ui`; `[command] [args]` form

### Design choice

Use `invoke_without_command=True` on the group. If no subcommand is supplied, `cli` callback calls `ctx.invoke(launch_ui)` using `launch_ui`'s own defaults. This keeps option parsing on each subcommand (already the case from plan2.md) and avoids duplicating option declarations.

```python
@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Image annotation tool.  Defaults to 'ui' when no command is given."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(launch_ui)


def _common_options(f):
    f = click.option(
        "--annotations", "annotations_path",
        default="annotations.tsv", type=click.Path(), show_default=True,
        help="TSV file for annotations.",
    )(f)
    f = click.option(
        "--images", "images_dir",
        default=".", type=click.Path(exists=True, file_okay=False), show_default=True,
        help="Folder to load in file tree.",
    )(f)
    f = click.option("-v", "--verbose", is_flag=True, default=False,
                     help="Enable DEBUG logging.")(f)
    return f


@cli.command("ui")
@_common_options
def launch_ui(annotations_path, images_dir, verbose):
    """Launch the graphical annotation interface."""
    _setup_logging(verbose)
    from .app import launch_gui
    launch_gui(images_dir=Path(images_dir), annotations_file=Path(annotations_path))


@cli.command("generate-images")
@_common_options
@click.option("--format", "filename_template", ...)
def generate_images(annotations_path, images_dir, verbose, filename_template):
    ...
```

**Valid invocations:**
```
image-annotate                                   # → ui with defaults
image-annotate ui                                # → ui with defaults
image-annotate ui --images ./photos              # → ui, custom images dir
image-annotate ui --images ./ --annotations a.tsv
image-annotate generate-images --images ./photos --annotations a.tsv
```

---

## 2. `models.py` — Per-name annotation styles, remove notes

### Design choice

Replace the single global `MarkerConfig` with a dict of `AnnotationStyle` keyed by annotation name. Each name has its own shape, color, size, and thickness. The global `marker` config is removed entirely. `notes` field removed from `Annotation` and `AppConfig`.

```python
class AnnotationStyle(TypedDict):
    shape: str      # "X" | "+" | "O"
    color: str      # hex e.g. "#FF0000"
    size: int       # px, 4–200
    thickness: int  # px, 1–20


class AppConfig(TypedDict):
    images_dir: str
    annotations_file: str
    annotation_styles: dict[str, AnnotationStyle]   # replaces `marker`
    magnifier: MagnifierConfig
    show_labels: bool
    show_coordinates: bool
    active_annotation_name: str
    zoom: float                                      # persisted zoom level
    metadata_fields: list[str]                       # e.g. ["photo_timestamp"]


class Annotation(TypedDict):
    id: str
    image_file: str
    annotation_name: str
    # annotation_icon removed — shape derived from annotation_styles at render time
    annotation_color: str   # kept for backwards-compat loading of old TSVs
    location_x: float
    location_y: float
    image_width: int
    image_height: int
    # notes removed


DEFAULT_ANNOTATION_NAMES = ["Point", "Feature", "Target"]

DEFAULT_STYLES: dict[str, AnnotationStyle] = {
    "Point":   {"shape": "X", "color": "#FF0000", "size": 12, "thickness": 2},
    "Feature": {"shape": "+", "color": "#00FF00", "size": 14, "thickness": 2},
    "Target":  {"shape": "O", "color": "#0000FF", "size": 16, "thickness": 3},
}


def default_app_config(images_dir=".", annotations_file="annotations.tsv") -> dict:
    return {
        "images_dir": images_dir,
        "annotations_file": annotations_file,
        "annotation_styles": dict(DEFAULT_STYLES),
        "magnifier": default_magnifier_config(),
        "show_labels": True,
        "show_coordinates": False,
        "active_annotation_name": "Point",
        "zoom": 1.0,
        "metadata_fields": ["photo_timestamp"],
    }
```

`make_annotation` no longer takes `annotation_icon` or `annotation_color` parameters; those fields are looked up from config at render time. The dict still stores `annotation_color` for backwards-compatibility when loading old TSVs.

---

## 3. `tsv_io.py` — Comment header, removed `annotation-icon`, metadata fields

### TSV format

The file starts with `#`-prefixed comment rows that encode session config, followed by the column header row, then data rows. `csv.DictReader` skips rows it cannot parse as field data when using a manual header, so comment rows must be stripped before passing to the reader.

**Example output:**
```
# image-annotate-session
# annotation-style	Point	X	#FF0000	12	2
# annotation-style	Feature	+	#00FF00	14	2
# annotation-style	Target	O	#0000FF	16	3
# zoom	1.50
# metadata-fields	photo_timestamp
image-file	annotation-name	locationX(px)	locationY(px)	imageX(total width px)	imageY(total height px)	photo_timestamp
img/photo1.jpg	Point	320.0000	240.0000	1920	1080	2024-06-15T14:23:01
```

### TSV fields (new)

```python
BASE_FIELDNAMES = [
    "image-file",
    "annotation-name",
    "locationX(px)",
    "locationY(px)",
    "imageX(total width px)",
    "imageY(total height px)",
]

KNOWN_METADATA_FIELDS = {
    "photo_timestamp": "DateTimeOriginal",   # EXIF tag name → column name
    "camera_make":     "Make",
    "camera_model":    "Model",
    "gps_latitude":    "GPSLatitude",
    "gps_longitude":   "GPSLongitude",
}
```

### `save_annotations` — writes comments then data

```python
def save_annotations(
    annotations: list[dict],
    tsv_path: Path,
    session_config: dict | None = None,
) -> None:
    """Write TSV with leading comment rows for session config."""
    tmp = tsv_path.with_suffix(".tsv.tmp")
    tsv_path.parent.mkdir(parents=True, exist_ok=True)

    metadata_fields = (session_config or {}).get("metadata_fields", [])
    fieldnames = BASE_FIELDNAMES + [f for f in metadata_fields if f in KNOWN_METADATA_FIELDS]

    with tmp.open("w", newline="", encoding="utf-8") as fh:
        # --- comment header ---
        fh.write("# image-annotate-session\n")
        if session_config:
            for name, style in session_config.get("annotation_styles", {}).items():
                fh.write(
                    f"# annotation-style\t{name}\t{style['shape']}\t"
                    f"{style['color']}\t{style['size']}\t{style['thickness']}\n"
                )
            zoom = session_config.get("zoom", 1.0)
            fh.write(f"# zoom\t{zoom:.4f}\n")
            if metadata_fields:
                fh.write(f"# metadata-fields\t{chr(9).join(metadata_fields)}\n")

        # --- data ---
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        for ann in annotations:
            writer.writerow(_annotation_to_row(ann, metadata_fields))

    tmp.replace(tsv_path)
```

### `load_annotations` — parses comment header + data

```python
def load_annotations(tsv_path: Path) -> tuple[list[dict], dict]:
    """
    Returns (annotations, session_config).
    session_config contains annotation_styles, zoom, metadata_fields if present.
    """
    if not tsv_path.exists():
        return [], {}

    comment_lines: list[str] = []
    data_lines: list[str] = []

    with tsv_path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#"):
                comment_lines.append(line.rstrip("\n"))
            else:
                data_lines.append(line)

    # Parse comment rows
    session_config: dict = {}
    annotation_styles: dict = {}
    metadata_fields: list[str] = []

    for line in comment_lines:
        parts = line.lstrip("# ").split("\t")
        if not parts:
            continue
        key = parts[0]
        if key == "annotation-style" and len(parts) >= 6:
            # annotation-style  name  shape  color  size  thickness
            _, name, shape, color, size, thickness = parts[:6]
            annotation_styles[name] = {
                "shape": shape,
                "color": color,
                "size": int(size),
                "thickness": int(thickness),
            }
        elif key == "zoom" and len(parts) >= 2:
            try:
                session_config["zoom"] = float(parts[1])
            except ValueError:
                pass
        elif key == "metadata-fields" and len(parts) >= 2:
            metadata_fields = parts[1:]
            session_config["metadata_fields"] = metadata_fields

    if annotation_styles:
        session_config["annotation_styles"] = annotation_styles

    # Parse data rows
    rows: list[dict] = []
    if data_lines:
        import io
        reader = csv.DictReader(io.StringIO("".join(data_lines)), delimiter="\t")
        for row in reader:
            try:
                rows.append({
                    "id": str(uuid.uuid4()),
                    "image_file": row["image-file"],
                    "annotation_name": row["annotation-name"],
                    # Legacy: parse annotation-icon if present
                    "annotation_color": _parse_legacy_color(row),
                    "location_x": float(row["locationX(px)"]),
                    "location_y": float(row["locationY(px)"]),
                    "image_width": int(row["imageX(total width px)"]),
                    "image_height": int(row["imageY(total height px)"]),
                    **{f: row.get(f, "") for f in metadata_fields},
                })
            except (KeyError, ValueError):
                continue

    return rows, session_config


def _parse_legacy_color(row: dict) -> str:
    """Extract color from old 'annotation-icon' field if present."""
    icon_raw = row.get("annotation-icon", "")
    if ":" in icon_raw:
        _, color = icon_raw.split(":", 1)
        return color
    return "#FF0000"
```

### `_annotation_to_row` — no annotation-icon

```python
def _annotation_to_row(ann: dict, metadata_fields: list[str]) -> dict:
    row = {
        "image-file": ann["image_file"],
        "annotation-name": ann["annotation_name"],
        "locationX(px)": f"{ann['location_x']:.4f}",
        "locationY(px)": f"{ann['location_y']:.4f}",
        "imageX(total width px)": ann["image_width"],
        "imageY(total height px)": ann["image_height"],
    }
    for field in metadata_fields:
        row[field] = ann.get(field, "")
    return row
```

### Photo metadata extraction

New utility function in `utils/metadata.py`:

```python
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS


def read_photo_metadata(image_path: Path) -> dict[str, str]:
    """Return a flat dict of known EXIF fields as strings."""
    result: dict[str, str] = {}
    try:
        with Image.open(image_path) as img:
            exif_data = img._getexif()  # returns None for non-JPEG
            if not exif_data:
                return result
            tag_lookup = {v: k for k, v in TAGS.items()}
            for field_name, exif_tag_name in KNOWN_METADATA_FIELDS.items():
                tag_id = tag_lookup.get(exif_tag_name)
                if tag_id and tag_id in exif_data:
                    val = exif_data[tag_id]
                    result[field_name] = str(val)
    except Exception:
        pass
    return result
```

`KNOWN_METADATA_FIELDS` is imported from `tsv_io`. GPS data requires additional decoding (degrees/minutes/seconds tuple → decimal) but that is a detail for implementation.

---

## 4. `annotation_list.py` — Full redesign as per-name style table

### Design choice

Replace `QListWidget` with a custom `QWidget` containing a `QScrollArea` with a `QVBoxLayout` of `AnnotationRow` sub-widgets. Each row has:

- `QLineEdit` for the name (editable, double-click-to-edit preserved)
- `QComboBox` for shape (X / + / O)
- `QPushButton` as color swatch (opens `QColorDialog`)
- `QSpinBox` for size (4–200)
- `QSpinBox` for thickness (1–20)
- Radio-button-style selection indicator (clicking row selects it as the active name)

```
┌─────────────────────────────────────────────────────────┐
│ ● [Point  ] [X▼] [■ ] [12↕] [2↕]                       │
│ ○ [Feature] [+▼] [■ ] [14↕] [2↕]                       │
│ ○ [Target ] [O▼] [■ ] [16↕] [3↕]                       │
│ [+]  [−]                                                 │
└─────────────────────────────────────────────────────────┘
```

### `AnnotationRow` widget

```python
class AnnotationRow(QWidget):
    selected = Signal(str)          # annotation name
    style_changed = Signal(str, dict)  # (name, new_style)
    name_changed = Signal(str, str)    # (old_name, new_name)

    def __init__(self, name: str, style: dict, parent=None):
        super().__init__(parent)
        self._name = name
        self._color = style.get("color", "#FF0000")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(4)

        self._select_btn = QRadioButton()
        self._select_btn.toggled.connect(lambda checked: self.selected.emit(self._name) if checked else None)
        layout.addWidget(self._select_btn)

        self._name_edit = QLineEdit(name)
        self._name_edit.setMinimumWidth(70)
        self._name_edit.editingFinished.connect(self._on_name_changed)
        layout.addWidget(self._name_edit)

        self._shape_combo = QComboBox()
        self._shape_combo.addItems(["X", "+", "O"])
        self._shape_combo.setCurrentText(style.get("shape", "X"))
        self._shape_combo.setFixedWidth(40)
        self._shape_combo.currentTextChanged.connect(self._emit_style)
        layout.addWidget(self._shape_combo)

        self._color_btn = QPushButton()
        self._color_btn.setFixedWidth(28)
        self._set_color(self._color)
        self._color_btn.clicked.connect(self._pick_color)
        layout.addWidget(self._color_btn)

        self._size_spin = QSpinBox()
        self._size_spin.setRange(4, 200)
        self._size_spin.setValue(style.get("size", 12))
        self._size_spin.setFixedWidth(48)
        self._size_spin.setToolTip("Size (px)")
        self._size_spin.valueChanged.connect(self._emit_style)
        layout.addWidget(self._size_spin)

        self._thick_spin = QSpinBox()
        self._thick_spin.setRange(1, 20)
        self._thick_spin.setValue(style.get("thickness", 2))
        self._thick_spin.setFixedWidth(38)
        self._thick_spin.setToolTip("Thickness")
        self._thick_spin.valueChanged.connect(self._emit_style)
        layout.addWidget(self._thick_spin)

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self._color), self, "Pick color")
        if color.isValid():
            self._color = color.name()
            self._set_color(self._color)
            self._emit_style()

    def _set_color(self, hex_color: str):
        self._color_btn.setStyleSheet(
            f"background-color: {hex_color}; border: 1px solid #888;"
        )

    def _emit_style(self, *_):
        self.style_changed.emit(self._name, self.get_style())

    def _on_name_changed(self):
        new_name = self._name_edit.text().strip() or self._name
        if new_name != self._name:
            old = self._name
            self._name = new_name
            self.name_changed.emit(old, new_name)

    def get_style(self) -> dict:
        return {
            "shape": self._shape_combo.currentText(),
            "color": self._color,
            "size": self._size_spin.value(),
            "thickness": self._thick_spin.value(),
        }

    def get_name(self) -> str:
        return self._name

    def set_active(self, active: bool):
        self._select_btn.setChecked(active)
```

### `AnnotationNameList` (container)

```python
class AnnotationNameList(QWidget):
    active_name_changed = Signal(str)
    styles_changed = Signal(dict)   # full styles dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[AnnotationRow] = []
        self._styles: dict[str, dict] = {}

        self._row_group = QButtonGroup(self)  # exclusive radio buttons
        self._row_group.setExclusive(True)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setSpacing(2)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)

        scroll_inner = QWidget()
        scroll_inner.setLayout(self._rows_layout)
        scroll = QScrollArea()
        scroll.setWidget(scroll_inner)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(30)
        add_btn.clicked.connect(self.add_name)
        remove_btn = QPushButton("−")
        remove_btn.setFixedWidth(30)
        remove_btn.clicked.connect(self.remove_selected)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        outer.addLayout(btn_layout)

    def add_name(self, name: str = "New annotation", style: dict | None = None) -> None:
        # Ensure unique name
        existing = self.get_names()
        base = name
        n = 1
        while name in existing:
            name = f"{base} {n}"
            n += 1
        style = style or {"shape": "X", "color": "#FF0000", "size": 12, "thickness": 2}
        self._add_row(name, style)
        self._emit_styles()

    def _add_row(self, name: str, style: dict) -> None:
        row = AnnotationRow(name, style, self)
        self._row_group.addButton(row._select_btn)
        row.selected.connect(self.active_name_changed)
        row.style_changed.connect(self._on_style_changed)
        row.name_changed.connect(self._on_name_changed)
        self._rows.append(row)
        self._rows_layout.addWidget(row)
        self._styles[name] = style
        # Select first row automatically
        if len(self._rows) == 1:
            row.set_active(True)

    def remove_selected(self):
        if len(self._rows) <= 1:
            return
        for row in self._rows:
            if row._select_btn.isChecked():
                self._rows.remove(row)
                self._styles.pop(row.get_name(), None)
                row.deleteLater()
                if self._rows:
                    self._rows[0].set_active(True)
                self._emit_styles()
                return

    def get_names(self) -> list[str]:
        return [r.get_name() for r in self._rows]

    def get_active_name(self) -> str:
        for row in self._rows:
            if row._select_btn.isChecked():
                return row.get_name()
        return self._rows[0].get_name() if self._rows else "Point"

    def get_styles(self) -> dict[str, dict]:
        return dict(self._styles)

    def populate_from_config(self, annotation_styles: dict[str, dict]) -> None:
        """Load styles from config dict, adding new names, updating existing."""
        existing = {r.get_name(): r for r in self._rows}
        for name, style in annotation_styles.items():
            if name not in existing:
                self._add_row(name, style)
            # Existing rows keep their current values unless styles differ —
            # for simplicity during load, overwrite with config values
        self._styles = dict(annotation_styles)
        self._emit_styles()

    def populate_from_annotations(self, annotations: list[dict]) -> None:
        """Add any annotation names seen in TSV rows that aren't already listed."""
        existing = set(self.get_names())
        for ann in annotations:
            name = ann["annotation_name"]
            if name not in existing:
                style = {"shape": "X", "color": ann.get("annotation_color", "#FF0000"),
                         "size": 12, "thickness": 2}
                self._add_row(name, style)
                existing.add(name)
        self._emit_styles()

    def _on_style_changed(self, name: str, style: dict):
        self._styles[name] = style
        self._emit_styles()

    def _on_name_changed(self, old_name: str, new_name: str):
        if old_name in self._styles:
            self._styles[new_name] = self._styles.pop(old_name)
        self._emit_styles()

    def _emit_styles(self):
        self.styles_changed.emit(dict(self._styles))
```

---

## 5. `config_panel.py` — Remove Marker/Notes groups; read-only Output; Metadata section

### Groups after redesign

1. **File Tree** (unchanged)
2. **Annotations** — redesigned (calls `AnnotationNameList` which now includes per-name style selectors)
3. **Magnifier** (unchanged)
4. **Metadata Fields** — new: checkboxes for which EXIF fields to include in TSV
5. **Output** — read-only label showing `--annotations` path
6. **Display** (unchanged)

Removed: **Marker** group, **Notes** group.

### `_build_output_group` — read-only

```python
def _build_output_group(self, config: dict) -> QGroupBox:
    group = QGroupBox("Output file")
    layout = QVBoxLayout(group)
    lbl = QLabel(config.get("annotations_file", "annotations.tsv"))
    lbl.setWordWrap(True)
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(lbl)
    return group
```

No browse button; no signal; value never changes.

### `_build_metadata_group` — new

```python
METADATA_LABELS = {
    "photo_timestamp": "Photo timestamp",
    "camera_make":     "Camera make",
    "camera_model":    "Camera model",
    "gps_latitude":    "GPS latitude",
    "gps_longitude":   "GPS longitude",
}

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
```

### `_on_any_change` — rebuilds config

```python
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
        "show_labels": self._show_labels.isChecked(),
        "show_coordinates": self._show_coords.isChecked(),
        "active_annotation_name": self.annotation_list.get_active_name(),
        "metadata_fields": [f for f, cb in self._metadata_checks.items() if cb.isChecked()],
        "zoom": self._config.get("zoom", 1.0),
    }
    self._config = config
    self.config_changed.emit(config)
```

Note: `annotation_list.styles_changed` is connected to `_on_any_change` rather than having `_on_any_change` read from `annotation_list` directly, to ensure styles are always up-to-date.

---

## 6. `image_canvas.py` — Style from config; zoom persistence

### `_draw_annotation` — resolve style from config

```python
def _draw_annotation(self, ann: dict):
    styles = self._config.get("annotation_styles", {})
    name = ann["annotation_name"]
    style = styles.get(name, {})

    color = style.get("color") or ann.get("annotation_color", "#FF0000")
    shape = style.get("shape", "X")
    size  = style.get("size", 12)
    thick = style.get("thickness", 2)

    items = _draw_marker_on_scene(
        self._scene,
        ann["location_x"], ann["location_y"],
        shape=shape, color=color, size=size, thickness=thick,
    )
    ...
```

No longer reads `ann["annotation_icon"]` at all (removed from data model).

### `_handle_left_click` — get shape from config style

```python
def _handle_left_click(self, scene_pos: QPointF):
    active_name = self._config.get("active_annotation_name", "Point")
    styles = self._config.get("annotation_styles", {})
    style = styles.get(active_name, {})
    color = style.get("color", "#FF0000")
    # shape stored in config; icon no longer stored per-annotation in TSV
    ...
    ann = make_annotation(
        image_file=image_file,
        annotation_name=active_name,
        location_x=img_x,
        location_y=img_y,
        image_width=self._original_size[0],
        image_height=self._original_size[1],
        annotation_color=color,  # kept in memory dict; not written to TSV
        metadata=self._pending_metadata,   # filled by MainWindow before click
    )
    ...
```

### `load_image` — do NOT reset zoom

```python
def load_image(self, path: Path) -> None:
    self._current_image_path = path
    pixmap = QPixmap(str(path))
    self._original_size = (pixmap.width(), pixmap.height())

    self._scene.clear()
    self._annotation_items.clear()
    self._crosshair_items.clear()
    self._annotations.clear()

    self._pixmap_item = self._scene.addPixmap(pixmap)
    self._pixmap_item.setPos(0, 0)
    self._scene.setSceneRect(self._pixmap_item.boundingRect())
    # NOTE: do NOT call setTransform(QTransform()) here
    # Zoom is applied by MainWindow after load_image returns
    self._scale_info = ScaleInfo(
        scale_factor=self.transform().m11(),
        original_width=pixmap.width(),
        original_height=pixmap.height(),
    )
    self._init_crosshair()
    self._rebuild_annotation_graphics()
```

`MainWindow._on_image_selected` calls `canvas.zoom_to(self._zoom_level)` after `load_image`. On first load `_zoom_level = 1.0`, giving 100%.

---

## 7. `main_window.py` — Zoom persistence; Ctrl+Z scoped; metadata enrichment; TSV session header

### Zoom persistence

```python
class MainWindow(QMainWindow):
    def __init__(self, config: dict):
        ...
        self._zoom_level: float = config.get("zoom", 1.0)
        ...

    @Slot(Path)
    def _on_image_selected(self, path: Path):
        self._current_image_path = path
        try:
            self._canvas.load_image(path)
        except Exception as e:
            QMessageBox.warning(self, "Image error", str(e))
            return

        # Apply stored zoom (not reset to 1.0)
        self._canvas.zoom_to(self._zoom_level)

        # Reload annotations from TSV
        try:
            self._annotations, _ = load_annotations(Path(self._config["annotations_file"]))
        except Exception:
            pass

        images_dir = Path(self._config.get("images_dir", "."))
        img_anns = [
            a for a in self._annotations
            if (images_dir / a["image_file"]).resolve() == path.resolve()
        ]
        self._canvas.set_annotations(img_anns)
        self._canvas.set_config(self._config)
        self._config_panel.annotation_list.populate_from_annotations(img_anns)

        n = len(img_anns)
        pct = int(self._zoom_level * 100)
        self._status.showMessage(f"{path.name}  —  {n} annotation(s)  |  zoom {pct}%")

    @Slot(float)
    def _on_zoom_changed(self, factor: float):
        self._zoom_level = factor          # persist across image switches
        self._config["zoom"] = factor
        pct = int(factor * 100)
        name = self._current_image_path.name if self._current_image_path else ""
        self._status.showMessage(f"{name}  |  zoom {pct}%")
```

### Metadata enrichment on annotation add

When an annotation is added, read EXIF metadata from the current image and attach to the annotation dict (in memory only — written to TSV via the metadata columns).

```python
@Slot(dict)
def _on_annotation_added(self, ann: dict):
    # Attach metadata to annotation dict
    if self._current_image_path:
        from ..utils.metadata import read_photo_metadata
        meta = read_photo_metadata(self._current_image_path)
        metadata_fields = self._config.get("metadata_fields", [])
        for field in metadata_fields:
            ann[field] = meta.get(field, "")

    self._annotations.append(ann)
    try:
        save_annotations(
            self._annotations,
            Path(self._config["annotations_file"]),
            session_config=self._config,
        )
    except Exception as e:
        QMessageBox.warning(self, "Save error", str(e))
    ...
```

### Ctrl+Z — scoped to current image

Replace the stack-based undo with a targeted "remove last for this image" operation.

```python
def _undo(self):
    if not self._current_image_path:
        self._status.showMessage("No image selected.")
        return

    images_dir = Path(self._config.get("images_dir", "."))
    try:
        rel = str(self._current_image_path.relative_to(images_dir))
    except ValueError:
        rel = str(self._current_image_path)

    # Find the last annotation in self._annotations that matches the current image
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
        QMessageBox.warning(self, "Save error", str(e))

    self._status.showMessage(f"Undid: '{last_ann['annotation_name']}'")
```

Key properties:
- Scans `self._annotations` in reverse to find the last entry for the current image.
- `self._annotations` is ordered by insertion (append-only), so reversing finds the most-recently-added entry for this image.
- Annotations for other images are untouched — the full list minus this one entry is saved.
- TSV is rewritten atomically via `tmp.replace(tsv_path)`.

### Session config round-trip at startup

```python
def __init__(self, config: dict):
    ...
    loaded_anns, session_config = load_annotations(Path(config["annotations_file"]))
    self._annotations = loaded_anns

    # Merge session config from TSV comments into app config
    # (TSV values override defaults but CLI args take highest priority)
    if "annotation_styles" in session_config:
        config.setdefault("annotation_styles", session_config["annotation_styles"])
    if "zoom" in session_config:
        config.setdefault("zoom", session_config["zoom"])
    if "metadata_fields" in session_config:
        config.setdefault("metadata_fields", session_config["metadata_fields"])

    self._zoom_level = config.get("zoom", 1.0)
    ...
```

### `_on_config_changed` — propagate styles to canvas

```python
@Slot(dict)
def _on_config_changed(self, config: dict):
    self._config = config
    self._canvas.set_config(config)
    # Also keep zoom in sync
    self._zoom_level = config.get("zoom", self._zoom_level)
```

---

## 8. `file_tree.py` — Single-click activation

### Root cause

`QTreeView.activated` fires on double-click (or Enter key) by default on most platforms. To get single-click, connect `clicked` instead.

```python
# Before
self._tree.activated.connect(self._on_item_activated)

# After
self._tree.clicked.connect(self._on_item_activated)
```

`clicked` passes a `QModelIndex` just like `activated`, so `_on_item_activated` needs no changes. The directory expand/collapse on single-click still works via the tree's built-in expand logic (unrelated to our signal).

If keyboard navigation (Enter to open) is also desired, keep both connections:
```python
self._tree.clicked.connect(self._on_item_activated)
self._tree.activated.connect(self._on_item_activated)  # Enter key
```

---

## 9. Bug fix: annotations from TSV not shown

Already covered in plan2.md; reproduced here for completeness.

### Root cause

`Path(a["image_file"]).resolve()` resolves relative to cwd, not `images_dir`.

### Fix (in `_on_image_selected`)

```python
images_dir = Path(self._config.get("images_dir", "."))
img_anns = [
    a for a in self._annotations
    if (images_dir / a["image_file"]).resolve() == path.resolve()
]
```

This is already included in the `_on_image_selected` rewrite above.

---

## 10. Bug fix: config panel too wide at startup

Already covered in plan2.md; already applied in codebase (`splitter.setSizes([1140, 260])`). No additional change needed.

---

## Summary of files to change

| File | Changes |
|------|---------|
| `cli.py` | Add `invoke_without_command=True`; invoke `launch_ui` when no subcommand |
| `models.py` | Add `AnnotationStyle`; replace `MarkerConfig`/`marker` with `annotation_styles`; remove `notes` |
| `tsv_io.py` | New TSV schema (no `annotation-icon`); comment header read/write; metadata columns; `load_annotations` returns `(rows, session_config)` |
| `utils/metadata.py` | New file: EXIF metadata reader using Pillow |
| `gui/annotation_list.py` | Full rewrite: `AnnotationRow` + `AnnotationNameList` with inline style selectors |
| `gui/config_panel.py` | Remove Marker group; remove Notes group; read-only Output; add Metadata Fields group; update `_on_any_change` |
| `gui/image_canvas.py` | `_draw_annotation` resolves style from config; `load_image` does not reset zoom; `_handle_left_click` uses per-name style |
| `gui/main_window.py` | Zoom persistence; `_undo` scoped to current image; EXIF enrichment on add; session config merge at startup |
| `gui/file_tree.py` | Connect `clicked` instead of (or in addition to) `activated` |

---

## Design decisions log

| Decision | Rationale |
|----------|-----------|
| Per-name styles in config (not per-annotation in TSV) | Keeps TSV clean; changing a style retroactively updates all markers of that name; aligns with the stated desire to remove the `annotation-icon` column |
| TSV comment rows use `#` prefix | Standard convention; `csv.DictReader` will error on these so they must be stripped before parsing — explicit pre-pass is cleaner than overriding the reader |
| Zoom not reset on image switch | User explicitly requested this; state held in `MainWindow._zoom_level` and synced to config |
| Ctrl+Z scoped to current image by scanning reversed list | Simpler than a per-image undo stack; matches stated requirement exactly; preserves order of other images' annotations |
| Single click via `clicked` signal | `activated` is platform-dependent (double-click on macOS/Windows); `clicked` is always single-click |
| `load_annotations` returns `(rows, session_config)` tuple | Clean separation; callers that don't need session config can unpack with `_, _` or ignore second element |
| `save_annotations` always writes comment header | Idempotent; ensures config is preserved even when annotations are added one-by-one |
| Metadata read at annotation-add time (not at load time) | Avoids scanning all images at startup; metadata is attached in `_on_annotation_added` |
