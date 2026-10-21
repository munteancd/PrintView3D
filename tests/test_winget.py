"""winget manifests (tools/winget.py): complete, valid YAML, and the values winget relies on."""

import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))

import winget  # noqa: E402

INFO = {"url": "https://github.com/sevagjb/PrintView3D/releases/download/v1.2.3/PrintView3D-Setup.exe",
        "sha256": "ab" * 32, "date": "2026-10-21"}


def load(tmp_path):
    folder = winget.write("1.2.3", str(tmp_path), INFO)
    assert folder.replace(os.sep, "/").endswith("manifests/s/sevagjb/PrintView3D/1.2.3")
    return {name: yaml.safe_load(open(os.path.join(folder, name), encoding="utf-8")) for name in os.listdir(folder)}


def test_three_manifests_same_package_and_version(tmp_path):
    docs = load(tmp_path)
    assert set(docs) == {"sevagjb.PrintView3D.yaml", "sevagjb.PrintView3D.installer.yaml",
                         "sevagjb.PrintView3D.locale.en-US.yaml"}
    for d in docs.values():
        assert d["PackageIdentifier"] == "sevagjb.PrintView3D" and str(d["PackageVersion"]) == "1.2.3"
        assert d["ManifestVersion"] == winget.MANIFEST_VERSION
    assert {d["ManifestType"] for d in docs.values()} == {"version", "installer", "defaultLocale"}


def test_installer(tmp_path):
    inst = load(tmp_path)["sevagjb.PrintView3D.installer.yaml"]
    assert inst["InstallerType"] == "inno" and inst["Scope"] == "user"
    assert inst["Installers"] == [{"Architecture": "x64", "InstallerUrl": INFO["url"],
                                   "InstallerSha256": INFO["sha256"].upper()}]
    assert inst["ProductCode"] == "{f46ac51f-055b-41dc-be29-5f0191feaf3d}_is1"   # the installer's AppId
    assert all(isinstance(e, str) for e in inst["FileExtensions"])              # "off" must not become False
    assert "off" in inst["FileExtensions"]


def test_product_code_matches_the_installer():
    iss = open(os.path.join(HERE, "..", "packaging", "windows", "PrintView3D.iss"), encoding="utf-8").read()
    app_id = iss.split("AppId={{", 1)[1].split("}", 1)[0]
    assert winget.PRODUCT_CODE == "{" + app_id + "}_is1"
