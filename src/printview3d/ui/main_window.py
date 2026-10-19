"""Main application window."""

from __future__ import annotations

import os
import threading
from typing import Optional

import numpy as np
from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QMenu, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QSlider, QSpinBox, QSplitter, QStackedWidget, QToolBar,
    QToolButton, QVBoxLayout, QWidget,
)

from .. import APP_NAME, __version__
from ..loaders import (
    FEATURES, GcodeData, ModelData, SUPPORTED_EXTENSIONS, file_kind, load_file,
    parse_gcode_text, read_embedded_gcode,
)
from ..loaders.gcode import FEATURE_INDEX
from ..gpu import renderer_info
from ..settings import Settings
from .. import slicer as sl
from .scene import Scene
from .settings_dialog import SettingsDialog

RESOURCES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")
FILE_FILTER = ("3D files (*.stl *.3mf *.gcode *.gco *.g);;STL models (*.stl);;"
               "3MF projects (*.3mf);;G-code (*.gcode *.gco *.g);;All files (*)")


def resource(name: str) -> str:
    return os.path.join(RESOURCES, name)


def _swatch(color: str, size: int = 12) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(QColor(color))
    return QIcon(pm)


class _LoadSignals(QObject):
    progress = Signal(int, float)
    done = Signal(int, object)
    failed = Signal(int, str)


class _KeySwallower(QObject):
    """Stops VTK's built-in single-letter shortcuts (wireframe, quit, ...)."""

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.KeyPress, QEvent.KeyRelease):
            return True
        return False


