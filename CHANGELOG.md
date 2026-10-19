# Changelog

## 0.4.0
- **Linux support**: a single-file AppImage that runs on most distributions (Ubuntu 22.04+,
  Debian 12+, Fedora 36+, Mint, Arch, …), built and tested automatically.
- Slicers on Linux are found automatically as AppImages (`~/Applications`, `~/Downloads`, `/opt`…),
  Flatpaks, Snaps, distribution packages and menu entries.
- Linux desktop integration: applications-menu entry, "Open With" and default app for STL, 3MF and
  G-code (Settings → Register & make default), with a hint to use the dedicated GPU.
- Wayland desktops are supported (PrintView3D runs through XWayland automatically).
- Slicers started from PrintView3D get a clean environment, so the packaged app's own libraries
  can't interfere with them.
- New command-line options `--register` and `--send-to-slicer [id]`; settings follow the XDG /
  macOS conventions.
- macOS: code is ready; a Mac build is available on request.

## 0.3.0
- Choose your slicer: Creality Print, OrcaSlicer, Bambu Studio, PrusaSlicer, UltiMaker Cura,
  Elegoo Slicer, Anycubic Slicer Next, or any other program (Custom). Installed slicers are
  detected automatically.
- The button shows the chosen slicer ("Open in OrcaSlicer"); its ▾ arrow opens the file in
  another installed slicer once, without changing the default.
- If no default is chosen, the first installed slicer is used instead of showing an error.
- Settings from earlier versions (Creality Print path) are carried over automatically.
- Tests no longer depend on which slicers are installed on the build PC.
- Demo files in `examples/`, new README with screenshots and a step-by-step build guide.

## 0.2.1
- Rotation follows the mouse without lag: mouse moves are coalesced into one redraw per
  frame instead of one redraw per mouse event (high-rate mice flooded the renderer).
- Press on the model and drag: it rotates around the exact point under the cursor.
  Press on empty space: it rotates around the model's centre. No more wandering pivot after zooming.
- From below, the plate surface and fine grid are hidden (outline and main grid lines stay),
  instead of relying on transparency, which some graphics drivers did not draw correctly.

## 0.2.0
- New slicer-style camera: left-drag orbits with Z always up (no tumbling/rolling),
  right/middle-drag pans, wheel zooms towards the cursor.
- G-code lines are drawn in a lighter mode while rotating, for smoother movement.
- Build plate becomes see-through when viewed from below, so the underside of the part is visible.
- Grid no longer flickers against the bottom face of the model.
- Settings > Graphics shows which GPU is used and can switch PrintView3D to the
  high-performance GPU on dual-GPU laptops. About shows the GPU too.

## 0.1.1
- Fix: 3MF files that use undeclared XML namespace prefixes (e.g. `p:`) failed with
  "ParseError: unbound prefix". They are now repaired while loading.

## 0.1.0 — first version
- View STL (binary + ASCII), 3MF (incl. Creality Print / OrcaSlicer multi-file projects) and G-code
- G-code: layer slider, "only this layer", feature colouring and filters, travel moves, arcs (G2/G3)
- Reads print time, filament use, printer, bed size and the embedded thumbnail from G-code
- 3MF: per-object visibility, project settings, thumbnail, and preview of sliced plates stored inside the project
- "Open in Creality Print" button (Ctrl+P) with automatic detection of the install
- Settings: register as the default app for .stl / .3mf / .gcode (per user, reversible)
- Drag & drop, recent files, screenshots, dark theme
