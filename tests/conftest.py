"""Shared test setup: import printview3d from src/ (works for any single test file too)."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _escape(text: str) -> str:
    """GitHub's escaping for annotation messages."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def pytest_terminal_summary(terminalreporter):
    """On GitHub Actions, show every failed test on the run's summary page (an "annotation"),
    so the reason is visible without opening the log."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    runner = os.environ.get("RUNNER_OS", "")
    for report in terminalreporter.stats.get("failed", []) + terminalreporter.stats.get("error", []):
        path, line, _ = report.location
        crash = getattr(report.longrepr, "reprcrash", None)
        message = crash.message if crash else str(report.longrepr)
        lines = message.strip().splitlines()
        if len(lines) > 12:
            lines = lines[:12] + ["…"]
        test = report.nodeid.split("::", 1)[-1]
        where = f"file={path.replace(os.sep, '/')},line={(line or 0) + 1}"
        title = _escape(f"{runner} test failed: {test}").replace(",", "%2C").replace(":", "%3A")
        terminalreporter.write_line(f"::error {where},title={title}::{_escape(chr(10).join(lines))}")