class MainWindow(QMainWindow):
    def __init__(self, settings: Optional[Settings] = None):
        super().__init__()
        self.settings = settings or Settings()
        self.current_path: Optional[str] = None
        self.current_kind = ""
        self.model: Optional[ModelData] = None
        self.gcode: Optional[GcodeData] = None
        self.showing_embedded = False
        self._load_token = 0

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(resource("icon.png")))
        self.resize(1320, 840)
        self.setAcceptDrops(True)

        self._signals = _LoadSignals()
        self._signals.progress.connect(self._on_progress)
        self._signals.done.connect(self._on_loaded)
        self._signals.failed.connect(self._on_failed)

        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._build_shortcuts()
        self._refresh_recent_menu()
        sl.migrate_settings(self.settings)
        self._update_slicer_button()

        self._gcode_timer = QTimer(self)
        self._gcode_timer.setSingleShot(True)
        self._gcode_timer.setInterval(15)
        self._gcode_timer.timeout.connect(self._redraw_gcode)

    # =================================================================== UI
    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(tb)

        self.act_open = QAction("Open…", self, shortcut=QKeySequence.Open, triggered=self.open_dialog)
        tb.addAction(self.act_open)

        self.recent_menu = QMenu("Recent", self)
        recent_btn = QToolButton()
        recent_btn.setText("Recent")
        recent_btn.setMenu(self.recent_menu)
        recent_btn.setPopupMode(QToolButton.InstantPopup)
        tb.addWidget(recent_btn)

        tb.addSeparator()
        self.slicer_btn = QToolButton()
        self.slicer_btn.setObjectName("slicerButton")
        self.slicer_btn.clicked.connect(lambda: self.open_in_slicer())
        # The small arrow: send the file to another slicer just once.
        self.slicer_menu = QMenu(self)
        self.slicer_menu.aboutToShow.connect(self._fill_slicer_menu)
        self.slicer_btn.setMenu(self.slicer_menu)
        self.slicer_btn.setPopupMode(QToolButton.MenuButtonPopup)
        tb.addWidget(self.slicer_btn)
        tb.addSeparator()

        self.view_actions = []
        for label, view, key in (("Fit", None, "F"), ("Iso", "iso", "1"), ("Top", "top", "2"),
                                 ("Front", "front", "3"), ("Right", "right", "4")):
            act = QAction(label, self)
            act.setToolTip(f"{label} view ({key})")
            act.triggered.connect(lambda _=False, v=view: self.set_view(v))
            tb.addAction(act)
            self.view_actions.append((act, key))

        self.act_bed = QAction("Plate", self, checkable=True)
        self.act_bed.setChecked(bool(self.settings.get("show_bed", True)))
        self.act_bed.setToolTip("Show / hide the build plate grid")
        self.act_bed.toggled.connect(self._toggle_bed)
        tb.addAction(self.act_bed)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        tb.addAction(QAction("Screenshot", self, triggered=self.save_screenshot))
        tb.addAction(QAction("Settings", self, triggered=self.open_settings))
        tb.addAction(QAction("About", self, triggered=self.show_about))

    def _build_central(self):
        from pyvistaqt import QtInteractor

        self.stack = QStackedWidget()

        # ---- welcome page ----
        welcome = QWidget()
        wl = QVBoxLayout(welcome)
        wl.addStretch(2)
        icon = QLabel()
        icon.setPixmap(QPixmap(resource("icon.png")).scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon.setAlignment(Qt.AlignCenter)
        wl.addWidget(icon)
        title = QLabel(APP_NAME)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 26px; font-weight: 600; margin-top: 8px;")
        wl.addWidget(title)
        sub = QLabel("Drop an STL, 3MF or G-code file here, or open one.")
        sub.setAlignment(Qt.AlignCenter)
        sub.setObjectName("muted")
        wl.addWidget(sub)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ob = QPushButton("Open file…")
        ob.setObjectName("primary")
        ob.setMinimumWidth(160)
        ob.clicked.connect(self.open_dialog)
        btn_row.addWidget(ob)
        btn_row.addStretch(1)
        wl.addSpacing(10)
        wl.addLayout(btn_row)
        self.welcome_recent = QVBoxLayout()
        self.welcome_recent.setAlignment(Qt.AlignHCenter)
        wl.addSpacing(18)
        wl.addLayout(self.welcome_recent)
        wl.addStretch(3)
        self.stack.addWidget(welcome)

        # ---- viewer page ----
        splitter = QSplitter(Qt.Horizontal)
        self.plotter = QtInteractor(splitter, auto_update=False)
        try:
            for key in ("q", "b", "C", "v", "Up", "Down", "plus", "minus"):
                self.plotter.clear_events_for_key(key)
        except Exception:
            pass
        self._key_filter = _KeySwallower(self)
        self.plotter.interactor.installEventFilter(self._key_filter)
        self.scene = Scene(self.plotter)
        from .camera_controls import TurntableControls
        self.controls = TurntableControls(self.plotter, self.scene, self.scene.interaction_started,
                                          self.scene.interaction_ended)
        self.scene.bed_visible = self.act_bed.isChecked()
        splitter.addWidget(self.plotter.interactor)

        self.side = QWidget()
        self.side_layout = QVBoxLayout(self.side)
        self.side_layout.setContentsMargins(10, 8, 10, 10)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self.side)
        scroll.setMinimumWidth(290)
        scroll.setMaximumWidth(420)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([1000, 310])
        self.stack.addWidget(splitter)

        self._build_side_panel()
        self.setCentralWidget(self.stack)

    def _build_side_panel(self):
        L = self.side_layout

        self.name_label = QLabel()
        self.name_label.setObjectName("fileName")
        self.name_label.setWordWrap(True)
        L.addWidget(self.name_label)
        self.kind_label = QLabel()
        self.kind_label.setObjectName("muted")
        L.addWidget(self.kind_label)

        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("background:#15181c; border-radius:6px; padding:6px;")
        L.addWidget(self.thumb_label)

        # Details
        self.details_box = QGroupBox("Details")
        self.details_form = QFormLayout(self.details_box)
        self.details_form.setLabelAlignment(Qt.AlignLeft)
        L.addWidget(self.details_box)

        # Objects (3MF / STL)
        self.objects_box = QGroupBox("Objects")
        self.objects_layout = QVBoxLayout(self.objects_box)
        L.addWidget(self.objects_box)

        # Embedded G-code (sliced 3MF)
        self.embedded_box = QGroupBox("Sliced plates")
        self.embedded_layout = QVBoxLayout(self.embedded_box)
        L.addWidget(self.embedded_box)

        # Layers (G-code)
        self.layers_box = QGroupBox("Layers")
        ll = QVBoxLayout(self.layers_box)
        self.layer_info = QLabel()
        ll.addWidget(self.layer_info)
        srow = QHBoxLayout()
        self.layer_down = QPushButton("◀")
        self.layer_down.setFixedWidth(34)
        self.layer_down.clicked.connect(lambda: self.step_layer(-1))
        self.layer_slider = QSlider(Qt.Horizontal)
        self.layer_slider.valueChanged.connect(self._on_layer_changed)
        self.layer_up = QPushButton("▶")
        self.layer_up.setFixedWidth(34)
        self.layer_up.clicked.connect(lambda: self.step_layer(1))
        srow.addWidget(self.layer_down)
        srow.addWidget(self.layer_slider, 1)
        srow.addWidget(self.layer_up)
        ll.addLayout(srow)
        row2 = QHBoxLayout()
        self.layer_spin = QSpinBox()
        self.layer_spin.valueChanged.connect(lambda v: self.layer_slider.setValue(v - 1))
        row2.addWidget(QLabel("Go to layer"))
        row2.addWidget(self.layer_spin)
        row2.addStretch(1)
        ll.addLayout(row2)
        self.only_layer_cb = QCheckBox("Show only this layer")
        self.only_layer_cb.toggled.connect(self._schedule_gcode)
        ll.addWidget(self.only_layer_cb)
        hint = QLabel("Tip: ↑ / ↓ arrow keys move through layers")
        hint.setObjectName("muted")
        ll.addWidget(hint)
        L.addWidget(self.layers_box)

        # Features (G-code)
        self.features_box = QGroupBox("Features")
        self.features_layout = QVBoxLayout(self.features_box)
        L.addWidget(self.features_box)
        self.feature_checks: dict[str, QCheckBox] = {}

        L.addStretch(1)
        self._reset_side_panel()

    def _build_statusbar(self):
        sb = self.statusBar()
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(220)
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.hide()
        sb.addPermanentWidget(self.progress)

    def _build_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.open_in_slicer)
        for act, key in self.view_actions:
            QShortcut(QKeySequence(key), self, activated=act.trigger)
        QShortcut(QKeySequence(Qt.Key_Up), self, activated=lambda: self.step_layer(1))
        QShortcut(QKeySequence(Qt.Key_Down), self, activated=lambda: self.step_layer(-1))
        QShortcut(QKeySequence(Qt.Key_PageUp), self, activated=lambda: self.step_layer(10))
        QShortcut(QKeySequence(Qt.Key_PageDown), self, activated=lambda: self.step_layer(-10))
        QShortcut(QKeySequence(Qt.Key_Home), self, activated=lambda: self.set_layer(0))
        QShortcut(QKeySequence(Qt.Key_End), self, activated=lambda: self.set_layer(10 ** 9))

    # ========================================================= side panel
    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                MainWindow._clear_layout(item.layout())

    def _reset_side_panel(self):
        self.name_label.setText("")
        self.kind_label.setText("")
        self.thumb_label.hide()
        while self.details_form.rowCount():
            self.details_form.removeRow(0)
        self._clear_layout(self.objects_layout)
        self._clear_layout(self.embedded_layout)
        self._clear_layout(self.features_layout)
        self.feature_checks = {}
        for box in (self.objects_box, self.embedded_box, self.layers_box, self.features_box):
            box.hide()

    def _add_detail(self, key: str, value: str):
        k = QLabel(key)
        k.setObjectName("formKey")
        v = QLabel(str(value))
        v.setWordWrap(True)
        v.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.details_form.addRow(k, v)

    def _set_thumbnail(self, data: Optional[bytes]):
        if not data:
            self.thumb_label.hide()
            return
        pm = QPixmap()
        if pm.loadFromData(data) and not pm.isNull() and pm.width() > 8:
            self.thumb_label.setPixmap(pm.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.thumb_label.show()
        else:
            self.thumb_label.hide()

    # ============================================================ loading
    def open_dialog(self):
        start = os.path.dirname(self.current_path) if self.current_path else ""
        if not start:
            recent = self.settings.get("recent_files", [])
            start = os.path.dirname(recent[0]) if recent else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self, "Open 3D file", start, FILE_FILTER)
        if path:
            self.load(path)

    def load(self, path: str):
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            QMessageBox.warning(self, "File not found", f"The file no longer exists:\n{path}")
            return
        kind = file_kind(path)
        if not kind:
            QMessageBox.warning(self, "Unsupported file",
                                "PrintView3D can open STL, 3MF and G-code files.")
            return
        self._load_token += 1
        token = self._load_token
        self.statusBar().showMessage(f"Loading {os.path.basename(path)}…")
        self.progress.setValue(0)
        self.progress.show()
        self.slicer_btn.setEnabled(False)

        def work():
            try:
                result = load_file(path, lambda f: self._signals.progress.emit(token, f))
                self._signals.done.emit(token, (path, kind, result))
            except Exception as e:  # noqa: BLE001 - show any error to the user
                self._signals.failed.emit(token, f"{type(e).__name__}: {e}")

        threading.Thread(target=work, daemon=True).start()

    def load_sync(self, path: str):
        """Load without a worker thread (used for --screenshot)."""
        path = os.path.abspath(path)
        self._load_token += 1
        self._on_loaded(self._load_token, (path, file_kind(path), load_file(path)))

    def _on_progress(self, token: int, frac: float):
        if token == self._load_token:
            self.progress.setValue(int(frac * 100))

    def _on_failed(self, token: int, msg: str):
        if token != self._load_token:
            return
        self.progress.hide()
        self.slicer_btn.setEnabled(True)
        self.statusBar().clearMessage()
        QMessageBox.critical(self, "Could not open file", msg)

    def _on_loaded(self, token: int, payload):
        if token != self._load_token:
            return
        if payload[0] == "__embedded__":
            self._on_embedded_loaded(token, payload)
            return
        path, kind, data = payload
        self.progress.hide()
        self.slicer_btn.setEnabled(True)
        self.current_path = path
        self.current_kind = kind
        self.showing_embedded = False
        self.settings.add_recent(path)
        self._refresh_recent_menu()
        self.setWindowTitle(f"{os.path.basename(path)} — {APP_NAME}")
        self.stack.setCurrentIndex(1)

        self.scene.clear()
        self._reset_side_panel()
        self.name_label.setText(os.path.basename(path))
        size_mb = os.path.getsize(path) / (1024 * 1024)

        if isinstance(data, GcodeData):
            self.model = None
            self._show_gcode(data, f"G-code · {size_mb:.1f} MB")
        else:
            self.model = data
            self.gcode = None
            self._show_model(data, f"{kind.upper()} · {size_mb:.1f} MB")
        self.scene.set_bed_visible(self.act_bed.isChecked())
        self.scene.set_view("iso")
        self.statusBar().showMessage(f"Opened {path}", 6000)

    # ------------------------------------------------------------- model
    def _show_model(self, m: ModelData, kind_text: str):
        self.kind_label.setText(kind_text)
        self._set_thumbnail(m.thumbnail)
        actors = self.scene.show_model(m)
        b = m.bounds()
        if b:
            self._add_detail("Size (X×Y×Z)", f"{b[1]-b[0]:.2f} × {b[3]-b[2]:.2f} × {b[5]-b[4]:.2f} mm")
        self._add_detail("Triangles", f"{m.n_triangles:,}")
        if len(m.parts) == 1:
            vol = self._mesh_volume(m.parts[0])
            if vol:
                self._add_detail("Volume", f"{vol / 1000:.2f} cm³")
        for k, v in m.meta.items():
            self._add_detail(k, v)

        if len(m.parts) > 1:
            for i, (part, actor) in enumerate(zip(m.parts, actors)):
                cb = QCheckBox(f"{part.name}  ({part.n_triangles:,} tris)")
                cb.setIcon(_swatch(Scene.model_color(i, len(m.parts))))
                cb.setChecked(True)
                cb.toggled.connect(lambda on, a=actor: (a.SetVisibility(on), self.plotter.render()))
                self.objects_layout.addWidget(cb)
            self.objects_box.setTitle(f"Objects ({len(m.parts)})")
            self.objects_box.show()

        if m.embedded_gcode:
            info = QLabel("This project contains sliced G-code.")
            info.setObjectName("muted")
            self.embedded_layout.addWidget(info)
            for member in m.embedded_gcode:
                plate = os.path.splitext(os.path.basename(member))[0].replace("_", " ").title()
                b = QPushButton(f"Show toolpaths — {plate}")
                b.clicked.connect(lambda _=False, mem=member: self._show_embedded(mem))
                self.embedded_layout.addWidget(b)
            self.embedded_box.show()

    @staticmethod
    def _mesh_volume(part) -> float:
        v, f = part.vertices.astype(np.float64), part.faces
        if len(f) == 0:
            return 0.0
        a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
        vol = float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)
        return abs(vol)

    def _show_embedded(self, member: str):
        path = self.current_path
        if not path:
            return
        self.statusBar().showMessage("Reading sliced G-code from project…")
        self.progress.setValue(0)
        self.progress.show()
        self._load_token += 1
        token = self._load_token

        def work():
            try:
                text = read_embedded_gcode(path, member)
                g = parse_gcode_text(text, lambda f: self._signals.progress.emit(token, f))
                self._signals.done.emit(token, ("__embedded__", member, g))
            except Exception as e:  # noqa: BLE001
                self._signals.failed.emit(token, f"{type(e).__name__}: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _on_embedded_loaded(self, token: int, payload):
        _, member, g = payload
        self.progress.hide()
        self.showing_embedded = True
        self.scene.clear()
        self._reset_side_panel()
        self.name_label.setText(os.path.basename(self.current_path or ""))
        plate = os.path.splitext(os.path.basename(member))[0].replace("_", " ").title()
        self._show_gcode(g, f"Sliced toolpaths · {plate}")
        back = QPushButton("◀ Back to 3D model")
        back.clicked.connect(lambda: self.load(self.current_path))
        self.embedded_layout.addWidget(back)
        self.embedded_box.setTitle("Project")
        self.embedded_box.show()
        self.scene.set_bed_visible(self.act_bed.isChecked())
        self.scene.set_view("iso")
        self.statusBar().clearMessage()

    # ------------------------------------------------------------- gcode
    def _show_gcode(self, g: GcodeData, kind_text: str):
        self.gcode = g
        self.kind_label.setText(kind_text)
        self._set_thumbnail(g.thumbnail)
        self.scene.show_gcode(g)

        b = g.extrusion_bounds
        if b:
            self._add_detail("Print size", f"{b[1]-b[0]:.1f} × {b[3]-b[2]:.1f} × {b[5]:.2f} mm")
        self._add_detail("Layers", f"{g.n_layers:,}")
        for key in ("Print time", "Filament (g)", "Filament (mm)", "Filament type", "Layer height",
                    "Nozzle", "Printer", "Printer profile", "Slicer"):
            if key in g.meta:
                self._add_detail(key, g.meta[key])

        if g.n_layers == 0:
            self.statusBar().showMessage("No printable moves found in this G-code.", 8000)
            return

        # features
        show_travel = bool(self.settings.get("show_travel"))
        for key, label, color in FEATURES:
            if key not in g.feature_counts:
                continue
            cb = QCheckBox(label)
            cb.setIcon(_swatch(color))
            cb.setChecked(show_travel if key == "travel" else True)
            cb.toggled.connect(self._schedule_gcode)
            self.features_layout.addWidget(cb)
            self.feature_checks[key] = cb
        row = QHBoxLayout()
        all_b = QPushButton("All")
        all_b.clicked.connect(lambda: self._set_all_features(True))
        none_b = QPushButton("None")
        none_b.clicked.connect(lambda: self._set_all_features(False))
        row.addWidget(all_b)
        row.addWidget(none_b)
        row.addStretch(1)
        self.features_layout.addLayout(row)
        self.features_box.show()

        # layers
        self.layer_slider.blockSignals(True)
        self.layer_spin.blockSignals(True)
        self.layer_slider.setRange(0, g.n_layers - 1)
        self.layer_slider.setValue(g.n_layers - 1)
        self.layer_spin.setRange(1, g.n_layers)
        self.layer_spin.setValue(g.n_layers)
        self.layer_slider.blockSignals(False)
        self.layer_spin.blockSignals(False)
        self.only_layer_cb.blockSignals(True)
        self.only_layer_cb.setChecked(False)
        self.only_layer_cb.blockSignals(False)
        self.layers_box.show()
        self._update_layer_label()
        self._redraw_gcode()

    def _set_all_features(self, on: bool):
        for key, cb in self.feature_checks.items():
            if key == "travel" and on:
                continue
            cb.blockSignals(True)
            cb.setChecked(on)
            cb.blockSignals(False)
        self._schedule_gcode()

    def _visible_features(self) -> np.ndarray:
        vis = np.zeros(len(FEATURES), dtype=bool)
        for key, cb in self.feature_checks.items():
            vis[FEATURE_INDEX[key]] = cb.isChecked()
        return vis

    def _on_layer_changed(self, v: int):
        self.layer_spin.blockSignals(True)
        self.layer_spin.setValue(v + 1)
        self.layer_spin.blockSignals(False)
        self._update_layer_label()
        self._schedule_gcode()

    def _update_layer_label(self):
        g = self.gcode
        if g is None or g.n_layers == 0:
            self.layer_info.setText("")
            return
        i = self.layer_slider.value()
        self.layer_info.setText(f"<b>Layer {i + 1}</b> of {g.n_layers}  ·  Z = {g.layer_z[i]:.2f} mm")

    def _schedule_gcode(self, *_):
        self._gcode_timer.start()

    def _redraw_gcode(self):
        if self.gcode is None or self.gcode.n_layers == 0:
            return
        self.scene.update_gcode(self.layer_slider.value(), self.only_layer_cb.isChecked(),
                                self._visible_features())

    def step_layer(self, delta: int):
        if self.gcode is not None and self.layers_box.isVisible():
            self.set_layer(self.layer_slider.value() + delta)

    def set_layer(self, value: int):
        if self.gcode is not None and self.layers_box.isVisible():
            self.layer_slider.setValue(max(0, min(value, self.layer_slider.maximum())))

    # ============================================================ actions
    def set_view(self, view: Optional[str]):
        if self.stack.currentIndex() != 1:
            return
        self.scene.set_view(view or self.scene._view)

    def _toggle_bed(self, on: bool):
        self.scene.set_bed_visible(on)
        self.settings.set("show_bed", on)
        self.plotter.render()

    # ------------------------------------------------------------ slicer
    def _update_slicer_button(self):
        sid, name, _ = sl.resolve(self.settings)
        if sid:
            self.slicer_btn.setText(f"Open in {name}")
            self.slicer_btn.setToolTip(f"Open this file in {name} (Ctrl+P). "
                                       "Use the arrow to pick another slicer.")
        else:
            self.slicer_btn.setText("Open in slicer")
            self.slicer_btn.setToolTip("No slicer found yet — choose one in Settings (Ctrl+P)")

    def _fill_slicer_menu(self):
        self.slicer_menu.clear()
        default_id = sl.resolve(self.settings)[0]
        installed = sl.detect_installed(self.settings.get("slicer_paths") or {})
        custom = self.settings.get("custom_slicer") or {}
        entries = [(s.id, s.name) for s in sl.SLICERS if s.id in installed]
        if os.path.isfile(custom.get("path", "")):
            entries.append((sl.CUSTOM, sl.slicer_name(sl.CUSTOM, custom.get("name", ""))))
        if not entries:
            a = self.slicer_menu.addAction("No slicers found")
            a.setEnabled(False)
        for sid, name in entries:
            label = f"Open in {name}" + ("   (default)" if sid == default_id else "")
            self.slicer_menu.addAction(label, lambda s_id=sid: self.open_in_slicer(s_id))
        self.slicer_menu.addSeparator()
        self.slicer_menu.addAction("Choose default slicer…", self.open_settings)

    def open_in_slicer(self, slicer_id: Optional[str] = None):
        sid, name, exe = sl.resolve(self.settings, slicer_id)
        if not sid:
            r = QMessageBox.question(
                self, "No slicer found",
                "No supported slicer was found on this computer.\n\n"
                "Open Settings to choose your slicer program?")
            if r == QMessageBox.Yes:
                self.open_settings()
            return
        if not exe:
            r = QMessageBox.question(
                self, f"{name} not found",
                f"{name} could not be found automatically.\n\n"
                f"Do you want to locate its program file yourself?")
            if r != QMessageBox.Yes:
                return
            path, _ = QFileDialog.getOpenFileName(self, f"Locate {name}",
                                                  os.environ.get("ProgramFiles", ""),
                                                  sl.program_file_filter())
            if not path:
                return
            exe = os.path.normpath(path)
            if sid == sl.CUSTOM:
                custom = dict(self.settings.get("custom_slicer") or {})
                custom["path"] = exe
                self.settings.set("custom_slicer", custom)
            else:
                paths = dict(self.settings.get("slicer_paths") or {})
                paths[sid] = exe
                self.settings.set("slicer_paths", paths)
        try:
            sl.open_in_slicer(exe, self.current_path)
        except OSError as e:
            QMessageBox.critical(self, f"Could not start {name}", str(e))
            return
        what = os.path.basename(self.current_path) if self.current_path else name
        self.statusBar().showMessage(f"Opening {what} in {name}…", 6000)

    def save_screenshot(self):
        if self.stack.currentIndex() != 1:
            return
        base = os.path.splitext(os.path.basename(self.current_path or "view"))[0]
        start = os.path.join(os.path.dirname(self.current_path or os.path.expanduser("~")), base + ".png")
        path, _ = QFileDialog.getSaveFileName(self, "Save screenshot", start, "PNG image (*.png)")
        if path:
            self.plotter.screenshot(path)
            self.statusBar().showMessage(f"Saved {path}", 6000)

    def open_settings(self):
        dlg = SettingsDialog(self.settings, self, renderer_info(self.plotter))
        if dlg.exec():
            self._update_slicer_button()
            show_bed = bool(self.settings.get("show_bed", True))
            if self.act_bed.isChecked() != show_bed:
                self.act_bed.setChecked(show_bed)

    def show_about(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<h3>{APP_NAME} {__version__}</h3>"
            "<p>A lightweight viewer for STL, 3MF and G-code files, with one-click "
            "hand-off to your slicer (Creality Print, OrcaSlicer, Bambu Studio, PrusaSlicer, "
            "Cura and others).</p>"
            "<p>Open source under the MIT License.</p>"
            "<p>Built with Python, Qt (PySide6) and PyVista / VTK.</p>"
            + "".join(f"<br><small>{k}: {v}</small>" for k, v in renderer_info(self.plotter).items()))

    # ------------------------------------------------------------- recent
    def _refresh_recent_menu(self):
        self.recent_menu.clear()
        self._clear_layout(self.welcome_recent)
        recent = [p for p in self.settings.get("recent_files", []) if os.path.isfile(p)]
        if not recent:
            a = self.recent_menu.addAction("No recent files")
            a.setEnabled(False)
        else:
            hdr = QLabel("Recent files")
            hdr.setObjectName("muted")
            hdr.setAlignment(Qt.AlignCenter)
            self.welcome_recent.addWidget(hdr)
        for i, p in enumerate(recent):
            self.recent_menu.addAction(f"{os.path.basename(p)}   —   {os.path.dirname(p)}",
                                       lambda path=p: self.load(path))
            if i < 6:
                b = QPushButton(os.path.basename(p))
                b.setToolTip(p)
                b.setFlat(True)
                b.setStyleSheet("QPushButton { color: #7cc7c4; border: none; background: transparent; }"
                                "QPushButton:hover { text-decoration: underline; }")
                b.clicked.connect(lambda _=False, path=p: self.load(path))
                self.welcome_recent.addWidget(b)
        if recent:
            self.recent_menu.addSeparator()
            self.recent_menu.addAction("Clear list", self._clear_recent)

    def _clear_recent(self):
        self.settings.clear_recent()
        self._refresh_recent_menu()

    # ------------------------------------------------------------ drag & drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            for u in e.mimeData().urls():
                if u.toLocalFile().lower().endswith(SUPPORTED_EXTENSIONS):
                    e.acceptProposedAction()
                    return
        e.ignore()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if p.lower().endswith(SUPPORTED_EXTENSIONS):
                self.load(p)
                return

    def closeEvent(self, e):
        try:
            self.plotter.close()
        except Exception:
            pass
        super().closeEvent(e)
