"""Make the winget manifests for a PrintView3D release (Windows Package Manager).

    python tools/winget.py 0.14.3 out/winget        # reads the release from GitHub
    python tools/winget.py 0.14.3 out/winget --url URL --sha256 HASH --date 2026-10-21

Writes the three files winget wants (version, installer, defaultLocale) in
out/winget/manifests/s/sevagjb/PrintView3D/<version>/. The GitHub Action
.github/workflows/winget.yml sends them to microsoft/winget-pkgs after each release.
Only the standard library is used, so it runs on any CI machine.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request

REPO = "sevagjb/PrintView3D"
PACKAGE_ID = "sevagjb.PrintView3D"
MANIFEST_VERSION = "1.9.0"
SETUP_ASSET = "PrintView3D-Setup.exe"
# Inno Setup's entry in "Apps & features": the installer's fixed AppId + "_is1".
# winget uses it to see that PrintView3D is installed (for winget upgrade / uninstall).
PRODUCT_CODE = "{f46ac51f-055b-41dc-be29-5f0191feaf3d}_is1"
FILE_EXTENSIONS = ["3mf", "gco", "gcode", "glb", "gltf", "obj", "off", "ply", "step", "stl", "stp"]
TAGS = ["3d-printing", "3mf", "cad", "freecad", "g-code", "gcode", "gltf", "obj", "slicer", "step",
        "stl", "viewer"]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def release_info(version: str) -> dict:
    """URL, SHA-256 and date of the Setup.exe of release v<version>, from the GitHub API."""
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/tags/v{version}",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "PrintView3D"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        rel = json.load(r)
    for a in rel.get("assets", []):
        if a["name"] == SETUP_ASSET:
            digest = a.get("digest") or ""
            if not digest.startswith("sha256:"):
                raise SystemExit(f"{SETUP_ASSET} of v{version} has no SHA-256 on GitHub")
            return {"url": a["browser_download_url"], "sha256": digest.split(":", 1)[1],
                    "date": rel["published_at"][:10]}
    raise SystemExit(f"v{version} has no {SETUP_ASSET}")


def _q(s: str) -> str:
    """A YAML string in double quotes."""
    return json.dumps(s, ensure_ascii=False)


def _list(items) -> str:
    return "\n".join(f"- {i}" for i in items)


def manifests(version: str, url: str, sha256: str, date: str) -> dict[str, str]:
    head = (f"# Created by PrintView3D's tools/winget.py\n"
            f"# yaml-language-server: $schema=https://aka.ms/winget-manifest.{{}}.{MANIFEST_VERSION}.schema.json\n\n")
    common = f"PackageIdentifier: {PACKAGE_ID}\nPackageVersion: {version}\n"
    tail = f"ManifestType: {{}}\nManifestVersion: {MANIFEST_VERSION}\n"
    version_yaml = (head.format("version") + common + "DefaultLocale: en-US\n" + tail.format("version"))
    installer_yaml = (
        head.format("installer") + common
        + "InstallerLocale: en-US\n"
        + "InstallerType: inno\n"
        + "Scope: user\n"                                  # per user, no administrator rights
        + "InstallModes:\n- interactive\n- silent\n- silentWithProgress\n"
        + "UpgradeBehavior: install\n"
        + f"ProductCode: {_q(PRODUCT_CODE)}\n"
        + f"ReleaseDate: {date}\n"
        # Quoted: in YAML a bare "off" means false.
        + "FileExtensions:\n" + _list(_q(e) for e in FILE_EXTENSIONS) + "\n"
        + "AppsAndFeaturesEntries:\n"
        + f"- DisplayName: PrintView3D\n  Publisher: PrintView3D contributors\n  DisplayVersion: {version}\n"
        + f"  ProductCode: {_q(PRODUCT_CODE)}\n"
        + "Installers:\n"
        + f"- Architecture: x64\n  InstallerUrl: {url}\n  InstallerSha256: {sha256.upper()}\n"
        + tail.format("installer"))
    locale_yaml = (
        head.format("defaultLocale") + common
        + "PackageLocale: en-US\n"
        + "Publisher: PrintView3D contributors\n"
        + f"PublisherUrl: https://github.com/{REPO}\n"
        + f"PublisherSupportUrl: https://github.com/{REPO}/issues\n"
        + "Author: Sevag Barsoumian\n"
        + "PackageName: PrintView3D\n"
        + f"PackageUrl: https://github.com/{REPO}\n"
        + "License: MIT\n"
        + f"LicenseUrl: https://github.com/{REPO}/blob/main/LICENSE\n"
        + "ShortDescription: Free viewer for STL, 3MF, G-code, FreeCAD, STEP, OBJ and glTF files with one-click "
          "hand-off to your slicer.\n"
        + "Description: |-\n"
        + "  PrintView3D is a fast, free viewer made for 3D printing. It shows models and sliced G-code\n"
        + "  (toolpaths by type, layer slider, print time and filament use), every object of a 3MF project,\n"
        + "  FreeCAD and STEP files (with your installed FreeCAD), and OBJ, PLY, OFF and glTF models.\n"
        + "  One click opens the file in Creality Print, OrcaSlicer, Bambu Studio, PrusaSlicer, Cura and\n"
        + "  others. Includes File Explorer thumbnails and is available in English, Arabic, Dutch, German,\n"
        + "  French and Spanish.\n"
        + "Moniker: printview3d\n"
        + "Tags:\n" + _list(TAGS) + "\n"
        + f"ReleaseNotesUrl: https://github.com/{REPO}/releases/tag/v{version}\n"
        + tail.format("defaultLocale"))
    return {f"{PACKAGE_ID}.yaml": version_yaml,
            f"{PACKAGE_ID}.installer.yaml": installer_yaml,
            f"{PACKAGE_ID}.locale.en-US.yaml": locale_yaml}


def write(version: str, out_dir: str, info: dict) -> str:
    folder = os.path.join(out_dir, "manifests", PACKAGE_ID[0].lower(), *PACKAGE_ID.split("."), version)
    os.makedirs(folder, exist_ok=True)
    for name, text in manifests(version, info["url"], info["sha256"], info["date"]).items():
        with open(os.path.join(folder, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return folder


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Make winget manifests for a PrintView3D release")
    p.add_argument("version", help="e.g. 0.14.3 (default: the version in src/printview3d/__init__.py)", nargs="?")
    p.add_argument("out_dir")
    p.add_argument("--url")
    p.add_argument("--sha256")
    p.add_argument("--date")
    a = p.parse_args(argv)
    version = a.version or re.search(r'__version__ = "(.+?)"', open(
        os.path.join(ROOT, "src", "printview3d", "__init__.py"), encoding="utf-8").read()).group(1)
    info = ({"url": a.url, "sha256": a.sha256, "date": a.date} if a.url and a.sha256 and a.date
            else release_info(version))
    print(write(version, a.out_dir, info))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
