# plan2.md — Bug Fix Plan

Five issues to address. No changes to TSV schema, data model, or CLI semantics beyond what's described.

---

## Issue 1: Annotation names list hardcodes defaults instead of loading from TSV

### Root cause

`AnnotationNameList.__init__` always calls `_add_default_names()`, which unconditionally inserts "Point", "Feature", and "Target" regardless of what's in the TSV.

```python
# annotation_list.py  (current)
def __init__(self, parent=None):
    super().__init__(parent)
    ...
    self._add_default_names()   # ← always runs, always inserts three hardcoded names

def _add_default_names(self):
    for name in ["Point", "Feature", "Target"]:
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.addItem(item)
    self.setCurrentRow(0)
```

### Fix

**`annotation_list.py`** — remove `_add_default_names()` entirely and stop calling it. The list starts empty. The existing `populate_from_annotations` method already handles additive merging, so it can be called with all annotations at startup.

```python
class AnnotationNameList(QListWidget):
    active_name_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.currentTextChanged.connect(self.active_name_changed)
        # No default names — populated from TSV at startup via populate_from_annotations()

    # _add_default_names() is deleted

    def populate_from_annotations(self, annotations: list[dict]) -> None:
        existing = set(self.get_names())
        for ann in annotations:
            if ann["annotation_name"] not in existing:
                item = QListWidgetItem(ann["annotation_name"])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.addItem(item)
                existing.add(ann["annotation_name"])
```

**`main_window.py`** — after loading annotations from the TSV in `__init__`, populate the name list with all unique names from those annotations:

```python
# In MainWindow.__init__, after self._annotations is loaded and config_panel is created:
self._config_panel.annotation_list.populate_from_annotations(self._annotations)
```

`config_panel.py` calls `_on_any_change` which reads `annotation_list.currentItem()`. When the list is empty `currentItem()` returns `None`; the existing fallback `... else "Point"` in `_on_any_change` handles that case already.

---

## Issue 2: Config panel is not 260px wide on startup

### Root cause

`ConfigPanel.setMinimumWidth(260)` only sets a lower bound. The `QSplitter` in `MainWindow` controls the actual initial width via its stretch factors (currently 3:1), which with a 1400px window gives the panel ~350px.

### Fix

**`main_window.py`** — after adding widgets to the splitter, call `setSizes()` to pin the initial split explicitly:

```python
splitter = QSplitter(Qt.Orientation.Horizontal, self)
splitter.addWidget(self._canvas)
splitter.addWidget(self._config_panel)
splitter.setStretchFactor(0, 1)
splitter.setStretchFactor(1, 0)
splitter.setSizes([1140, 260])   # ← added; total matches resize(1400, 900)
self.setCentralWidget(splitter)
```

`setStretchFactor(1, 0)` prevents the panel from growing when the user resizes the window; stretch factor 1 on the canvas takes all extra space. The user can still manually drag the splitter handle.

---

## Issue 3: Annotations from TSV not shown when image is opened

### Root cause

In `_on_image_selected`, annotations are filtered by comparing resolved paths:

```python
# main_window.py  (current)
img_anns = [
    a for a in self._annotations
    if Path(a["image_file"]).resolve() == path.resolve()
]
```

`image_file` stored in the TSV is a **relative path** (relative to `images_dir`), e.g. `photo.jpg` or `subdir/photo.jpg`. Calling `.resolve()` on it resolves relative to the **current working directory**, not `images_dir`. Unless the user runs the tool from exactly `images_dir`, the paths never match.

**Demonstration:**
```
images_dir = /Users/alice/project/img
cwd        = /Users/alice/project
image_file = "photo.jpg"               # stored in TSV

Path("photo.jpg").resolve()            # → /Users/alice/project/photo.jpg
path.resolve()                         # → /Users/alice/project/img/photo.jpg
# → no match
```

### Fix

**`main_window.py`** — prefix `image_file` with `images_dir` before resolving:

```python
@Slot(Path)
def _on_image_selected(self, path: Path):
    self._current_image_path = path
    try:
        self._canvas.load_image(path)
    except Exception as e:
        QMessageBox.warning(self, "Image error", f"Could not open image:\n{e}")
        return
    self._canvas.set_config(self._config)

    images_dir = Path(self._config.get("images_dir", "."))
    img_anns = [
        a for a in self._annotations
        if (images_dir / a["image_file"]).resolve() == path.resolve()
    ]

    self._canvas.set_annotations(img_anns)
    self._config_panel.annotation_list.populate_from_annotations(img_anns)
    self._status.showMessage(
        f"{path.name}  —  {len(img_anns)} annotation(s)  |  zoom 100%"
    )
```

