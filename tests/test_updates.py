"""Update check: versions, GitHub's answer, daily schedule, skipping, verified download."""

import hashlib
import io

import pytest

from printview3d import __version__
from printview3d import updates as u
from printview3d.settings import Settings

PAYLOAD = b"pretend installer " * 1000


def gh_release(tag="v9.9.0", digest=None, **extra):
    data = {"tag_name": tag, "draft": False, "prerelease": False, "body": "## What's new\n- things",
            "html_url": f"https://github.com/{u.REPO}/releases/tag/{tag}", "published_at": "2026-11-01T10:00:00Z",
            "assets": [{"name": "PrintView3D-windows.zip", "browser_download_url": "https://x/zip", "size": 1},
                       {"name": u.SETUP_ASSET, "browser_download_url": "https://x/setup.exe",
                        "size": len(PAYLOAD),
                        "digest": digest or "sha256:" + hashlib.sha256(PAYLOAD).hexdigest()}]}
    data.update(extra)
    return data


@pytest.mark.parametrize("remote,local,newer", [
    ("v0.10.0", "0.9.0", True), ("0.9.1", "0.9.0", True), ("1.0", "0.99.9", True),
    ("0.9.0", "0.9.0", False), ("0.9", "0.9.0", False), ("0.8.9", "0.9.0", False),
    ("v1.0.0-beta", "0.9.0", True), ("garbage", "0.9.0", False),
])
def test_is_newer(remote, local, newer):
    assert u.is_newer(remote, local) is newer


def test_parse_release():
    rel = u.parse_release(gh_release())
    assert rel.version == "9.9.0"
    assert rel.setup_url == "https://x/setup.exe"
    assert rel.setup_sha256 == hashlib.sha256(PAYLOAD).hexdigest()
    assert "What's new" in rel.notes


def test_drafts_and_test_versions_are_ignored():
    assert u.parse_release(gh_release(draft=True)) is None
    assert u.parse_release(gh_release(prerelease=True)) is None


def test_fetch_latest_offline_raises(monkeypatch):
    def boom(*_a, **_k):
        raise OSError("no network")
    monkeypatch.setattr(u, "_request", boom)
    with pytest.raises(u.UpdateError):
        u.fetch_latest()


@pytest.fixture
def settings(tmp_path):
    return Settings(str(tmp_path / "settings.json"))


def test_not_asked_means_no_automatic_check(settings):
    assert settings.get("update_check") is None
    assert not u.check_is_due(settings, now=10 ** 10)


def test_daily_schedule(settings):
    settings.set("update_check", True)
    assert u.check_is_due(settings, now=10 ** 9)
    u.remember(settings, None, now=10 ** 9)
    assert not u.check_is_due(settings, now=10 ** 9 + 3600)
    assert u.check_is_due(settings, now=10 ** 9 + u.CHECK_INTERVAL)
    settings.set("update_check", False)
    assert not u.check_is_due(settings, now=10 ** 10)


def test_available_and_skip(settings):
    u.remember(settings, u.parse_release(gh_release("v9.9.0")))
    assert u.available(settings).version == "9.9.0"
    settings.set("update_skip", "9.9.0")
    assert u.available(settings) is None
    u.remember(settings, u.parse_release(gh_release("v9.9.1")))     # a newer one shows again
    assert u.available(settings).version == "9.9.1"


def test_same_version_is_not_an_update(settings):
    u.remember(settings, u.parse_release(gh_release("v" + __version__)))
    assert u.available(settings) is None


class _Resp(io.BytesIO):
    headers = {"Content-Length": str(len(PAYLOAD))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_download_checks_the_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(u, "download_dir", lambda: str(tmp_path))
    monkeypatch.setattr(u, "_request", lambda *a, **k: _Resp(PAYLOAD))
    seen = []
    path = u.download_installer(u.parse_release(gh_release()), progress=seen.append)
    assert open(path, "rb").read() == PAYLOAD
    assert seen[-1] == pytest.approx(1.0)

    bad = u.parse_release(gh_release(digest="sha256:" + "0" * 64))
    with pytest.raises(u.UpdateError):
        u.download_installer(bad)
    assert not any(p.name.endswith(".part") for p in tmp_path.iterdir())


def test_install_kind_from_source_opens_the_page():
    assert u.install_kind() == "page"          # tests run from source, not the installed .exe
