from typing import List

from PySide2 import QtCore
from PySide2.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

import hou


def show_rename_dialog(menu_labels: List[str], menu_items: List[str]):
    dialog = RenameDialog(menu_labels, menu_items)
    dialog.setParent(hou.qt.mainWindow(), QtCore.Qt.Window)
    dialog.show()
    height = dialog.height()
    dialog.setMaximumHeight(height)


class RenameDialog(QDialog):
    def __init__(self, menu_labels: List[str], menu_items: List[str]) -> None:
        super().__init__()
        self.setWindowTitle("Rampage - Rename ramp")
        self.layout = QVBoxLayout()

        standard_buttons = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        self.button_box = QDialogButtonBox(standard_buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        combo_box = self._create_combo_box(menu_labels, menu_items)
        self.add_field("Preset name:", combo_box)
        self.add_field("New preset name:", QLineEdit())
        self.layout.addWidget(self.button_box)
        self.layout.addStretch(1)

        self.setLayout(self.layout)
        print(self.size())

    def add_field(self, label: str, widget: QWidget):
        layout = QHBoxLayout()
        layout.addWidget(QLabel(label))
        layout.addStretch()
        layout.addWidget(widget)
        self.layout.addLayout(layout)

    def _create_combo_box(
        self, menu_labels: List[str], menu_items: List[str]
    ) -> QComboBox:
        combo_box = QComboBox()
        for label, item in zip(menu_labels, menu_items):
            combo_box.addItem(label, userData=item)

        return combo_box
