"""Settings dialog: a sidebar with one page per topic.

Language · Appearance · Slicer · FreeCAD · Files (default program) · Viewer (and graphics) ·
Updates · About. MainWindow.open_settings(page="updates") opens a given page.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QDateTime, QLocale, QSize, Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from .. import APP_NAME, __version__, file_assoc, gpu, i18n
from .. import updates as up
from .. import freecad as fc
from .. import slicer as sl
from ..i18n import tr
from . import theme
from . import update_ui
from .labels import assoc_status

PAGES = ["language", "appearance", "slicer", "freecad", "files", "viewer", "updates", "about"]


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None, gpu_info=None, page: str = ""):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(tr("Settings"))
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        outer = QVBoxLayout(self)
        body = QHBoxLayout()
        outer.addLayout(body, 1)
        self.nav = QListWidget()
        self.nav.setObjectName("settingsNav")
        self.nav.setIconSize(QSize(20, 20))
        self.nav.setFixedWidth(200)
        self.pages = QStackedWidget()
        body.addWidget(self.nav)
        body.addWidget(self.pages, 1)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self._page_keys: list[str] = []

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
        self._add_page("language", tr("Language"), [g0])

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
        self._add_page("appearance", tr("Appearance"), [ga])

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
        self._add_page("slicer", tr("Slicer"), [g1])

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
        self._add_page("freecad", tr("FreeCAD"), [gf])
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
        self._add_page("files", tr("Files"), [g2])

        # ---------------- Viewer ----------------
        g3 = QGroupBox(tr("Viewer"))
        l3 = QVBoxLayout(g3)
        self.travel_cb = QCheckBox(tr("Show travel moves when opening G-code"))
        self.travel_cb.setChecked(bool(settings.get("show_travel")))
        self.bed_cb = QCheckBox(tr("Show build plate grid"))
        self.bed_cb.setChecked(bool(settings.get("show_bed", True)))
        l3.addWidget(self.travel_cb)
        l3.addWidget(self.bed_cb)

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
                      "(after Register on the Files page) — the menu entry asks for the dedicated GPU — or "
                      "use your desktop's \"Launch using Dedicated Graphics Card\" option.")
        if gpu.looks_integrated(gpu_name):
            hint = tr("This looks like the built-in (slower) graphics. Tick the box and restart "
                      "for smoother rotation.") + " " + hint
        self.gpu_hint = QLabel(hint)
        self.gpu_hint.setWordWrap(True)
        self.gpu_hint.setObjectName("muted")
        l4.addWidget(self.gpu_hint)
        self._add_page("viewer", tr("Viewer"), [g3, g4], keep_titles=True)

        self._add_page("updates", tr("Updates"), [self._build_updates()])
        self._add_page("about", tr("About"), [self._build_about(gpu_info)])

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

        self._update_assoc_status()
        self._refresh_updates()
        self.nav.setCurrentRow(self._page_keys.index(page) if page in self._page_keys else 0)
        self._initial_size()

    # ---------------------------------------------------------------- pages
    def _add_page(self, key: str, title: str, widgets: list, keep_titles: bool = False):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(16, 0, 6, 0)
        head = QLabel(title)
        head.setObjectName("pageTitle")
        v.addWidget(head)
        for w in widgets:
            if isinstance(w, QGroupBox) and not keep_titles:
                w.setTitle("")                          # the page title already says it
            v.addWidget(w)
        v.addStretch(1)
        scroll = QScrollArea()                          # long pages scroll on small screens
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        self.pages.addWidget(scroll)
        item = QListWidgetItem(theme.nav_icon(key), title)
        item.setData(Qt.UserRole, key)
        self.nav.addItem(item)
        self._page_keys.append(key)

    def _initial_size(self):
        screen = (self.parent().screen() if self.parent() is not None else QApplication.primaryScreen())
        avail = screen.availableGeometry() if screen is not None else None
        w, h = 860, 580
        if avail is not None:
            w, h = min(w, int(avail.width() * 0.9)), min(h, int(avail.height() * 0.9))
        self.resize(w, h)

    def show_page(self, key: str):
        if key in self._page_keys:
            self.nav.setCurrentRow(self._page_keys.index(key))

    # -------------------------------------------------------------- updates
    def _build_updates(self) -> QGroupBox:
        g = QGroupBox()
        v = QVBoxLayout(g)
        self.upd_version = QLabel()
        v.addWidget(self.upd_version)
        self.upd_status = QLabel()
        self.upd_status.setObjectName("muted")
        self.upd_status.setWordWrap(True)
        v.addWidget(self.upd_status)
        row = QHBoxLayout()
        self.upd_install = QPushButton(update_ui.install_button_text())
        self.upd_install.setObjectName("primary")
        self.upd_install.clicked.connect(self._install_update)
        self.upd_notes = QPushButton(tr("What's new"))
        self.upd_notes.clicked.connect(lambda: self._available and update_ui.show_whats_new(self, self._available))
        self.upd_skip = QPushButton(tr("Skip this version"))
        self.upd_skip.clicked.connect(self._skip_update)
        self.upd_check = QPushButton(tr("Check for updates now"))
        self.upd_check.clicked.connect(self._check_now)
        for b in (self.upd_install, self.upd_notes, self.upd_skip, self.upd_check):
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        v.addSpacing(6)
        self.upd_auto = QCheckBox(tr("Check for updates automatically (once a day)"))
        self.upd_auto.setChecked(up.auto_check_enabled(self.settings))
        v.addWidget(self.upd_auto)
        note = QLabel(tr("Only asks GitHub for the newest version number. No personal data or files "
                         "are sent.") + f' <a href="{up.PRIVACY_URL}">' + tr("Read more") + "</a>")
        note.setObjectName("muted")
        note.setWordWrap(True)
        note.setOpenExternalLinks(True)
        v.addWidget(note)
        if up.install_kind() != "installer":
            how = QLabel(tr("This copy of PrintView3D is not the installed Windows version, so updates "
                            "open the download page."))
            how.setObjectName("muted")
            how.setWordWrap(True)
            v.addWidget(how)
        self._checker = update_ui.make_checker(self.settings, self)
        self._checker.finished.connect(self._check_done)
        return g

    def _refresh_updates(self, checking: bool = False):
        self._available = up.available(self.settings)
        rel = self._available
        last = float(self.settings.get("update_last_check") or 0)
        when = self._when(last) if last else tr("never")
        if rel:
            self.upd_version.setText(f'<span style="color:{theme.UPDATE_DOT}">●</span>&nbsp; '
                                     + tr("<b>Version {new} is available</b> (you have {current})").format(
                                         new=rel.version, current=__version__))
        else:
            self.upd_version.setText(tr("You have version {version}").format(version=f"<b>{__version__}</b>"))
        if checking:
            self.upd_status.setText(tr("Checking…"))
        elif rel:
            self.upd_status.setText(tr("Last checked: {when}").format(when=when))
        elif last:
            self.upd_status.setText("✔ " + tr("You are up to date · last checked {when}").format(when=when))
        else:
            self.upd_status.setText(tr("Not checked yet."))
        for b in (self.upd_install, self.upd_notes, self.upd_skip):
            b.setVisible(bool(rel))
        self.upd_check.setEnabled(not checking)
        row = self._page_keys.index("updates") if "updates" in self._page_keys else -1
        if row >= 0:
            self.nav.item(row).setIcon(theme.nav_icon("updates", dot=bool(rel)))

    @staticmethod
    def _when(ts: float) -> str:
        """'today 14:02' or '14 Nov 2026, 14:02' in the user's language."""
        dt = QDateTime.fromSecsSinceEpoch(int(ts))
        loc = QLocale()
        hm = loc.toString(dt.time(), "HH:mm")
        if dt.date() == QDateTime.currentDateTime().date():
            return tr("today {time}").format(time=hm)
        return loc.toString(dt.date(), "d MMM yyyy") + ", " + hm

    def _check_now(self):
        self._refresh_updates(checking=True)
        self._checker.start()

    def _check_done(self, rel, err):
        self._refresh_updates()
        if err:
            self.upd_status.setText(tr("Could not check for updates: {error}").format(error=err))
        parent = self.parent()
        if hasattr(parent, "refresh_update_badge"):
            parent.refresh_update_badge()

    def _skip_update(self):
        if self._available:
            self.settings.set("update_skip", self._available.version)
        self._refresh_updates()
        parent = self.parent()
        if hasattr(parent, "refresh_update_badge"):
            parent.refresh_update_badge()

    def _install_update(self):
        if self._available:
            self._save_update_choice()
            update_ui.install(self, self._available)

    def _save_update_choice(self):
        self.settings.set("update_check", self.upd_auto.isChecked())

    # ---------------------------------------------------------------- about
    def _build_about(self, gpu_info) -> QGroupBox:
        g = QGroupBox()
        v = QVBoxLayout(g)
        v.addWidget(QLabel(f"<b>{APP_NAME} {__version__}</b>"))
        about = QLabel(tr("A lightweight viewer for STL, 3MF and G-code files, with one-click "
                          "hand-off to your slicer (Creality Print, OrcaSlicer, Bambu Studio, "
                          "PrusaSlicer, Cura and others).") + "<br><br>"
                       + tr("Open source under the MIT License.") + "<br>"
                       + f'<a href="https://github.com/{up.REPO}">github.com/{up.REPO}</a>')
        about.setWordWrap(True)
        about.setOpenExternalLinks(True)
        v.addWidget(about)
        built = QLabel(tr("Built with Python, Qt (PySide6) and PyVista / VTK.") + "<br>"
                       + "<br>".join(f"{k}: {val}" for k, val in (gpu_info or {}).items()))
        built.setObjectName("muted")
        built.setWordWrap(True)
        v.addWidget(built)
        return g

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
        self._save_update_choice()
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
