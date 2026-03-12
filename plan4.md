# plan4.md — Extended Format Support & Image Adjustments

This plan covers four feature areas:

1. **HEIC/HEIF** — iPhone image support (already partly implemented)
2. **TIFF** — robust TIFF loading via PIL rather than Qt
3. **RW2** — Panasonic RAW format support via `rawpy`
4. **Image Adjustments** — per-session exposure, brightness, and gamma controls persisted in the TSV

---

## Status of HEIC work (from original plan4)

All HEIC steps are already complete in the codebase:
- `pillow-heif>=0.13` is in `pyproject.toml`
- `register_heif_opener()` is called in `__init__.py`
- `.heic`/`.heif` are in `FileTreeWidget.SUPPORTED_EXTENSIONS` and `setNameFilters`
- `_load_pixmap()` in `image_canvas.py` branches on `_HEIC_EXTENSIONS` and loads via PIL
- `renderer.py` redirects `.heic` output paths to `.png`

The HEIC section below is kept for reference only. New work starts at **TIFF**.

---

## Feature 1 — TIFF: reliable loading via PIL

Qt can open some TIFF variants natively, but fails on 16-bit, multi-page, or uncommon-compression files. PIL (Pillow) handles the full TIFF spec across all platforms.

### Change: `src/image_annotate/gui/image_canvas.py`

The existing `_load_pixmap()` helper currently hard-codes HEIC as the only PIL path. As part of the broader refactor in Feature 3 below, **all** image loading will be routed through PIL. This automatically solves TIFF, HEIC, and RW2 in one unified pipeline.

No TIFF-specific changes are needed beyond that refactor.

---

## Feature 2 — RW2: Panasonic RAW support

RW2 is Panasonic's proprietary RAW format. Neither Qt nor Pillow can open it. The `rawpy` library decodes RAW files (including RW2) via LibRaw, returning a numpy array that PIL can consume.

### Step 1 — Add dependency

**`pyproject.toml`** — add `rawpy`:

```toml
dependencies = [
    "PySide6>=6.6",
    "Pillow>=10.4",
    "pillow-heif>=0.13",
    "rawpy>=0.18",
    "click>=8.1",
    "Jinja2>=3.1",
]
```

`rawpy` pulls in `numpy` as its own dependency; no need to list numpy separately. `rawpy` ships prebuilt wheels for macOS, Windows, and most Linux distributions.

### Step 2 — File browser: show RW2 files

**`src/image_annotate/gui/file_tree.py`** — add `.rw2` in two places:

```python
SUPPORTED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".tiff", ".tif",
    ".bmp", ".gif", ".webp",
    ".heic", ".heif",
    ".rw2",                # ← added
}

self._model.setNameFilters([
    "*.png", "*.jpg", "*.jpeg", "*.tiff", "*.tif",
    "*.bmp", "*.gif", "*.webp",
    "*.heic", "*.heif",
    "*.rw2",               # ← added
])
```

### Step 3 — Canvas: unified PIL loader

Refactor `image_canvas.py` to route **all** formats through PIL. This replaces the current dual `_HEIC_EXTENSIONS` / `QPixmap(str(path))` split.

```python
import io
from PIL import Image as PILImage, ImageEnhance

_RAW_EXTENSIONS = {".rw2"}
# All formats that need PIL (everything — Qt path removed for simplicity)

def _load_pil_image(path: Path) -> PILImage.Image:
    """
    Decode any supported format into an RGB PIL Image.
    - RW2 and other RAW formats: decoded via rawpy
    - Everything else (HEIC, TIFF, JPEG, PNG, …): PIL / pillow-heif
    """
    if path.suffix.lower() in _RAW_EXTENSIONS:
        import rawpy  # lazy import — only paid when opening a RAW file
        with rawpy.imread(str(path)) as raw:
            rgb_array = raw.postprocess(use_camera_wb=True, output_bps=8)
        return PILImage.fromarray(rgb_array)  # numpy array → PIL Image

    with PILImage.open(path) as img:
        return img.convert("RGB")  # force pixel data into memory before context exits


def _pil_to_pixmap(pil_image: PILImage.Image) -> QPixmap:
    """Encode a PIL Image to PNG bytes and load into QPixmap."""
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buf.getvalue())
    return pixmap
```

