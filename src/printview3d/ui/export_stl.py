"""Export STL from a 3MF project: choose the objects, then one combined STL or one STL per object.

The geometry comes from loaders.read_3mf_for_export: printable parts only, no modifiers,
negative parts or support blockers / enforcers, no colours, materials or print settings.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QGroupBox, QHeaderView, QLabel, QRadioButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from ..i18n import count, tr
from ..loaders import MeshPart


class ExportStlDialog(QDialog):
    def __init__(self, parts: list[MeshPart], parent=None):
        super().__init__(parent)
        self.parts = parts
        self.setWindowTitle(tr("Export STL"))
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.resize(520, 460)
        lay = QVBoxLayout(self)

        intro = QLabel(tr("Choose the objects to export."))
        intro.setWordWrap(True)
        lay.addWidget(intro)

        self.tree = QTreeWidget()
        self.tree.setObjectName("exportObjects")
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels([tr("Object"), tr("Triangles")])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.NoSelection)
        self.tree.setFocusPolicy(Qt.StrongFocus)
        head = self.tree.header()
        head.setStretchLastSection(False)
        head.setSectionResizeMode(0, QHeaderView.Stretch)
        head.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        for part in parts:
            it = QTreeWidgetItem([part.name, count(part.n_triangles)])
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            it.setCheckState(0, Qt.Checked)
            it.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
            self.tree.addTopLevelItem(it)
        self.tree.itemChanged.connect(self._update_ok)
        # A click anywhere on the row (not only on the box) ticks or unticks it.
        self.tree.itemClicked.connect(self._row_clicked)
        lay.addWidget(self.tree, 1)

        box = QGroupBox(tr("Save as"))
        bl = QVBoxLayout(box)
        self.combined_rb = QRadioButton(tr("One combined STL"))
        self.separate_rb = QRadioButton(tr("One STL per object"))
        self.combined_rb.setChecked(True)
        sep_hint = QLabel(tr("Each file is named after its object and saved in a folder you choose."))
        sep_hint.setObjectName("muted")
        sep_hint.setWordWrap(True)
        sep_hint.setContentsMargins(22, 0, 0, 0)
        bl.addWidget(self.combined_rb)
        bl.addWidget(self.separate_rb)
        bl.addWidget(sep_hint)
        lay.addWidget(box)

        note = QLabel(tr("Raw geometry only: no modifiers, negative parts, or support blockers and "
                         "enforcers, and no colours, materials or print settings. Sizes in millimetres, "
                         "saved as binary STL."))
        note.setObjectName("muted")
        note.setWordWrap(True)
        lay.addWidget(note)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.ok_btn = self.buttons.addButton(tr("Export…"), QDialogButtonBox.AcceptRole)
        self.ok_btn.setDefault(True)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)
        self._update_ok()

    def _row_clicked(self, item: QTreeWidgetItem, column: int):
        if column != 0:
            item.setCheckState(0, Qt.Unchecked if item.checkState(0) == Qt.Checked else Qt.Checked)

    def _update_ok(self, *_):
        self.ok_btn.setEnabled(bool(self.selected_parts()))

    def selected_parts(self) -> list[MeshPart]:
        return [p for i, p in enumerate(self.parts)
                if self.tree.topLevelItem(i).checkState(0) == Qt.Checked]

    def per_object(self) -> bool:
        return self.separate_rb.isChecked()
