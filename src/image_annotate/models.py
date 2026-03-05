import uuid
from typing import TypedDict


class AnnotationStyle(TypedDict):
    shape: str      # "X" | "+" | "O"
    color: str      # hex e.g. "#FF0000"
    size: int       # px, 4–200
    thickness: int  # px, 1–20


class MagnifierConfig(TypedDict):
    enabled: bool
    size: int
    zoom_factor: float
    offset_x: int
    offset_y: int
    upscale: bool


class Annotation(TypedDict):
    id: str
    image_file: str
    annotation_name: str
    annotation_color: str   # kept for backwards-compat loading of old TSVs
    location_x: float
    location_y: float
    image_width: int
    image_height: int


class AppConfig(TypedDict):
    images_dir: str
    annotations_file: str
    annotation_styles: dict     # dict[str, AnnotationStyle]
    magnifier: MagnifierConfig
    show_labels: bool
    show_coordinates: bool
    active_annotation_name: str
    zoom: float
    metadata_fields: list       # list[str]


DEFAULT_STYLES: dict = {
    "Point":   {"shape": "X", "color": "#FF0000", "size": 12, "thickness": 2},
    "Feature": {"shape": "+", "color": "#00FF00", "size": 14, "thickness": 2},
    "Target":  {"shape": "O", "color": "#0000FF", "size": 16, "thickness": 3},
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
        "annotation_styles": {k: dict(v) for k, v in DEFAULT_STYLES.items()},
        "magnifier": default_magnifier_config(),
        "show_labels": True,
        "show_coordinates": False,
        "active_annotation_name": "Point",
        "zoom": 1.0,
        "metadata_fields": ["photo_timestamp"],
    }


def make_annotation(
    image_file: str,
    annotation_name: str,
    location_x: float,
    location_y: float,
    image_width: int,
    image_height: int,
    annotation_color: str = "#FF0000",
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "image_file": image_file,
        "annotation_name": annotation_name,
        "annotation_color": annotation_color,
        "location_x": location_x,
        "location_y": location_y,
        "image_width": image_width,
        "image_height": image_height,
    }
