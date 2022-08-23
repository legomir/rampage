from typing import List, Optional

from PySide2 import QtCore
from PySide2.QtGui import QShowEvent
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
    dialog = RenameDialog(menu_labels, menu_items, parent=hou.qt.mainWindow())
    dialog.exec_()


class RenameDialog(QDialog):
    def __init__(
        self,
        menu_labels: List[str],
        menu_items: List[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Rampage - Rename ramp")
        self.layout = QVBoxLayout()

        self.layout.addWidget(QLabel("Choose ramp preset from menu and type new name."))

        self._combo_box = self._create_combo_box(menu_labels, menu_items)
        self._add_field("Preset name:", self._combo_box)
        self._input = QLineEdit()
        self._add_field("New preset name:", self._input)

        standard_buttons = QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        self.button_box = QDialogButtonBox(standard_buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

        self.setLayout(self.layout)

    def _add_field(self, label: str, widget: QWidget):
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

    def showEvent(self, event: QShowEvent) -> None:
        result = super().showEvent(event)
        self.setMaximumHeight(self.height())
        return result
