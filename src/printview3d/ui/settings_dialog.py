"""Settings dialog: language, theme, default slicer, FreeCAD, default-app registration, viewer and graphics."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from .. import file_assoc, gpu, i18n
from .. import freecad as fc
from .. import slicer as sl
from ..i18n import tr
from . import theme
from .labels import assoc_status


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None, gpu_info=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(tr("Settings"))
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(560)
        outer = QVBoxLayout(self)
        # The settings scroll when the screen is small (laptops with display scaling).
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 0, 6, 0)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        # ---------------- Language ----------------
        g0 = QGroupBox(tr("Language"))
        l0 = QFormLayout(g0)
        self.lang_combo = QComboBox()
        self.lang_combo.addItem(tr("Automatic (system language)"), "auto")
        completion = i18n.completion()
        for code, name in i18n.LANGUAGES.items():
            label = name
            if code != "en" and completion.get(code, 0) < 50:
                label += "  " + tr("(incomplete)")
            self.lang_combo.addItem(label, code)
        self.lang_combo.setCurrentIndex(max(0, self.lang_combo.findData(settings.get("language", "en"))))
        k0 = QLabel(tr("Language"))
        k0.setObjectName("formKey")
        l0.addRow(k0, self.lang_combo)
        help_lbl = QLabel(tr("Missing or wrong translation? You can help translate PrintView3D — "
                             "see \"Translations\" on the project page."))
        help_lbl.setObjectName("muted")
        help_lbl.setWordWrap(True)
        l0.addRow(help_lbl)
        root.addWidget(g0)

        # ---------------- Appearance ----------------
        ga = QGroupBox(tr("Appearance"))
        la = QFormLayout(ga)
        self.theme_combo = QComboBox()
        for key, name in theme.THEME_NAMES.items():
            self.theme_combo.addItem(tr(name), key)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(settings.get("theme", "auto"))))
        ka = QLabel(tr("Theme"))
        ka.setObjectName("formKey")
        la.addRow(ka, self.theme_combo)
        root.addWidget(ga)

        # ---------------- Slicer ----------------
        self._paths = dict(settings.get("slicer_paths") or {})
        self._custom = dict(settings.get("custom_slicer") or {})
        self._installed = sl.detect_installed(self._paths)
        g1 = QGroupBox(tr("Slicer"))
        l1 = QVBoxLayout(g1)
        form = QFormLayout()
        self.slicer_combo = QComboBox()
        for s_ in sl.SLICERS:
            tag = tr("installed") if s_.id in self._installed else tr("not found")
            self.slicer_combo.addItem(f"{s_.name}   ({tag})", s_.id)
        self.slicer_combo.addItem(tr("Custom program…"), sl.CUSTOM)
        k = QLabel(tr("Default slicer"))
        k.setObjectName("formKey")
        form.addRow(k, self.slicer_combo)
        self.custom_name = QLineEdit(self._custom.get("name", ""))
        self.custom_name.setPlaceholderText(tr("Name shown on the button, e.g. SuperSlicer"))
        self.custom_name_label = QLabel(tr("Name"))
        self.custom_name_label.setObjectName("formKey")
        form.addRow(self.custom_name_label, self.custom_name)
        l1.addLayout(form)
        row = QHBoxLayout()
        self.slicer_edit = QLineEdit()
        browse = QPushButton(tr("Browse…"))
        browse.clicked.connect(self._browse)
        self.detect_btn = QPushButton(tr("Detect"))
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

        # ---------------- FreeCAD ----------------
        gf = QGroupBox(tr("FreeCAD"))
        lf = QVBoxLayout(gf)
        fc_help = QLabel(tr("FreeCAD files (.FCStd) are shown in 3D with the help of your installed "
                            "FreeCAD. Without it, PrintView3D shows the preview picture and the object list."))
        fc_help.setObjectName("muted")
        fc_help.setWordWrap(True)
        lf.addWidget(fc_help)
        row_f = QHBoxLayout()
        self.freecad_edit = QLineEdit(settings.get("freecad_path", ""))
        self.freecad_edit.setPlaceholderText(tr("Found automatically"))
        self.freecad_edit.textChanged.connect(self._update_freecad_status)
        row_f.addWidget(self.freecad_edit, 1)
        fb = QPushButton(tr("Browse…"))
        fb.clicked.connect(self._browse_freecad)
        row_f.addWidget(fb)
        lf.addLayout(row_f)
        self.freecad_status = QLabel()
        self.freecad_status.setObjectName("muted")
        self.freecad_status.setWordWrap(True)
        lf.addWidget(self.freecad_status)
        root.addWidget(gf)
        self._update_freecad_status()

        current_id = sl.resolve(settings, installed=self._installed)[0] or sl.SLICERS[0].id
        self._current_id = current_id
        self.slicer_combo.setCurrentIndex(max(0, self.slicer_combo.findData(current_id)))
        self._load_slicer_fields()
        self.slicer_combo.currentIndexChanged.connect(self._slicer_changed)
        self.slicer_edit.textChanged.connect(self._update_slicer_status)

        # ---------------- File associations ----------------
        g2 = QGroupBox(tr("Default program for 3D files"))
        l2 = QVBoxLayout(g2)
        if file_assoc.needs_confirmation():
            info_text = tr("Register PrintView3D so it can open .stl, .3mf and .gcode files when you "
                           "double-click them. Windows then asks you to confirm it as the default app — "
                           "that last step is done by Windows itself and can be changed back at any time.")
        else:
            info_text = tr("Add PrintView3D to your applications menu and to \"Open with\", and make it "
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
        self.reg_btn = QPushButton(tr("Register && choose as default…") if file_assoc.needs_confirmation()
                                   else tr("Register && make default"))
        self.reg_btn.setObjectName("primary")
        self.reg_btn.clicked.connect(self._register)
        self.unreg_btn = QPushButton(tr("Remove registration"))
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
        g3 = QGroupBox(tr("Viewer"))
        l3 = QVBoxLayout(g3)
        self.travel_cb = QCheckBox(tr("Show travel moves when opening G-code"))
        self.travel_cb.setChecked(bool(settings.get("show_travel")))
        self.bed_cb = QCheckBox(tr("Show build plate grid"))
        self.bed_cb.setChecked(bool(settings.get("show_bed", True)))
        l3.addWidget(self.travel_cb)
        l3.addWidget(self.bed_cb)
        root.addWidget(g3)

        # ---------------- Graphics ----------------
        g4 = QGroupBox(tr("Graphics"))
        l4 = QVBoxLayout(g4)
        gpu_name = (gpu_info or {}).get("GPU") or tr("unknown")
        self.gpu_label = QLabel(tr("Drawing with: {gpu}").format(gpu=f"<b>{gpu_name}</b>"))
        self.gpu_label.setWordWrap(True)
        l4.addWidget(self.gpu_label)
        self.gpu_cb = QCheckBox(tr("Use the high-performance graphics card (recommended on laptops)"))
        self.gpu_cb.setEnabled(gpu.is_supported())
        self.gpu_cb.setChecked(gpu.high_performance_enabled())
        self.gpu_cb.setVisible(sys.platform == "win32")
        l4.addWidget(self.gpu_cb)
        if gpu.is_supported():
            hint = tr("Takes effect after restarting PrintView3D.")
        elif sys.platform == "win32":
            hint = tr("Available in the installed PrintView3D.exe.")
        else:
            hint = tr("On laptops with two graphics chips, start PrintView3D from the applications menu "
                      "(after Register below) — the menu entry asks for the dedicated GPU — or use your "
                      "desktop's \"Launch using Dedicated Graphics Card\" option.")
        if gpu.looks_integrated(gpu_name):
            hint = tr("This looks like the built-in (slower) graphics. Tick the box and restart "
                      "for smoother rotation.") + " " + hint
        self.gpu_hint = QLabel(hint)
        self.gpu_hint.setWordWrap(True)
        self.gpu_hint.setObjectName("muted")
        l4.addWidget(self.gpu_hint)
        root.addWidget(g4)

        root.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

        self._update_assoc_status()
        self._initial_size(content)

    def _initial_size(self, content):
        """As tall as the content needs, but never taller than 90 % of the screen."""
        width = 620
        content.setFixedWidth(width - 40)            # lets wrapped labels compute their height
        need = content.sizeHint().height() + 70
        content.setMinimumWidth(0)
        content.setMaximumWidth(16777215)
        screen = (self.parent().screen() if self.parent() is not None else QApplication.primaryScreen())
        avail = screen.availableGeometry().height() if screen is not None else 900
        self.resize(width, min(need, int(avail * 0.9)))

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
            self.slicer_edit.setPlaceholderText(tr("Path to the slicer program"))
        else:
            self.slicer_edit.setText(self._paths.get(sid) or self._installed.get(sid, ""))
            self.slicer_edit.setPlaceholderText(tr("Not found automatically — use Browse… to select it"))
        self.slicer_edit.blockSignals(False)
        self._update_slicer_status()

    def _slicer_changed(self, _index):
        self._store_slicer_fields()
        self._current_id = self.slicer_combo.currentData()
        self._load_slicer_fields()

    def _display_name(self, sid: str) -> str:
        if sid == sl.CUSTOM:
            return self.custom_name.text().strip() or tr("custom slicer")
        return sl.slicer_name(sid)

    def _browse(self):
        start = (os.path.dirname(self.slicer_edit.text()) or os.environ.get("ProgramFiles", "")
                 or os.path.expanduser("~"))
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Locate {slicer}").format(slicer=self._display_name(self._current_id)),
            start, sl.program_file_filter())
        if path:
            self.slicer_edit.setText(os.path.normpath(path))

    def _browse_freecad(self):
        start = (os.path.dirname(self.freecad_edit.text()) or os.environ.get("ProgramFiles", "")
                 or os.path.expanduser("~"))
        path, _ = QFileDialog.getOpenFileName(self, tr("Locate FreeCAD"), start, sl.program_file_filter())
        if path:
            self.freecad_edit.setText(os.path.normpath(path))

    def _update_freecad_status(self, *_):
        found = fc.find_freecad(self.freecad_edit.text().strip())
        if found:
            self.freecad_status.setText("✔ " + tr("FreeCAD found: {where}").format(where=found.where))
        else:
            self.freecad_status.setText(tr("FreeCAD was not found. Install it from freecad.org "
                                           "(free), or choose its program file with Browse."))

    def _detect(self):
        sid = self._current_id
        found = sl.find_slicer(sid, "")
        if found:
            self._installed[sid] = found
            self.slicer_edit.setText(found)
        else:
            QMessageBox.information(
                self, tr("Not found"),
                tr("{slicer} could not be found automatically.").format(slicer=self._display_name(sid))
                + "\n" + tr("Use Browse… to select its program file."))

    def _update_slicer_status(self):
        txt = self.slicer_edit.text().strip()
        if not txt:
            self.slicer_status.setText(tr("No program selected."))
        elif not os.path.isfile(txt):
            self.slicer_status.setText("✖ " + tr("This file does not exist"))
        elif self._current_id != sl.CUSTOM and txt == self._installed.get(self._current_id):
            self.slicer_status.setText("✔ " + tr("Detected automatically"))
        else:
            self.slicer_status.setText("✔ " + tr("Found"))

    # --------------------------------------------------------- associations
    def _update_assoc_status(self):
        supported = file_assoc.is_supported()
        self.reg_btn.setEnabled(supported)
        self.unreg_btn.setEnabled(supported and file_assoc.is_registered())
        if not supported:
            for lab in self.assoc_labels.values():
                lab.setText(tr("Not available"))
            self.assoc_note.setText(tr("File associations are available on Windows and Linux."))
            return
        for ext, st in file_assoc.status().items():
            self.assoc_labels[ext].setText(assoc_status(st))
        notes = []
        if not file_assoc.is_frozen():
            notes.append(tr("You are running from source: registration will point to this Python "
                            "installation. For everyday use, register from the built PrintView3D program."))
        else:
            reg_cmd = file_assoc.registered_command()
            if reg_cmd and file_assoc.this_program().lower() not in reg_cmd.lower():
                notes.append(tr("The registration points to a different copy of PrintView3D. "
                                "Click Register again to point it to this one."))
        self.assoc_note.setText("\n".join(notes))

    def _register(self):
        if file_assoc.needs_confirmation():
            QMessageBox.information(
                self, tr("Almost done"),
                tr("PrintView3D will be added to \"Open with\".") + "\n\n"
                + tr("Windows Settings opens next. Set PrintView3D as the default for "
                     ".stl, .3mf and .gcode there (click each file type and choose PrintView3D)."))
        try:
            file_assoc.make_default()
        except OSError as e:
            QMessageBox.warning(self, tr("Registration failed"), str(e))
            return
        self._update_assoc_status()
        if not file_assoc.needs_confirmation():
            QMessageBox.information(
                self, tr("Done"),
                tr("PrintView3D is now in your applications menu and opens .stl, .3mf and .gcode "
                   "files when you double-click them."))

    def _unregister(self):
        if QMessageBox.question(self, tr("Remove registration"),
                                tr("Remove PrintView3D from \"Open with\" and default apps?")) != QMessageBox.Yes:
            return
        file_assoc.unregister()
        self._update_assoc_status()

    # ------------------------------------------------------------------ save
    def _save(self):
        self._store_slicer_fields()
        sid = self._current_id
        if sid == sl.CUSTOM and not os.path.isfile(self._custom.get("path", "")):
            QMessageBox.warning(self, tr("Custom slicer"), tr("Select the program file of your slicer first."))
            return
        self.settings.set("slicer_id", sid)
        self.settings.set("slicer_paths", self._paths)
        self.settings.set("custom_slicer", self._custom)
        self.settings.set("freecad_path", self.freecad_edit.text().strip())
        self.settings.set("show_travel", self.travel_cb.isChecked())
        self.settings.set("show_bed", self.bed_cb.isChecked())
        if gpu.is_supported() and self.gpu_cb.isChecked() != gpu.high_performance_enabled():
            try:
                gpu.set_high_performance(self.gpu_cb.isChecked())
                QMessageBox.information(self, tr("Restart needed"),
                                        tr("Restart PrintView3D to switch graphics card."))
            except OSError as e:
                QMessageBox.warning(self, tr("Could not change graphics setting"), str(e))
        lang = self.lang_combo.currentData()
        if lang != self.settings.get("language", "en"):
            self.settings.set("language", lang)
            # Takes effect immediately: every window re-sets its texts.
            i18n.apply_language(QApplication.instance(), lang)
        choice = self.theme_combo.currentData()
        if choice != self.settings.get("theme", "auto"):
            self.settings.set("theme", choice)
            parent = self.parent()
            if hasattr(parent, "apply_theme"):
                parent.apply_theme(choice)          # windows and the 3D view
            else:
                theme.apply_theme(QApplication.instance(), choice)
        self.accept()
