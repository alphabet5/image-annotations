# image-annotate: Codebase Research

## Overview

**image-annotate** is a point-based image annotation tool built with Python 3.11+ and PySide6. It lets users place named, styled point markers on images and stores them in a portable TSV file. There are two modes:

- **GUI** (`image-annotate ui`): Interactive desktop app for placing markers
- **CLI** (`image-annotate generate-images`): Batch renderer that draws markers onto image copies

Supported formats: PNG, JPG, JPEG, TIFF, BMP, GIF, WebP, HEIC/HEIF.

---

## Architecture

The app follows a **Model-View-Mediator** pattern:

```
CLI (click) → Config Dict → TSV I/O ↔ File System
                    ↓
            MainWindow (controller)
                    ↓
         ┌──────────┴──────────┐
         ↓                     ↓
  AnnotationCanvas     ConfigPanel
  (QGraphicsView)      (QWidget)
         ↓
  QGraphicsScene
  ├─ QGraphicsPixmapItem (image)
  ├─ QGraphicsItems (markers + labels)
  └─ MagnifierOverlay (child widget)
```

**Master state** lives in `MainWindow`:
- `self._annotations` — the live list of annotation dicts
- `self._config` — the current AppConfig dict (styles, zoom, display, magnifier, metadata)

Both `AnnotationCanvas` and `ConfigPanel` are views — they don't hold independent state.

---

## Module Reference

### `__init__.py`
Registers `pillow-heif` at import time so all `PIL.Image.open()` calls transparently support HEIC.

### `cli.py`
Click-based CLI with two commands sharing `--images` and `--annotations` options:

- `ui` — launches `launch_gui(images_dir, annotations_file)`
- `generate-images` — loads TSV, groups by image, renders each via `renderer.py`; accepts `--format` for Jinja2 output path templates

Default invocation (no subcommand) launches `ui`.

### `models.py`
TypedDicts for type hints only (never instantiated at runtime):
- `AnnotationStyle`: shape (`X`/`+`/`O`), color (hex), size (px), thickness (px)
- `MagnifierConfig`: enabled, size, zoom_factor, offset_x/y, upscale
- `Annotation`: id (UUID), image_file, annotation_name, location_x/y, image_width/height, + optional metadata fields
- `AppConfig`: styles dict, magnifier, zoom, display, metadata_fields, images_dir, annotations_file

Factory: `make_annotation()` — creates an annotation dict with a fresh UUID.

Defaults:
- `DEFAULT_STYLES`: Point (red X), Feature (green +), Target (blue O)
- `default_magnifier_config()`: 150px, 4× zoom, 20px offset
- `default_app_config()`: all defaults, optional path overrides

### `tsv_io.py`
Persistence layer. The TSV file has two sections:

**Header comments:**
```
# image-annotate-session
# annotation-style <name> <shape> <color> <size> <thickness>
# zoom <value>
# display show_labels=<0|1> show_coordinates=<0|1>
# metadata-fields <field1> <field2> ...
```

**Data rows:** `image-file`, `annotation-name`, `locationX(px)`, `locationY(px)`, `imageX(total width px)`, `imageY(total height px)`, [optional metadata columns]

Key behaviors:
- `load_annotations()` returns `(annotations[], session_config{})` — session config restores styles/zoom/display on reopen
- `save_annotations()` uses atomic write (`.tmp` + rename) and auto-creates parent dirs
- Image paths stored **relative to `images_dir`** for portability
- Malformed rows skipped gracefully; missing `id` fields get a generated UUID

### `renderer.py`
Headless Pillow renderer for `generate-images`. Draws markers (X, +, O shapes) with configurable color/size/thickness and optional labels/coordinates. Automatically redirects `.heic` output to `.png` (encoding licensing constraint).

### `app.py`
Bootstraps `QApplication` and launches `MainWindow`. Window defaults to 1400×900.

### `gui/main_window.py`
Controller. Connects all signals, manages state, handles keyboard shortcuts:

| Shortcut | Action |
|----------|--------|
| `Ctrl+Z` | Undo last annotation for current image |
| `Ctrl+0` | Reset zoom to 100% |
| `+` / `-` | Zoom ±10% |
| `→` / `←` | Next/previous image |

On close: saves window geometry to `QSettings` and persists session config to TSV.

