"""Sending several models of a ZIP to a slicer when a 3MF project is among them.

Why a choice is needed (root cause): a slicer opens a 3MF as a *project* - its plates,
objects and settings replace what is open - so it does not take a 3MF together with other
files in one go (Creality Print refused the whole set). So the user picks one of:

  * a 3MF project on its own (one option per 3MF in the set), or
  * the other models (STL / OBJ) together on one plate, or
  * everything as STL: each project's printable objects become one plain STL, so all models
    go on one plate (the project's plates, colours and print settings are left behind).
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QRadioButton, QVBoxLayout

from ..i18n import ltr, tr

PROJECT = "project"
MODELS = "models"
ALL_AS_STL = "all_as_stl"


def needs_choice(kinds: list[str]) -> bool:
    """True when the set cannot go to a slicer in one go: a 3MF together with anything else."""
    return kinds.count("3mf") >= 1 and len(kinds) > 1


class SendChoiceDialog(QDialog):
    """names/kinds: the files to send, in list order. After exec(): choice and project_index."""

    def __init__(self, names: list[str], kinds: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Send to slicer"))
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(480)
        self.choice = ""
        self.project_index = -1
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        intro = QLabel(tr("A 3MF project opens on its own in the slicer, so it cannot be sent "
                          "together with other models. What do you want to send?"))
        intro.setWordWrap(True)
        lay.addWidget(intro)

        self._options: list[tuple[QRadioButton, str, int]] = []
        models = [n for n, k in zip(names, kinds) if k != "3mf"]

        for i, (n, k) in enumerate(zip(names, kinds)):
            if k == "3mf":
                # Long download names are shortened in the middle (the end, ".3mf", stays);
                # ltr() keeps a Latin name in one piece inside right-to-left Arabic text.
                short = self.fontMetrics().elidedText(n, Qt.ElideMiddle, 340)
                self._add(lay, tr("The 3MF project: {name}").format(name=ltr(short)),
                          tr("With its plates, colours and print settings."), PROJECT, i)
        if models:
            self._add(lay, tr("The other models: {n}").format(n=len(models)),
                      tr("Together on one plate; the 3MF project is left out."), MODELS)
        self._add(lay, tr("Everything as STL: {n} models").format(n=len(names)),
                  tr("The project's objects become a plain STL, so all models go on one plate. "
                     "Its plates, colours and print settings are not included."), ALL_AS_STL)
        self._options[0][0].setChecked(True)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(tr("Send"))
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _add(self, lay, title: str, explanation: str, choice: str, index: int = -1):
        rb = QRadioButton(title)
        rb.setStyleSheet("font-weight: 600;")
        lay.addWidget(rb)
        text = QLabel(explanation)
        text.setObjectName("muted")
        text.setWordWrap(True)
        text.setContentsMargins(24, 0, 0, 4)          # under the radio button's text
        text.mousePressEvent = lambda _e, r=rb: r.setChecked(True)
        lay.addWidget(text)
        self._options.append((rb, choice, index))

    def _accept(self):
        for rb, choice, index in self._options:
            if rb.isChecked():
                self.choice, self.project_index = choice, index
        self.accept()


def stl_name(path: str) -> str:
    """'kit.3mf' -> 'kit.stl' (the name of a project sent as STL)."""
    return os.path.splitext(os.path.basename(path))[0] + ".stl"
