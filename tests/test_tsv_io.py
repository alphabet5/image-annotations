from src.image_annotate.tsv_io import (
    load_annotations,
    append_annotation,
    save_annotations,
    TSV_FIELDNAMES,
)
from src.image_annotate.models import make_annotation


def _ann(name="Point", x=10.5, y=20.75, icon="X", color="#FF0000"):
    return make_annotation("img.png", name, icon, x, y, 800, 600, annotation_color=color)


def test_load_missing_file(tmp_path):
    result = load_annotations(tmp_path / "nonexistent.tsv")
    assert result == []


def test_round_trip(tmp_path):
    tsv = tmp_path / "out.tsv"
    ann = _ann(x=123.4567, y=89.1234)
    save_annotations([ann], tsv)
    loaded = load_annotations(tsv)
    assert len(loaded) == 1
    assert loaded[0]["annotation_name"] == "Point"
    assert abs(loaded[0]["location_x"] - 123.4567) < 0.0001
    assert abs(loaded[0]["location_y"] - 89.1234) < 0.0001
    assert loaded[0]["image_width"] == 800
    assert loaded[0]["image_height"] == 600


def test_color_round_trip(tmp_path):
    tsv = tmp_path / "out.tsv"
    ann = _ann(color="#00FF80")
    save_annotations([ann], tsv)
    loaded = load_annotations(tsv)
    assert loaded[0]["annotation_icon"] == "X"
    assert loaded[0]["annotation_color"] == "#00FF80"


def test_color_encoded_in_icon_column(tmp_path):
    tsv = tmp_path / "out.tsv"
    ann = _ann(icon="+", color="#1234AB")
    save_annotations([ann], tsv)
    raw = tsv.read_text()
    assert "+:#1234AB" in raw


def test_legacy_icon_without_color(tmp_path):
    tsv = tmp_path / "out.tsv"
    tsv.write_text(
        "\t".join(TSV_FIELDNAMES) + "\n"
        "img.png\tPoint\tX\t1.0\t2.0\t800\t600\n",
        encoding="utf-8",
    )
    loaded = load_annotations(tsv)
    assert loaded[0]["annotation_icon"] == "X"
    assert loaded[0]["annotation_color"] == "#FF0000"


def test_float_coords_preserved(tmp_path):
    tsv = tmp_path / "out.tsv"
    ann = _ann(x=1.2345, y=6.7890)
    save_annotations([ann], tsv)
    loaded = load_annotations(tsv)
    assert abs(loaded[0]["location_x"] - 1.2345) < 0.0001
    assert abs(loaded[0]["location_y"] - 6.7890) < 0.0001


def test_append_creates_header(tmp_path):
    tsv = tmp_path / "out.tsv"
    ann = _ann()
    append_annotation(ann, tsv)
    lines = tsv.read_text().splitlines()
    assert lines[0].startswith("image-file")
    assert len(lines) == 2


def test_append_no_duplicate_header(tmp_path):
    tsv = tmp_path / "out.tsv"
    append_annotation(_ann(name="A"), tsv)
    append_annotation(_ann(name="B"), tsv)
    lines = tsv.read_text().splitlines()
    header_count = sum(1 for l in lines if l.startswith("image-file"))
    assert header_count == 1
    assert len(lines) == 3


def test_corrupt_rows_skipped(tmp_path):
    tsv = tmp_path / "out.tsv"
    tsv.write_text(
        "\t".join(TSV_FIELDNAMES) + "\n"
        "good.png\tPoint\tX\t1.0\t2.0\t800\t600\n"
        "bad row with missing columns\n"
        "good2.png\tTarget\tO\t3.0\t4.0\t640\t480\n",
        encoding="utf-8",
    )
    loaded = load_annotations(tsv)
    assert len(loaded) == 2
    assert loaded[0]["image_file"] == "good.png"
    assert loaded[1]["image_file"] == "good2.png"


def test_save_overwrites(tmp_path):
    tsv = tmp_path / "out.tsv"
    save_annotations([_ann(name="First")], tsv)
    save_annotations([_ann(name="Second"), _ann(name="Third")], tsv)
    loaded = load_annotations(tsv)
    assert len(loaded) == 2
    assert loaded[0]["annotation_name"] == "Second"
