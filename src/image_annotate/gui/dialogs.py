from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About image-annotate")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>image-annotate</b> v0.1.0"))
        layout.addWidget(QLabel("Point annotation tool for images."))
        layout.addWidget(QLabel("Left-click to add, right-click to remove."))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
