import csv
import io
import logging
import uuid
from pathlib import Path

from .utils.metadata import KNOWN_METADATA_FIELDS

log = logging.getLogger(__name__)

BASE_FIELDNAMES = [
    "image-file",
    "annotation-name",
    "locationX(px)",
    "locationY(px)",
    "imageX(total width px)",
    "imageY(total height px)",
]


def load_annotations(tsv_path: Path) -> tuple[list[dict], dict]:
    """
    Returns (annotations, session_config).

    session_config may contain:
      annotation_styles: dict[str, dict]
      zoom: float
      metadata_fields: list[str]
    """
    if not tsv_path.exists():
        log.debug("load_annotations: file not found: %s", tsv_path.resolve())
        return [], {}

    comment_lines: list[str] = []
    data_lines: list[str] = []

    with tsv_path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#"):
                comment_lines.append(line.rstrip("\n"))
            else:
                data_lines.append(line)

    # --- Parse comment header ---
    session_config: dict = {}
    annotation_styles: dict = {}
    metadata_fields: list[str] = []

    for line in comment_lines:
        # Strip leading "# " or "#"
        content = line.lstrip("#").strip()
        parts = content.split("\t")
        if not parts:
            continue
        key = parts[0].strip()

        if key == "annotation-style" and len(parts) >= 6:
            # annotation-style  <name>  <shape>  <color>  <size>  <thickness>
            _, name, shape, color, size_s, thick_s = parts[:6]
            try:
                annotation_styles[name] = {
                    "shape": shape,
                    "color": color,
                    "size": int(size_s),
                    "thickness": int(thick_s),
                }
            except ValueError:
                pass

        elif key == "zoom" and len(parts) >= 2:
            try:
                session_config["zoom"] = float(parts[1])
            except ValueError:
                pass

        elif key == "display" and len(parts) >= 2:
            for token in parts[1:]:
                if "=" in token:
                    k, v = token.split("=", 1)
                    if k == "show_labels":
                        session_config["show_labels"] = bool(int(v))
                    elif k == "show_coordinates":
                        session_config["show_coordinates"] = bool(int(v))

        elif key == "metadata-fields" and len(parts) >= 2:
            metadata_fields = [f.strip() for f in parts[1:] if f.strip()]
            session_config["metadata_fields"] = metadata_fields

    if annotation_styles:
        session_config["annotation_styles"] = annotation_styles

    # --- Parse data rows ---
    rows: list[dict] = []
    if data_lines:
        reader = csv.DictReader(io.StringIO("".join(data_lines)), delimiter="\t")
        for row in reader:
            try:
                rows.append({
                    "id": row.get("id") or str(uuid.uuid4()),
                    "image_file": row["image-file"],
                    "annotation_name": row["annotation-name"],
                    "annotation_color": _parse_legacy_color(row),
                    "location_x": float(row["locationX(px)"]),
                    "location_y": float(row["locationY(px)"]),
                    "image_width": int(row["imageX(total width px)"]),
                    "image_height": int(row["imageY(total height px)"]),
                    **{f: row.get(f, "") for f in metadata_fields},
                })
            except (KeyError, ValueError, TypeError) as exc:
                log.debug("load_annotations: skipping malformed row %r: %s", row, exc)
                continue

    log.debug("load_annotations: loaded %d annotation(s), session_config keys=%s",
              len(rows), list(session_config.keys()))
    return rows, session_config


def save_annotations(
    annotations: list[dict],
    tsv_path: Path,
    session_config: dict | None = None,
) -> None:
    """Write TSV with leading comment rows encoding session_config."""
    tmp_path = tsv_path.with_suffix(".tsv.tmp")
    tsv_path.parent.mkdir(parents=True, exist_ok=True)

    cfg = session_config or {}
    metadata_fields = [
        f for f in cfg.get("metadata_fields", [])
        if f in KNOWN_METADATA_FIELDS
    ]
    fieldnames = BASE_FIELDNAMES + metadata_fields

    with tmp_path.open("w", newline="", encoding="utf-8") as fh:
        # --- Comment header ---
        fh.write("# image-annotate-session\n")

        for name, style in cfg.get("annotation_styles", {}).items():
            fh.write(
                f"# annotation-style\t{name}\t{style.get('shape', 'X')}\t"
                f"{style.get('color', '#FF0000')}\t"
                f"{style.get('size', 12)}\t{style.get('thickness', 2)}\n"
            )

        zoom = cfg.get("zoom", 1.0)
        fh.write(f"# zoom\t{zoom:.4f}\n")

        show_labels = cfg.get("show_labels", True)
        show_coordinates = cfg.get("show_coordinates", False)
        fh.write(f"# display\tshow_labels={int(show_labels)}\tshow_coordinates={int(show_coordinates)}\n")

        if metadata_fields:
            fh.write("# metadata-fields\t" + "\t".join(metadata_fields) + "\n")

        # --- Data ---
        writer = csv.DictWriter(
            fh, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore"
        )
        writer.writeheader()
        for ann in annotations:
            writer.writerow(_annotation_to_row(ann, metadata_fields))

    tmp_path.replace(tsv_path)


def _annotation_to_row(ann: dict, metadata_fields: list[str] | None = None) -> dict:
    row: dict = {
        "image-file": ann["image_file"],
        "annotation-name": ann["annotation_name"],
        "locationX(px)": f"{ann['location_x']:.4f}",
        "locationY(px)": f"{ann['location_y']:.4f}",
        "imageX(total width px)": ann["image_width"],
        "imageY(total height px)": ann["image_height"],
    }
    for field in (metadata_fields or []):
        row[field] = ann.get(field, "")
    return row


def _parse_legacy_color(row: dict) -> str:
    """Extract color from old 'annotation-icon' field (shape:color) if present."""
    icon_raw = row.get("annotation-icon", "")
    if ":" in icon_raw:
        _, color = icon_raw.split(":", 1)
        return color
    return "#FF0000"