Update `AnnotationCanvas.__init__` to store the raw PIL image:

```python
self._pil_image: PILImage.Image | None = None
```

Update `load_image` to use the new pipeline:

```python
def load_image(self, path: Path) -> None:
    self._current_image_path = path
    self._pil_image = _load_pil_image(path)          # raw, unadjusted
    pixmap = _apply_adjustments(self._pil_image, self._config)
    if pixmap.isNull():
        raise ValueError(f"Could not load image: {path}")
    self._original_size = (pixmap.width(), pixmap.height())
    # … rest unchanged (scene.clear, addPixmap, etc.)
```

Add a `_reload_pixmap` helper for when adjustments change without a new image:

```python
def _reload_pixmap(self) -> None:
    """Re-apply adjustments to the stored PIL image, update the scene in place."""
    if self._pil_image is None or self._pixmap_item is None:
        return
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
```

Update `set_config` to trigger `_reload_pixmap` only when adjustment values actually change:

```python
def set_config(self, config: dict) -> None:
    old_adj = self._config.get("image_adjustments", {})
    self._config = config
    new_adj = config.get("image_adjustments", {})
    if new_adj != old_adj:
        self._reload_pixmap()
    self._rebuild_annotation_graphics()
    if self._magnifier:
        self._magnifier.set_config(config)
```

---

## Feature 3 — Image Adjustments (exposure, brightness, gamma)

These are **display-only** modifiers applied on top of the raw decoded image. They do not alter the source file. They persist across image switches within a session and are saved to the TSV header so they reload automatically on next open.

### Adjustment definitions

| Setting | Storage key | Range | Default | Semantics |
|---------|-------------|-------|---------|-----------|
| Exposure | `exposure` | 0.1 – 4.0 | 1.0 | Linear pixel multiplier (e.g. 2.0 = twice as bright) |
| Brightness | `brightness` | 0.1 – 3.0 | 1.0 | Secondary linear multiplier applied after exposure |
| Gamma | `gamma` | 0.1 – 5.0 | 1.0 | Tonal power curve: output = input^(1/gamma) |

**Application pipeline** (all in PIL, no numpy required):

```python
def _apply_adjustments(pil_image: PILImage.Image, config: dict) -> QPixmap:
    adj = config.get("image_adjustments", {})
    exposure   = float(adj.get("exposure",   1.0))
    brightness = float(adj.get("brightness", 1.0))
    gamma      = float(adj.get("gamma",      1.0))

    img = pil_image  # already RGB

    # Combined linear factor (exposure × brightness)
    linear = exposure * brightness
    if abs(linear - 1.0) > 1e-4:
        img = ImageEnhance.Brightness(img).enhance(linear)

    # Gamma: 256-entry LUT per channel
    if abs(gamma - 1.0) > 1e-4:
        inv_gamma = 1.0 / max(gamma, 0.01)
        lut = [min(255, max(0, round((i / 255.0) ** inv_gamma * 255.0)))
               for i in range(256)]
        img = img.point(lut * 3)  # 3 identical channel LUTs

    return _pil_to_pixmap(img)
```

Order: exposure → brightness → gamma. Exposure and brightness are both linear, so they are folded into a single `ImageEnhance.Brightness` call. Gamma uses a precomputed 8-bit LUT applied via `Image.point()` (no numpy needed).

### Step 1 — Model

**`src/image_annotate/models.py`** — add TypedDict and defaults:

