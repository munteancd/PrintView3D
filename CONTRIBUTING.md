# Contributing to PrintView3D

Thanks for helping! Issues and pull requests are welcome.

## Reporting a problem

Open an [issue](../../issues) and include:
- what you did, what you expected and what happened
- your Windows version and the PrintView3D version (**About** button)
- if a file does not open: the error message, and if possible the file (or a small file that
  fails the same way)

## Adding a slicer

Slicers are listed in `SLICERS` in `src/printview3d/slicer.py`. A new entry needs:

```python
Slicer("my_slicer", "My Slicer",
       ("MySlicer.exe",),            # exact program file name(s)
       ("myslicer",),                # fallback: part of the program file name
       r"my\s*slicer",               # regex for its name in "Installed apps"
       (r"MySlicer*", r"Programs\MySlicer*")),  # install folders (Program Files / LocalAppData)
```

Then add a test in `tests/test_slicer.py` if the detection has anything special.

## Development setup

1. Install Python 3.12 (see the README: newer versions may not be supported by VTK yet).
2. Run `build_windows.bat` once; it creates `.venv` with everything installed.
3. `run_from_source.bat` starts the app from the source code.
4. `.venv\Scripts\python -m pytest -q` runs the tests. Please keep them passing.

Keep code readable: small functions, comments that explain *why*, no new heavy dependencies
without discussion.

## Releasing (maintainers)

1. Update the version in `src/printview3d/__init__.py`, `pyproject.toml`, `version_info.txt`
   and add an entry to `CHANGELOG.md`.
2. Commit, then tag and push: `git tag v0.4.0 && git push origin v0.4.0`.
3. GitHub Actions builds the program and publishes the release with the zip attached.