The key change is `(images_dir / a["image_file"]).resolve()` instead of `Path(a["image_file"]).resolve()`. Because `image_file` is stored relative to `images_dir` by `image_canvas.py` (via `relative_to(images_dir)`), prepending `images_dir` reconstructs the absolute path correctly regardless of cwd.

---

## Issue 4 & 5: CLI `--images`/`--annotations` not on subcommands

### Root cause

`--images` and `--annotations` are declared on the `@click.group`, not on the subcommands. Click requires group-level options to appear **before** the subcommand name on the command line. Placing them after the subcommand name raises `Error: No such option`.

```
# fails (--images after subcommand name):
image-annotate generate-images --images ./img --annotations ./ann.tsv

# works but is non-obvious and not shown in subcommand --help:
image-annotate --images ./img --annotations ./ann.tsv generate-images
```

Additionally, subcommand `--help` output does not mention `--images` or `--annotations`, making the CLI confusing.

### Fix

Move `--images` and `--annotations` from the group onto each subcommand individually. The group becomes a plain group with no options. Each subcommand receives the values directly as parameters.

```python
# cli.py

import click
from pathlib import Path


@click.group()
def cli():
    """Image annotation tool."""


def _common_options(f):
    """Shared decorator: adds --annotations and --images to a subcommand."""
    f = click.option(
        "--annotations",
        "annotations_path",
        default="annotations.tsv",
        type=click.Path(),
        show_default=True,
        help="TSV file for annotations.",
    )(f)
    f = click.option(
        "--images",
        "images_dir",
        default=".",
        type=click.Path(exists=True, file_okay=False),
        show_default=True,
        help="Folder to load in file tree (defaults to cwd).",
    )(f)
    return f


@cli.command("ui")
@_common_options
def launch_ui(annotations_path, images_dir):
    """Launch the graphical annotation interface."""
    from .app import launch_gui
    launch_gui(
        images_dir=Path(images_dir),
        annotations_file=Path(annotations_path),
    )


@cli.command("generate-images")
@_common_options
@click.option(
    "--format",
    "filename_template",
    default="{{image_file_no_ext}}-annotated.png",
    show_default=True,
    help=(
        "Jinja2 template for output filename. "
        "Variables: image_file, image_file_no_ext, imageX, imageY"
    ),
)
def generate_images(annotations_path, images_dir, filename_template):
    """Render annotations onto copies of images and save to disk."""
    from collections import defaultdict
    from jinja2 import Template
    from PIL import Image
    from .renderer import render_annotations_onto_image
    from .tsv_io import load_annotations

    tsv_path = Path(annotations_path)
    annotations = load_annotations(tsv_path)

    if not annotations:
        click.echo("No annotations found.")
        return

    by_image: dict[str, list] = defaultdict(list)
    for ann in annotations:
        by_image[ann["image_file"]].append(ann)

    images_root = Path(images_dir)
    template = Template(filename_template)
    errors = 0

    for image_file, anns in by_image.items():
        img_path = images_root / image_file
        if not img_path.exists():
            click.echo(f"WARNING: image not found: {img_path}", err=True)
            errors += 1
            continue

        try:
            with Image.open(img_path) as img:
                iw, ih = img.size

            out_name = template.render(
                image_file=image_file,
                image_file_no_ext=Path(image_file).stem,
                imageX=iw,
                imageY=ih,
            )
            out_path = img_path.parent / out_name
            render_annotations_onto_image(img_path, anns, out_path)
            click.echo(f"Saved: {out_path}")
        except Exception as e:
            click.echo(f"ERROR processing {img_path}: {e}", err=True)
            errors += 1

    if errors:
        click.echo(f"\n{errors} file(s) had errors.", err=True)
```

After this change both invocation styles work:

```
image-annotate ui --images ./img --annotations ./ann.tsv
image-annotate generate-images --images ./img --annotations ./ann.tsv
image-annotate generate-images --help   # now shows --images and --annotations
```

Note: `generate-images` now builds image paths as `images_root / image_file` rather than using `Path(image_file)` directly, which also fixes a latent bug where relative `image_file` paths in the TSV would be resolved relative to cwd rather than `images_dir`.

---

## Summary of files to change

| File | Change |
|------|--------|
| `src/image_annotate/gui/annotation_list.py` | Remove `_add_default_names()` and its call from `__init__` |
| `src/image_annotate/gui/main_window.py` | (1) Call `populate_from_annotations(self._annotations)` after creating config panel; (2) fix path resolution in `_on_image_selected`; (3) set splitter sizes `[1140, 260]` |
| `src/image_annotate/cli.py` | Remove options from group; add `_common_options` decorator; apply to each subcommand |