```python
class ImageAdjustments(TypedDict):
    exposure:   float   # linear multiplier, 0.1–4.0
    brightness: float   # linear multiplier, 0.1–3.0
    gamma:      float   # power exponent,    0.1–5.0


def default_image_adjustments() -> dict:
    return {"exposure": 1.0, "brightness": 1.0, "gamma": 1.0}
```

Add to `AppConfig`:

```python
class AppConfig(TypedDict):
    ...
    image_adjustments: ImageAdjustments
```

Add to `default_app_config()`:

```python
def default_app_config(...) -> dict:
    return {
        ...
        "image_adjustments": default_image_adjustments(),
    }
```

### Step 2 — TSV persistence

**`src/image_annotate/tsv_io.py`** — new comment-header line:

```
# image-adjustments	exposure=1.0000	brightness=1.0000	gamma=1.0000
```

**Parsing** — add inside the `for line in comment_lines` loop:

```python
elif key == "image-adjustments" and len(parts) >= 2:
    adj: dict = {}
    for token in parts[1:]:
        if "=" in token:
            k, v = token.split("=", 1)
            try:
                adj[k] = float(v)
            except ValueError:
                pass
    if adj:
        session_config["image_adjustments"] = adj
```

**Writing** — add inside `save_annotations`, after the `# display` line:

```python
adj = cfg.get("image_adjustments", {})
exposure   = adj.get("exposure",   1.0)
brightness = adj.get("brightness", 1.0)
gamma      = adj.get("gamma",      1.0)
fh.write(
    f"# image-adjustments\t"
    f"exposure={exposure:.4f}\t"
    f"brightness={brightness:.4f}\t"
    f"gamma={gamma:.4f}\n"
)
```

### Step 3 — Config panel UI

**`src/image_annotate/gui/config_panel.py`** — add a new group builder and wire it in:

```python
def _build_adjustments_group(self, config: dict) -> QGroupBox:
    group = QGroupBox("Image Adjustments")
    layout = QVBoxLayout(group)
    adj = config.get("image_adjustments", {})

    # Exposure
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

    # Brightness
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

    # Gamma
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

    # Reset button
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
```

Wire the group into `__init__` (after the magnifier group):

```python
layout.addWidget(self._build_adjustments_group(config))
```

Include adjustments in `_on_any_change`:

```python
"image_adjustments": {
    "exposure":   self._adj_exposure.value(),
    "brightness": self._adj_brightness.value(),
    "gamma":      self._adj_gamma.value(),
},
```

Add `QPushButton` to imports.

### Step 4 — Main window session restore

**`src/image_annotate/gui/main_window.py`** — restore `image_adjustments` from `session_config`:

```python
if "image_adjustments" in session_config:
    config["image_adjustments"] = session_config["image_adjustments"]
```

Add alongside the existing `zoom`, `show_labels`, `show_coordinates`, and `metadata_fields` restore blocks.

---

## File-by-file change summary

| File | Changes |
|------|---------|
| `pyproject.toml` | Add `rawpy>=0.18` |
| `models.py` | Add `ImageAdjustments` TypedDict, `default_image_adjustments()`, add field to `AppConfig` and `default_app_config()` |
| `gui/file_tree.py` | Add `.rw2` to `SUPPORTED_EXTENSIONS` and `setNameFilters` |
| `gui/image_canvas.py` | Replace `_load_pixmap` with `_load_pil_image` + `_pil_to_pixmap`; add `_apply_adjustments`; add `_reload_pixmap`; store `self._pil_image`; update `load_image` and `set_config` |
| `gui/config_panel.py` | Add `_build_adjustments_group`, `_reset_adjustments`; wire into layout and `_on_any_change` |
| `tsv_io.py` | Parse and write `# image-adjustments` header line |
| `gui/main_window.py` | Restore `image_adjustments` from `session_config` on startup |

---

## Testing notes

