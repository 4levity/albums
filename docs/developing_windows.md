---
icon: lucide/app-window
---

# Windows Builds

`albums` ships for Windows as a standalone executable bundled into an Inno Setup
installer. The steps for building the Windows installer are:

1. Install the project and dependencies in a Windows Python environment
   (`uv sync --locked`).
2. Write the version into the package (see [Developing](./developing.md))
3. Render the installer script template into `build/albums.iss` with the real
   version (`scripts/render_iss.py`).
4. Build the standalone executable with PyInstaller into
   `dist/pyinstaller/win_amd64/albums/`.
5. Compile the installer with Inno Setup's command-line compiler `iscc` into
   `dist/installer/`.

## Inno Setup script

The installer script template is in `scripts/albums.iss`. It is a valid Inno
Setup 6+ installer script, with 0.0.0 placeholder versions.

## Windows CI (releases)

`.github/workflows/pyinstaller.yml` runs on tag pushes (`v*`) and manual
dispatch. Its Windows job performs the steps above on a Windows runner (the
runner image ships with Inno Setup) and uploads the installer; the release job
publishes the installer and the Linux executable as GitHub release assets.

## Local Windows

The same steps run directly on a Windows machine. Inno Setup must be installed.
If `make` is not installed, the commands can be run individually; the Windows CI
job shows these commands in one place.

## Linux with wine

No Windows machine is needed: wine runs the same Windows build.

- Prerequisites: `wine` 11.0+ and, on headless systems, `xvfb`.
- `make wine-setup` idempotently creates the environment in the gitignored
  `.cache/wine/` folder: a wine prefix, uv (which downloads the Windows Python),
  and Inno Setup. The Inno Setup silent installer needs a display; without one,
  the setup runs it under xvfb-run.
- `make wine-build` performs the steps above and writes
  `dist/installer/albums_win_x86_64-<version>-setup.exe`.

## Testing

Tests run natively with `make test` on Linux and Windows. Running the test suite
against a Windows build in CI or wine is not yet automated.

The wine build uses the same locked dependencies, PyInstaller arguments, and
installer script as the Windows CI job, so it produces the same kind of
installer. Testing the installer is not yet automated.

## Certificate

The installer is currently unsigned, causing a warning when installing on
Windows and preventing installation on systems with restrictive policies. I
won't spend money on a signing certificate for it, but if there is ever evidence
of an online user community for `albums`, [SignPath](https://signpath.org/apply)
would probably provide a free certificate.