Signal wiring:
- `ConfigPanel.config_changed` → update canvas + magnifier
- `FileTreeWidget.image_selected` → load image + filter annotations
- `AnnotationCanvas.annotation_added` → append to TSV (with EXIF metadata if enabled)
- `AnnotationCanvas.annotation_removed` → remove from TSV
- `AnnotationCanvas.zoom_changed` → update config + status bar
- `AnnotationCanvas.cursor_moved` → update status bar coordinates

### `gui/image_canvas.py`
Core drawing surface (`QGraphicsView` wrapping a `QGraphicsScene`).

- **Left-click**: converts scene coords → image coords via `coord_utils.scene_to_image()`, creates annotation, emits `annotation_added`
- **Right-click**: hit-tests all markers using euclidean distance with tolerance `max(10px, marker_size/2)`, removes nearest, emits `annotation_removed`
- **Ctrl+Wheel**: zoom 1.15× per notch
- **Mouse move**: updates green dashed crosshair + magnifier overlay

HEIC images opened via PIL → PNG bytes → `QPixmap` (Qt can't decode HEIC natively).

Zoom level preserved in `ScaleInfo` and reapplied when switching images.

### `gui/config_panel.py`
Right-side panel (520px wide). Sections:
1. **File Tree** — image browser
2. **Annotations** — `AnnotationNameList` for type/style management
3. **Magnifier** — size (50–400px), zoom (1–20×), offset X/Y (0–200px), smooth upscale
4. **Metadata Fields** — EXIF checkboxes: photo_timestamp, camera_make, camera_model, gps_latitude, gps_longitude
5. **Output File** — read-only TSV path label
6. **Display** — show/hide labels and coordinates

All widgets connect to `_on_any_change()` which collects full state and emits `config_changed`. A `_suppress_signals` flag prevents feedback loops during initialization.

### `gui/annotation_list.py`
`AnnotationRow` — one row per annotation type with radio button (exclusive selection), editable name, shape combobox, color swatch, size spinbox (4–200), thickness spinbox (1–20).

`AnnotationNameList` — scrollable container:
- `add_name()` deduplicates via suffix numbering ("New annotation", "New annotation 1", ...)
- `remove_selected()` guards against removing last row
- `populate_from_config()` rebuilds rows from styles dict on startup/session restore
- `populate_from_annotations()` adds rows for annotation names not already listed

### `gui/file_tree.py`
`QFileSystemModel` + `QTreeView` filtered to image extensions (PNG, JPG, JPEG, TIFF, TIF, BMP, GIF, WebP, HEIC, HEIF). Emits `image_selected(Path)` on activation.

### `gui/magnifier.py`
`MagnifierOverlay` — circular floating widget, child of canvas. Clips source pixmap region using ellipse path, overlays green crosshair. `WA_TransparentForMouseEvents` passes clicks through to canvas. Stays within viewport bounds.

### `gui/dialogs.py`
`AboutDialog` — minimal about/help dialog.

### `utils/coord_utils.py`
`ScaleInfo` dataclass (scale_factor, original_width, original_height).

- `scene_to_image(x, y, scale)` — clamps to `[0, width-1] × [0, height-1]`
- `image_to_scene(x, y)` — identity (scene and image coords coincide at 1:1 zoom)

### `utils/metadata.py`
EXIF extraction via Pillow. Converts GPS rational tuples to decimal degrees. Returns empty dict on any error.

---

## Data Flow

```
1. STARTUP
   tsv_io.load_annotations() → annotations[], session_config{}
   Build styles from session_config (or defaults)
   Populate AnnotationNameList from styles

2. LOAD IMAGE
   FileTree selects image → MainWindow._on_image_selected()
   image_canvas.load_image(path) → _load_pixmap() → draw all annotations for this image

3. ADD ANNOTATION
   Left-click → scene coords → image coords (clamped)
   Emit annotation_added(dict) → MainWindow appends + saves TSV
   Optionally reads EXIF at creation time

4. REMOVE ANNOTATION
   Right-click → hit-test (euclidean, size-based tolerance)
   Emit annotation_removed(id) → MainWindow removes + saves TSV

5. CONFIG CHANGE
   Any widget change → ConfigPanel emits config_changed(dict)
   MainWindow forwards to canvas and magnifier

6. CLOSE
   Save QSettings geometry
   Save session config to TSV header (even if no annotations)

7. CLI RENDER
   load_annotations() → group by image_file
   For each image: renderer.render_annotations_onto_image()
   Output paths via Jinja2 template; .heic → .png auto-redirected
```

---

## TSV File Format

```tsv
# image-annotate-session
# annotation-style Point X #ff0000 12 2
# annotation-style Feature + #00ff00 12 2
# zoom 1.0000
# display show_labels=1 show_coordinates=0
# metadata-fields photo_timestamp gps_latitude gps_longitude
image-file	annotation-name	locationX(px)	locationY(px)	imageX(total width px)	imageY(total height px)	photo_timestamp	gps_latitude	gps_longitude
photos/img001.jpg	Point	245.3125	189.0000	1920	1080	2024:01:15 10:23:45	37.7749	-122.4194
```

Image paths are **relative to `images_dir`**. Moving the project folder preserves all annotations as long as the relative structure is maintained.

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| PySide6 | ≥6.6 | GUI framework |
| Pillow | ≥10.4 | Image processing and rendering |
| pillow-heif | ≥0.13 | HEIC/HEIF decoding |
| Click | ≥8.1 | CLI framework |
| Jinja2 | ≥3.1 | Output filename templates |

Dev: `pytest`, `pytest-qt`, `black`, `ruff`, `mypy` (strict).

---

## Key Design Decisions

**Plain dicts over instances** — All runtime data (Annotation, AppConfig, AnnotationStyle) are plain dicts. TypedDicts exist only for type hints. Keeps serialization simple and allows flexible keys.

**Relative image paths** — `image_file` in TSV is relative to `images_dir`. Portability: move the whole folder and annotations still resolve.

**UUID per annotation** — Stable identity for removal; generated at creation or assigned on load if missing from old files.

**Session config in TSV comments** — Styles, zoom, display settings stored in TSV header. No separate config file needed; everything travels with the data.

**Zoom preserved across images** — Intentional: useful for repeated inspection at the same magnification across a set of related images.

**Hit-testing tolerance** — `max(10px, marker_size/2)` means larger markers are proportionally easier to click-remove.

**Atomic writes** — `.tsv.tmp` → rename pattern prevents corruption if process dies mid-write.

**Metadata at annotation time** — EXIF captured when marker is placed, not on load. Stable record of the metadata at point of annotation.

---

## Quirks and Edge Cases

- **No undo stack**: `Ctrl+Z` removes only the last annotation for the current image; no redo.
- **HEIC → PNG redirect**: `generate-images` silently converts `.heic` output paths to `.png` and reports the actual output path.
- **QSettings platform-specific**: Window geometry stored in registry (Windows), plist (macOS), or ini (Linux).
- **Crosshair visibility**: Auto-hides when mouse leaves canvas to reduce clutter.
- **Empty TSV still saves session config**: Closing with zero annotations still writes style/zoom/display header lines.
- **Path resolution bug (fixed)**: Annotations are matched to selected images by resolving `images_dir / image_file`, not `image_file` alone — critical for relative path portability.

---

## Test Coverage

- `test_coord_utils.py` — bounds clamping, float precision, image-to-scene identity, zero-size images
- `test_tsv_io.py` — round-trip save/load, float precision, legacy color parsing, malformed row skipping, overwrite semantics

---

## File Map

| File | Lines | Role |
|------|-------|------|
| `cli.py` | ~146 | CLI entry points |
| `models.py` | ~95 | Type definitions + defaults |
| `tsv_io.py` | ~187 | Persistence |
| `renderer.py` | ~82 | Headless rendering |
| `app.py` | ~24 | Qt bootstrap |
| `gui/main_window.py` | ~298 | State controller |
| `gui/image_canvas.py` | ~315 | Drawing surface + interactions |
| `gui/config_panel.py` | ~224 | Settings panel |
| `gui/annotation_list.py` | ~287 | Annotation type editor |
| `gui/file_tree.py` | ~42 | Image browser |
| `gui/magnifier.py` | ~90 | Magnifier overlay |
| `gui/dialogs.py` | ~15 | About dialog |
| `utils/coord_utils.py` | ~19 | Coordinate math |
| `utils/metadata.py` | ~78 | EXIF extraction |
