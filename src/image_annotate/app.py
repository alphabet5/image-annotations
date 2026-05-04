import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .models import default_app_config
from .gui.main_window import MainWindow


def launch_gui(
    images_dir: Path,
    annotations_file: Path,
    image_files: list[Path] | None = None,
) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("image-annotate")
    app.setOrganizationName("image-annotate")

    config = default_app_config(
        images_dir=str(images_dir.resolve()),
        annotations_file=str(annotations_file.resolve()),
    )
    if image_files:
        config["image_files"] = [str(p.resolve()) for p in image_files]

    window = MainWindow(config)
    window.resize(1400, 900)
    window.show()
    sys.exit(app.exec())
