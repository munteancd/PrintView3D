# Security

PrintView3D opens files from the internet (models, ZIP packages, G-code), so its safety matters.

## Reporting a problem

Please **don't open a public issue** for a security problem. Report it privately instead:
on GitHub, open the **Security** tab of this repository and click **Report a vulnerability**.
You'll get an answer within a week. Once it is fixed, the release notes thank you (unless you'd
rather not be named).

Only the newest version gets security fixes; the program can update itself (Settings → Updates).

## How PrintView3D protects you

- **Works offline.** It only connects to GitHub to check for updates, when you allow it
  ([details](README.md#updates-and-privacy)).
- **Updates** are downloaded only from this project's GitHub releases, and installed only when
  their SHA-256 fingerprint matches the one GitHub publishes.
- **Files are only read, never run.** ZIP packages are size-checked before anything is unpacked
  (no "ZIP bombs") and can't write outside PrintView3D's own cache folder. 3MF and FreeCAD files
  get the same size checks. A glTF file can only use data files from its own folder.
- **File Explorer thumbnails** (Windows) check every size and position they read, because they run
  for every file Explorer shows.
- **FreeCAD and STEP files** are converted by your installed FreeCAD, so they deserve the same
  trust as opening them in FreeCAD.
