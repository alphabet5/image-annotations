from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QFileSystemModel, QHBoxLayout, QPushButton, QTreeView, QVBoxLayout, QWidget

FILE_PATH_ROLE = Qt.ItemDataRole.UserRole + 1


class FileTreeWidget(QWidget):
    image_selected = Signal(Path)

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif", ".webp", ".heic", ".heif", ".rw2"}

    def __init__(self, root: Path, files: list[Path] | None = None, parent=None):
        super().__init__(parent)
        self._expand_all = False
        self._file_list_mode = files is not None

        if self._file_list_mode:
            self._model = self._build_file_list_model(files, root)
        else:
            self._model = QFileSystemModel()
            self._model.setNameFilters(
                ["*.png", "*.jpg", "*.jpeg", "*.tiff", "*.tif", "*.bmp", "*.gif", "*.webp", "*.heic", "*.heif", "*.rw2"]
            )
            self._model.setNameFilterDisables(False)
            self._model.setRootPath(str(root))
            self._model.directoryLoaded.connect(self._on_directory_loaded)

        self._tree = QTreeView()
        self._tree.setModel(self._model)
        if not self._file_list_mode:
            self._tree.setRootIndex(self._model.index(str(root)))
        self._tree.setAutoScroll(False)
        self._tree.setDragEnabled(False)
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        if not self._file_list_mode:
            self._tree.hideColumn(1)
            self._tree.hideColumn(2)
            self._tree.hideColumn(3)
        self._tree.selectionModel().currentChanged.connect(self._on_current_changed)

        self._expand_btn = QPushButton("Expand All")
        self._expand_btn.setCheckable(True)
        self._expand_btn.clicked.connect(self._on_expand_toggled)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(self._expand_btn)
        btn_layout.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(btn_layout)
        layout.addWidget(self._tree)

        if self._file_list_mode:
            self._tree.expandAll()

    def _build_file_list_model(self, files: list[Path], root: Path) -> QStandardItemModel:
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["File"])
        dirs: dict[Path, QStandardItem] = {}

        for file_path in sorted(files):
            try:
                rel = file_path.resolve().relative_to(root.resolve())
            except ValueError:
                rel = Path(file_path.name)

            parent_rel = rel.parent

            file_item = QStandardItem(file_path.name)
            file_item.setData(file_path.resolve(), FILE_PATH_ROLE)
            file_item.setEditable(False)

            if parent_rel == Path("."):
                model.appendRow(file_item)
            else:
                if parent_rel not in dirs:
                    dir_item = QStandardItem(str(parent_rel))
                    dir_item.setEditable(False)
                    model.appendRow(dir_item)
                    dirs[parent_rel] = dir_item
                dirs[parent_rel].appendRow(file_item)

        return model

    def set_root(self, path: Path) -> None:
        if not self._file_list_mode:
            self._model.setRootPath(str(path))
            self._tree.setRootIndex(self._model.index(str(path)))

    def _on_expand_toggled(self, checked: bool) -> None:
        self._expand_all = checked
        self._expand_btn.setText("Collapse All" if checked else "Expand All")
        if checked:
            if self._file_list_mode:
                self._tree.expandAll()
            else:
                self._tree.expandRecursively(self._tree.rootIndex())
        else:
            self._tree.collapseAll()

    def _on_directory_loaded(self, path: str) -> None:
        if self._expand_all and not self._file_list_mode:
            idx = self._model.index(path)
            self._tree.expandRecursively(idx)

    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if self._file_list_mode:
            path_data = current.data(FILE_PATH_ROLE)
            if isinstance(path_data, Path) and path_data.is_file():
                self.image_selected.emit(path_data)
        else:
            path = Path(self._model.filePath(current))
            if path.suffix.lower() in self.SUPPORTED_EXTENSIONS and path.is_file():
                self.image_selected.emit(path)
