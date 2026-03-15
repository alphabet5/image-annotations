from pathlib import Path

from PySide6.QtCore import QModelIndex, Signal
from PySide6.QtWidgets import QAbstractItemView, QFileSystemModel, QTreeView, QVBoxLayout, QWidget


class FileTreeWidget(QWidget):
    image_selected = Signal(Path)

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif", ".webp", ".heic", ".heif", ".rw2"}

    def __init__(self, root: Path, parent=None):
        super().__init__(parent)
        self._model = QFileSystemModel()
        self._model.setNameFilters(
            ["*.png", "*.jpg", "*.jpeg", "*.tiff", "*.tif", "*.bmp", "*.gif", "*.webp", "*.heic", "*.heif", "*.rw2"]
        )
        self._model.setNameFilterDisables(False)
        self._model.setRootPath(str(root))

        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setRootIndex(self._model.index(str(root)))
        self._tree.setAutoScroll(False)
        self._tree.setDragEnabled(False)
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self._tree.hideColumn(1)
        self._tree.hideColumn(2)
        self._tree.hideColumn(3)
        # currentChanged fires on single-click AND arrow-key navigation
        self._tree.selectionModel().currentChanged.connect(self._on_current_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree)

    def set_root(self, path: Path) -> None:
        self._model.setRootPath(str(path))
        self._tree.setRootIndex(self._model.index(str(path)))

    def _on_current_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        path = Path(self._model.filePath(current))
        if path.suffix.lower() in self.SUPPORTED_EXTENSIONS and path.is_file():
            self.image_selected.emit(path)
