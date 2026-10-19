"""Settings dialog: default slicer, default-app registration, viewer and graphics options."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
)

from .. import file_assoc, gpu
from .. import slicer as sl


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None, gpu_info=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(560)
        root = QVBoxLayout(self)

        # ---------------- Slicer ----------------
        self._paths = dict(settings.get("slicer_paths") or {})
        self._custom = dict(settings.get("custom_slicer") or {})
        self._installed = sl.detect_installed(self._paths)
        g1 = QGroupBox("Slicer")
        l1 = QVBoxLayout(g1)
        form = QFormLayout()
        self.slicer_combo = QComboBox()
        for s_ in sl.SLICERS:
            tag = "installed" if s_.id in self._installed else "not found"
            self.slicer_combo.addItem(f"{s_.name}   ({tag})", s_.id)
        self.slicer_combo.addItem("Custom program…", sl.CUSTOM)
        k = QLabel("Default slicer")
        k.setObjectName("formKey")
        form.addRow(k, self.slicer_combo)
        self.custom_name = QLineEdit(self._custom.get("name", ""))
        self.custom_name.setPlaceholderText("Name shown on the button, e.g. SuperSlicer")
        self.custom_name_label = QLabel("Name")
        self.custom_name_label.setObjectName("formKey")
        form.addRow(self.custom_name_label, self.custom_name)
        l1.addLayout(form)
        row = QHBoxLayout()
        self.slicer_edit = QLineEdit()
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        self.detect_btn = QPushButton("Detect")
        self.detect_btn.clicked.connect(self._detect)
        row.addWidget(self.slicer_edit, 1)
        row.addWidget(browse)
        row.addWidget(self.detect_btn)
        l1.addLayout(row)
        self.slicer_status = QLabel()
        self.slicer_status.setObjectName("muted")
        self.slicer_status.setWordWrap(True)
        l1.addWidget(self.slicer_status)
        root.addWidget(g1)

        current_id = sl.resolve(settings, installed=self._installed)[0] or sl.SLICERS[0].id
        self._current_id = current_id
        self.slicer_combo.setCurrentIndex(max(0, self.slicer_combo.findData(current_id)))
        self._load_slicer_fields()
        self.slicer_combo.currentIndexChanged.connect(self._slicer_changed)
        self.slicer_edit.textChanged.connect(self._update_slicer_status)

        # ---------------- File associations ----------------
        g2 = QGroupBox("Default program for 3D files")
        l2 = QVBoxLayout(g2)
        if file_assoc.needs_confirmation():
            info_text = ("Register PrintView3D so it can open .stl, .3mf and .gcode files when you "
                         "double-click them. Windows then asks you to confirm it as the default app — "
                         "that last step is done by Windows itself and can be changed back at any time.")
        else:
            info_text = ("Add PrintView3D to your applications menu and to \"Open With\", and make it "
                         "the default app for .stl, .3mf and .gcode files. Remove registration undoes it.")
        info = QLabel(info_text)
        info.setWordWrap(True)
        info.setObjectName("muted")
        l2.addWidget(info)
        self.assoc_form = QFormLayout()
        self.assoc_form.setVerticalSpacing(6)
        l2.addLayout(self.assoc_form)
        self.assoc_labels = {}
        for ext in file_assoc.EXTENSIONS:
            lab = QLabel("-")
            self.assoc_labels[ext] = lab
            key = QLabel(ext)
            key.setObjectName("formKey")
            self.assoc_form.addRow(key, lab)
        btns = QHBoxLayout()
        self.reg_btn = QPushButton("Register && choose as default…" if file_assoc.needs_confirmation()
                                   else "Register && make default")
        self.reg_btn.setObjectName("primary")
        self.reg_btn.clicked.connect(self._register)
        self.unreg_btn = QPushButton("Remove registration")
        self.unreg_btn.clicked.connect(self._unregister)
        btns.addWidget(self.reg_btn)
        btns.addWidget(self.unreg_btn)
        btns.addStretch(1)
        l2.addLayout(btns)
        self.assoc_note = QLabel()
        self.assoc_note.setWordWrap(True)
        self.assoc_note.setObjectName("muted")
        l2.addWidget(self.assoc_note)
        root.addWidget(g2)

        # ---------------- Viewer ----------------
        g3 = QGroupBox("Viewer")
        l3 = QVBoxLayout(g3)
        self.travel_cb = QCheckBox("Show travel moves when opening G-code")
        self.travel_cb.setChecked(bool(settings.get("show_travel")))
        self.bed_cb = QCheckBox("Show build plate grid")
        self.bed_cb.setChecked(bool(settings.get("show_bed", True)))
        l3.addWidget(self.travel_cb)
        l3.addWidget(self.bed_cb)
        root.addWidget(g3)

        # ---------------- Graphics ----------------
        g4 = QGroupBox("Graphics")
        l4 = QVBoxLayout(g4)
        gpu_name = (gpu_info or {}).get("GPU", "unknown")
        self.gpu_label = QLabel(f"Drawing with: <b>{gpu_name}</b>")
        self.gpu_label.setWordWrap(True)
        l4.addWidget(self.gpu_label)
        self.gpu_cb = QCheckBox("Use the high-performance graphics card (recommended on laptops)")
        self.gpu_cb.setEnabled(gpu.is_supported())
        self.gpu_cb.setChecked(gpu.high_performance_enabled())
        self.gpu_cb.setVisible(sys.platform == "win32")
        l4.addWidget(self.gpu_cb)
        if gpu.is_supported():
            hint = "Takes effect after restarting PrintView3D."
        elif sys.platform == "win32":
            hint = "Available in the installed PrintView3D.exe."
        else:
            hint = ("On laptops with two graphics chips, start PrintView3D from the applications menu "
                    "(after Register below) — the menu entry asks for the dedicated GPU — or use your "
                    "desktop's \"Launch using Dedicated Graphics Card\" option.")
        if gpu.looks_integrated(gpu_name):
            hint = ("This looks like the built-in (slower) graphics. Tick the box and restart "
                    "for smoother rotation. " + hint)
        self.gpu_hint = QLabel(hint)
        self.gpu_hint.setWordWrap(True)
        self.gpu_hint.setObjectName("muted")
        l4.addWidget(self.gpu_hint)
        root.addWidget(g4)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        self._update_assoc_status()

    # ---------------------------------------------------------------- slicer
    def _store_slicer_fields(self):
        """Remember what was typed for the slicer that is currently selected."""
        sid, txt = self._current_id, self.slicer_edit.text().strip()
        if sid == sl.CUSTOM:
            self._custom = {"name": self.custom_name.text().strip(), "path": txt}
        elif txt and txt != self._installed.get(sid, ""):
            self._paths[sid] = txt                       # manual choice
        else:
            self._paths.pop(sid, None)                   # auto-detected

    def _load_slicer_fields(self):
        sid = self._current_id
        is_custom = sid == sl.CUSTOM
        self.custom_name.setVisible(is_custom)
        self.custom_name_label.setVisible(is_custom)
        self.detect_btn.setEnabled(not is_custom)
        self.slicer_edit.blockSignals(True)
        if is_custom:
            self.slicer_edit.setText(self._custom.get("path", ""))
            self.slicer_edit.setPlaceholderText("Path to the slicer program")
        else:
            self.slicer_edit.setText(self._paths.get(sid) or self._installed.get(sid, ""))
            self.slicer_edit.setPlaceholderText("Not found automatically — use Browse… to select it")
        self.slicer_edit.blockSignals(False)
        self._update_slicer_status()

    def _slicer_changed(self, _index):
        self._store_slicer_fields()
        self._current_id = self.slicer_combo.currentData()
        self._load_slicer_fields()

    def _browse(self):
        start = (os.path.dirname(self.slicer_edit.text()) or os.environ.get("ProgramFiles", "")
                 or os.path.expanduser("~"))
        name = sl.slicer_name(self._current_id, self.custom_name.text())
        path, _ = QFileDialog.getOpenFileName(self, f"Locate {name}", start, sl.program_file_filter())
        if path:
            self.slicer_edit.setText(os.path.normpath(path))

    def _detect(self):
        sid = self._current_id
        found = sl.find_slicer(sid, "")
        if found:
            self._installed[sid] = found
            self.slicer_edit.setText(found)
        else:
            QMessageBox.information(self, "Not found",
                                    f"{sl.slicer_name(sid)} could not be found automatically.\n"
                                    "Use Browse… to select its program file.")

    def _update_slicer_status(self):
        txt = self.slicer_edit.text().strip()
        if not txt:
            self.slicer_status.setText("No program selected.")
        elif not os.path.isfile(txt):
            self.slicer_status.setText("✖ This file does not exist")
        elif self._current_id != sl.CUSTOM and txt == self._installed.get(self._current_id):
            self.slicer_status.setText("✔ Detected automatically")
        else:
            self.slicer_status.setText("✔ Found")

    # --------------------------------------------------------- associations
    def _update_assoc_status(self):
        supported = file_assoc.is_supported()
        self.reg_btn.setEnabled(supported)
        self.unreg_btn.setEnabled(supported and file_assoc.is_registered())
        if not supported:
            for lab in self.assoc_labels.values():
                lab.setText("Not available")
            self.assoc_note.setText("File associations are available on Windows and Linux.")
            return
        for ext, st in file_assoc.status().items():
            self.assoc_labels[ext].setText(st)
        notes = []
        if not file_assoc.is_frozen():
            notes.append("You are running from source: registration will point to this Python "
                         "installation. For everyday use, register from the built PrintView3D program.")
        else:
            reg_cmd = file_assoc.registered_command()
            if reg_cmd and file_assoc.this_program().lower() not in reg_cmd.lower():
                notes.append("The registration points to a different copy of PrintView3D. "
                             "Click Register again to point it to this one.")
        self.assoc_note.setText("\n".join(notes))

    def _register(self):
        if file_assoc.needs_confirmation():
            QMessageBox.information(
                self, "Almost done",
                "PrintView3D will be added to \"Open with\".\n\n"
                "Windows Settings opens next. Set PrintView3D as the default for "
                ".stl, .3mf and .gcode there (click each file type and choose PrintView3D).")
        try:
            file_assoc.make_default()
        except OSError as e:
            QMessageBox.warning(self, "Registration failed", str(e))
            return
        self._update_assoc_status()
        if not file_assoc.needs_confirmation():
            QMessageBox.information(
                self, "Done",
                "PrintView3D is now in your applications menu and opens .stl, .3mf and .gcode "
                "files when you double-click them.")

    def _unregister(self):
        if QMessageBox.question(self, "Remove registration",
                                "Remove PrintView3D from \"Open with\" and default apps?") != QMessageBox.Yes:
            return
        file_assoc.unregister()
        self._update_assoc_status()

    # ------------------------------------------------------------------ save
    def _save(self):
        self._store_slicer_fields()
        sid = self._current_id
        if sid == sl.CUSTOM and not os.path.isfile(self._custom.get("path", "")):
            QMessageBox.warning(self, "Custom slicer", "Select the program file of your slicer first.")
            return
        self.settings.set("slicer_id", sid)
        self.settings.set("slicer_paths", self._paths)
        self.settings.set("custom_slicer", self._custom)
        self.settings.set("show_travel", self.travel_cb.isChecked())
        self.settings.set("show_bed", self.bed_cb.isChecked())
        if gpu.is_supported() and self.gpu_cb.isChecked() != gpu.high_performance_enabled():
            try:
                gpu.set_high_performance(self.gpu_cb.isChecked())
                QMessageBox.information(self, "Restart needed",
                                        "Restart PrintView3D to switch graphics card.")
            except OSError as e:
                QMessageBox.warning(self, "Could not change graphics setting", str(e))
        self.accept()
