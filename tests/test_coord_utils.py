from src.image_annotate.utils.coord_utils import ScaleInfo, scene_to_image, image_to_scene


def _scale(w=100, h=200, factor=1.0):
    return ScaleInfo(scale_factor=factor, original_width=w, original_height=h)


def test_in_bounds_passthrough():
    x, y = scene_to_image(50.0, 100.0, _scale())
    assert x == 50.0
    assert y == 100.0


def test_clamp_below_zero():
    x, y = scene_to_image(-5.0, -10.0, _scale())
    assert x == 0.0
    assert y == 0.0


def test_clamp_at_boundary():
    x, y = scene_to_image(99.0, 199.0, _scale())
    assert x == 99.0
    assert y == 199.0


def test_clamp_above_bounds():
    x, y = scene_to_image(200.0, 500.0, _scale())
    assert x == 99.0
    assert y == 199.0


def test_float_precision_preserved():
    x, y = scene_to_image(12.3456, 78.9012, _scale())
    assert abs(x - 12.3456) < 1e-9
    assert abs(y - 78.9012) < 1e-9


def test_image_to_scene_passthrough():
    x, y = image_to_scene(42.5, 73.1)
    assert x == 42.5
    assert y == 73.1


def test_zero_size_image():
    scale = ScaleInfo(scale_factor=1.0, original_width=0, original_height=0)
    x, y = scene_to_image(10.0, 10.0, scale)
    assert x == 0.0
    assert y == 0.0
