from pathlib import Path

from PySide6.QtCore import QModelIndex, Signal
from PySide6.QtWidgets import QFileSystemModel, QTreeView, QVBoxLayout, QWidget


class FileTreeWidget(QWidget):
    image_selected = Signal(Path)

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif", ".webp"}

    def __init__(self, root: Path, parent=None):
        super().__init__(parent)
        self._model = QFileSystemModel()
        self._model.setNameFilters(
            ["*.png", "*.jpg", "*.jpeg", "*.tiff", "*.tif", "*.bmp", "*.gif", "*.webp"]
        )
        self._model.setNameFilterDisables(False)
        self._model.setRootPath(str(root))

        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setRootIndex(self._model.index(str(root)))
        self._tree.hideColumn(1)
        self._tree.hideColumn(2)
        self._tree.hideColumn(3)
        self._tree.clicked.connect(self._on_item_activated)
        self._tree.activated.connect(self._on_item_activated)  # keyboard Enter

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree)

    def set_root(self, path: Path) -> None:
        self._model.setRootPath(str(path))
        self._tree.setRootIndex(self._model.index(str(path)))

    def _on_item_activated(self, index: QModelIndex) -> None:
        path = Path(self._model.filePath(index))
        if path.suffix.lower() in self.SUPPORTED_EXTENSIONS and path.is_file():
            self.image_selected.emit(path)
