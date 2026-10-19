#!/usr/bin/env bash
# ============================================================
#  PrintView3D - install for the current user (no root needed)
#  Copies the AppImage to ~/Applications and adds PrintView3D to the
#  applications menu and to "Open With" for .stl / .3mf / .gcode.
#  Usage: ./install_linux.sh [path/to/PrintView3D-x86_64.AppImage]
# ============================================================
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

SRC="${1:-}"
if [[ -z "$SRC" ]]; then
    SRC="$(ls -1 dist/PrintView3D-*.AppImage PrintView3D-*.AppImage 2>/dev/null | head -n1 || true)"
fi
if [[ -z "$SRC" || ! -f "$SRC" ]]; then
    echo "[ERROR] PrintView3D AppImage not found."
    echo "        Download it from the releases page, or run ./build_linux.sh first."
    exit 1
fi

DEST="$HOME/Applications/PrintView3D.AppImage"
mkdir -p "$HOME/Applications"
cp -f "$SRC" "$DEST"
chmod +x "$DEST"
echo "Installed to $DEST"

# Adds the menu entry and "Open With" (the AppImage knows its own path).
"$DEST" --register || APPIMAGE_EXTRACT_AND_RUN=1 "$DEST" --register
echo
echo "PrintView3D is now in your applications menu."
echo "To open .stl / .3mf / .gcode files with it by double-click, use"
echo "Settings -> Register & make default inside PrintView3D."
