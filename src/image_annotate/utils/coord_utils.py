from dataclasses import dataclass


@dataclass
class ScaleInfo:
    scale_factor: float = 1.0
    original_width: int = 0
    original_height: int = 0


def scene_to_image(scene_x: float, scene_y: float, scale: ScaleInfo) -> tuple[float, float]:
    x = max(0.0, min(scene_x, float(scale.original_width - 1) if scale.original_width > 0 else 0.0))
    y = max(0.0, min(scene_y, float(scale.original_height - 1) if scale.original_height > 0 else 0.0))
    return x, y


def image_to_scene(img_x: float, img_y: float) -> tuple[float, float]:
    return img_x, img_y
