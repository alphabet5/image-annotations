from pathlib import Path

from PIL import Image, ImageDraw

from .models import DEFAULT_STYLES


def _hex_to_rgba(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def render_annotations_onto_image(
    image_path: Path,
    annotations: list[dict],
    output_path: Path,
    annotation_styles: dict | None = None,
    show_labels: bool = True,
    show_coordinates: bool = False,
) -> None:
    """Render annotations onto an image and save to output_path.

    Marker shape, color, size, and thickness are resolved from annotation_styles
    keyed by annotation name. Falls back to DEFAULT_STYLES, then hardcoded defaults.
    """
    styles = annotation_styles or {}

    if output_path.suffix.lower() in {".heic", ".heif"}:
        output_path = output_path.with_suffix(".png")

    with Image.open(image_path).convert("RGBA") as img:
        draw = ImageDraw.Draw(img)

        for ann in annotations:
            cx = ann["location_x"]
            cy = ann["location_y"]
            name = ann["annotation_name"]

            style = styles.get(name) or DEFAULT_STYLES.get(name, {})
            shape = style.get("shape", "X")
            color = _hex_to_rgba(style.get("color") or ann.get("annotation_color", "#FF0000"))
            half = style.get("size", 12) / 2.0
            thickness = style.get("thickness", 2)

            if shape == "X":
                draw.line(
                    [(cx - half, cy - half), (cx + half, cy + half)],
                    fill=color, width=thickness,
                )
                draw.line(
                    [(cx + half, cy - half), (cx - half, cy + half)],
                    fill=color, width=thickness,
                )
            elif shape == "+":
                draw.line(
                    [(cx - half, cy), (cx + half, cy)],
                    fill=color, width=thickness,
                )
                draw.line(
                    [(cx, cy - half), (cx, cy + half)],
                    fill=color, width=thickness,
                )
            elif shape == "O":
                draw.ellipse(
                    [(cx - half, cy - half), (cx + half, cy + half)],
                    outline=color, width=thickness,
                )

            label_x = cx + half + 2
            if show_labels:
                draw.text((label_x, cy), name, fill=color)
            if show_coordinates:
                y_offset = cy + 14 if show_labels else cy
                draw.text(
                    (label_x, y_offset),
                    f"({cx:.1f},{cy:.1f})",
                    fill=(255, 255, 0, 255),
                )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path))
