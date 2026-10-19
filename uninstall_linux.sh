#!/usr/bin/env bash
# PrintView3D - remove the per-user installation (menu entry, file types, AppImage).
set -uo pipefail
DEST="$HOME/Applications/PrintView3D.AppImage"
if [[ -x "$DEST" ]]; then
    "$DEST" --unregister || APPIMAGE_EXTRACT_AND_RUN=1 "$DEST" --unregister
    rm -f "$DEST"
fi
read -r -p "Also delete your PrintView3D settings (recent files, slicer choice)? [y/N] " a
if [[ "$a" =~ ^[Yy] ]]; then
    rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/printview3d"
fi
echo "PrintView3D has been removed."
