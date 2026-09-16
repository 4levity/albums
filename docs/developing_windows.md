---
icon: lucide/app-window
---

# Windows Builds

`albums` ships for Windows as a standalone executable bundled into an Inno Setup
installer. The steps for building the Windows installer are:

1. Install the project and dependencies in a Windows Python environment
   (`uv sync --locked`).
2. Write the version into the package (see [Developing](./developing.md))
3. Render the project icon into `build/icon.ico` (`scripts/render_icon.py`);
   PyInstaller and Inno Setup use it for the executable and installer.
4. Render the installer script template into `build/albums.iss` with the real
   version (`scripts/render_iss.py`).
5. Build the standalone executable with PyInstaller into
   `dist/pyinstaller/win_amd64/albums/`.
6. Compile the installer with Inno Setup's command-line compiler `iscc` into
   `dist/installer/`.

## Inno Setup script

The installer script template is in `scripts/albums.iss`. It is a valid Inno
Setup 6+ installer script, with 0.0.0 placeholder versions, and it expects
the rendered icon (`build/icon.ico`) next to the rendered script.

## CI

No Windows runner is used: the Windows installer is built on Linux with wine
(see below). The build/test jobs are shared between `.github/workflows/ci.yml`
(pushes to main, pull requests, manual dispatch) and
`.github/workflows/release.yml` (tag pushes `v*`, manual dispatch) via the
reusable workflow `.github/workflows/build-test.yml`. Their `wine` job
installs wine 11 from the WineHQ apt repository (the distro package is too
old), caches the wine environment, then builds the installer
(`make wine-build`), runs the test suite under wine (`make wine-pytest`), and
tests the installer end-to-end (`make wine-e2e`). The `release` job in
`release.yml` publishes the installer, the Linux executable, and the source
archive as GitHub release assets: published for tag pushes, draft for manual
dispatch.

## Local Windows

The same steps run directly on a Windows machine. Inno Setup must be installed.
If `make` is not installed, the commands can be run individually;
`scripts/wine_build.py` runs the same commands in one place.

## Linux with wine

No Windows machine is needed: wine runs the same Windows build.

!!!warning

    Wine prefixes are large: `.cache/wine/` (the wine environment) uses
    about 2.5 GB and `build/wine-e2e/` (the e2e prefix) another 1.4 GB.
    `make clean` removes the e2e prefix but keeps `.cache/wine/`; remove
    it manually to reclaim the space, it is re-created as needed.

- Prerequisites: `wine` 11.0+ and, on headless systems, `xvfb`.
- `make wine-setup` idempotently creates the environment in the gitignored
  `.cache/wine/` folder: a wine prefix, uv (which downloads the Windows Python),
  and Inno Setup. The Inno Setup silent installer needs a display; without one,
  the setup runs it under xvfb-run.
- `make wine-build` performs the steps above and writes
  `dist/installer/albums_win_x86_64-<version>-setup.exe`.

## Testing

Tests run natively with `make test` on Linux and Windows.

`make wine-pytest` runs the test suite in the wine venv. It needs the wine
environment, so the target depends on `wine-setup`.

`make wine-e2e` tests the installer in a temporary wine prefix: it installs it
with `/VERYSILENT /SUPPRESSMSGBOXES`, checks that albums is installed, added to
the user PATH and runs, then uninstalls it and checks that it is gone. Like the
Inno Setup install in `make wine-setup`, installing and uninstalling need a
display, or xvfb when headless.

`make wine-e2e` does not build the installer by default: it uses the installer
in `dist/installer/` whose name matches the current version (built by
`make wine-build`), warns that it is an existing build that may be stale, and
fails if no matching installer is found. Run
`uv run python scripts/wine_e2e.py --build` to build a fresh installer first
(the wine environment is created if needed); the stale-build warning is then
skipped.

## Certificate

The installer is currently unsigned, causing a warning when installing on
Windows and preventing installation on systems with restrictive policies. I
won't spend money on a signing certificate for it, but if there is ever evidence
of an online user community for `albums`, [SignPath](https://signpath.org/apply)
would probably provide a free certificate.