### TIFF
1. Open a folder containing 8-bit, 16-bit, and multi-page TIFF files
2. Each should display without error; multi-page opens the first frame
3. Annotations placed on a TIFF round-trip through TSV correctly

### RW2
1. `image-annotate ui --images ./raws` — `.rw2` files appear in the file tree
2. Click an RW2 file — image renders (camera white balance applied)
3. Place annotation, close, reopen — annotation still present
4. `image-annotate generate-images` renders annotations onto the RW2 and writes a PNG output

### Image Adjustments
1. Open any image; move Exposure slider from 0.5 to 2.0 — image responds immediately
2. Move Brightness — secondary brightening applied on top
3. Move Gamma — tonal curve shifts midtones
4. Switch images — sliders retain their values (adjustments persist across image switch)
5. Close and reopen — TSV header contains `# image-adjustments …` line; sliders restore to saved values
6. Click Reset — all three values return to 1.0 / 1.0 / 1.0; image returns to native appearance
7. Non-adjusted images (all defaults) — no performance penalty (PIL encode/decode still runs but without transforms)

---

## Todo List

### Setup
- [x] Add `rawpy>=0.18` to `dependencies` in `pyproject.toml`
- [ ] Install updated dependencies: `pip install -e ".[dev]"`

### `src/image_annotate/models.py`
- [x] Add `ImageAdjustments` TypedDict
- [x] Add `default_image_adjustments()` function
- [x] Add `image_adjustments: ImageAdjustments` field to `AppConfig`
- [x] Add `"image_adjustments": default_image_adjustments()` to `default_app_config()`

### `src/image_annotate/gui/file_tree.py`
- [x] Add `".rw2"` to `SUPPORTED_EXTENSIONS`
- [x] Add `"*.rw2"` to `setNameFilters()` list

### `src/image_annotate/gui/image_canvas.py`
- [x] Add `from PIL import ImageEnhance` import
- [x] Replace `_HEIC_EXTENSIONS` constant with `_RAW_EXTENSIONS = {".rw2"}`
- [x] Write `_load_pil_image(path: Path) -> PILImage.Image` (handles RW2 via rawpy, all others via PIL)
- [x] Write `_pil_to_pixmap(pil_image: PILImage.Image) -> QPixmap` helper
- [x] Write `_apply_adjustments(pil_image: PILImage.Image, config: dict) -> QPixmap`
- [x] Add `self._pil_image: PILImage.Image | None = None` to `__init__`
- [x] Update `load_image` to call `_load_pil_image` then `_apply_adjustments`
- [x] Add `_reload_pixmap()` method
- [x] Update `set_config` to call `_reload_pixmap()` when adjustments change

### `src/image_annotate/gui/config_panel.py`
- [x] Add `QPushButton` to imports
- [x] Write `_build_adjustments_group(config)` method with exposure, brightness, gamma spinboxes
- [x] Write `_reset_adjustments()` method
- [x] Call `self._build_adjustments_group(config)` in `__init__` (after magnifier group)
- [x] Add `"image_adjustments": {...}` dict to `_on_any_change` output

### `src/image_annotate/tsv_io.py`
- [x] Parse `# image-adjustments` comment line in `load_annotations`
- [x] Write `# image-adjustments` comment line in `save_annotations`

### `src/image_annotate/gui/main_window.py`
- [x] Restore `image_adjustments` from `session_config` in `__init__`

### Manual testing
- [ ] TIFF files (8-bit, 16-bit) load without errors
- [ ] RW2 files appear in file tree and load in canvas
- [ ] Annotations on RW2 images save and restore correctly
- [ ] Exposure slider affects image brightness linearly
- [ ] Brightness and gamma sliders produce expected tonal changes
- [ ] Adjustments persist when switching between images
- [ ] Closing and reopening restores adjustment values from TSV header
- [ ] Reset button restores all three sliders to 1.0
- [ ] Non-RAW images (PNG, JPEG, HEIC) unaffected by refactor
