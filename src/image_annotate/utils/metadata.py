import logging
from pathlib import Path

log = logging.getLogger(__name__)

# Maps TSV column name → PIL ExifTags tag name
KNOWN_METADATA_FIELDS: dict[str, str] = {
    "photo_timestamp": "DateTimeOriginal",
    "camera_make":     "Make",
    "camera_model":    "Model",
    "gps_latitude":    "GPSLatitude",
    "gps_longitude":   "GPSLongitude",
}


def _rational_to_decimal(rational_tuple) -> float:
    """Convert a GPS rational tuple [(deg_num, deg_den), (min_num, min_den), (sec_num, sec_den)]
    to decimal degrees."""
    try:
        degrees = rational_tuple[0][0] / rational_tuple[0][1]
        minutes = rational_tuple[1][0] / rational_tuple[1][1] / 60.0
        seconds = rational_tuple[2][0] / rational_tuple[2][1] / 3600.0
        return degrees + minutes + seconds
    except (IndexError, ZeroDivisionError, TypeError):
        return 0.0


def read_photo_metadata(image_path: Path) -> dict[str, str]:
    """Return a flat dict of known EXIF fields as strings. Returns {} on any failure."""
    result: dict[str, str] = {}
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS

        with Image.open(image_path) as img:
            exif_data = img._getexif()  # type: ignore[attr-defined]
            if not exif_data:
                return result

        # Build reverse lookup: tag name → tag id
        name_to_id = {name: tag_id for tag_id, name in TAGS.items()}

        # Simple string fields
        for field_name, exif_tag_name in KNOWN_METADATA_FIELDS.items():
            if exif_tag_name.startswith("GPS"):
                continue  # handled separately below
            tag_id = name_to_id.get(exif_tag_name)
            if tag_id is not None and tag_id in exif_data:
                result[field_name] = str(exif_data[tag_id]).strip()

        # GPS fields — need to decode the GPSInfo sub-IFD
        gps_tag_id = name_to_id.get("GPSInfo")
        if gps_tag_id and gps_tag_id in exif_data:
            gps_raw = exif_data[gps_tag_id]
            gps_name_to_id = {name: tag_id for tag_id, name in GPSTAGS.items()}

            lat_id  = gps_name_to_id.get("GPSLatitude")
            lat_ref_id = gps_name_to_id.get("GPSLatitudeRef")
            lon_id  = gps_name_to_id.get("GPSLongitude")
            lon_ref_id = gps_name_to_id.get("GPSLongitudeRef")

            if lat_id and lat_id in gps_raw:
                lat = _rational_to_decimal(gps_raw[lat_id])
                if lat_ref_id and gps_raw.get(lat_ref_id) == "S":
                    lat = -lat
                result["gps_latitude"] = f"{lat:.6f}"

            if lon_id and lon_id in gps_raw:
                lon = _rational_to_decimal(gps_raw[lon_id])
                if lon_ref_id and gps_raw.get(lon_ref_id) == "W":
                    lon = -lon
                result["gps_longitude"] = f"{lon:.6f}"

    except Exception as exc:
        log.debug("read_photo_metadata(%s): %s", image_path, exc)

    return result
