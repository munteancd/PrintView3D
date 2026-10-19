#!/usr/bin/env bash
# Run PrintView3D directly from the source code (for development/testing).
# Run ./build_linux.sh --no-appimage once first so the .venv folder exists.
cd "$(dirname "$(readlink -f "$0")")"
if [[ ! -x .venv/bin/python ]]; then
    echo "Run ./build_linux.sh first to set up the environment."
    exit 1
fi
PYTHONPATH="$PWD/src" exec .venv/bin/python -m printview3d "$@"
