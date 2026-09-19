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

No Windows runner is used: the Windows installer is built on Linux with wine.
The build/test jobs are shared between `.github/workflows/ci.yml` (pushes to
main, pull requests, manual dispatch) and
`.github/workflows/release.yml` (tag pushes `v*`, manual dispatch) via the
reusable workflow `.github/workflows/build-test.yml`. Its `wine-pytest` and
`wine-build` jobs run in parallel on self-hosted runners (label `wine`) in
the purpose-built image from [`docker/`](../docker/): the test job runs the
test suite under wine, and the build job builds the installer and tests it
end-to-end. The `release` job in `release.yml` publishes the installer, the
Linux executable, and the source archive as GitHub release assets: published
for tag pushes, draft for manual dispatch.

Runner setup, and local building and testing with wine, are documented in
`docker/self_hosted_runner.md` (in the repo, not on this site).

## Testing Windows-specific behavior

`make` (the default target) and the commit/push hooks only run the test suite
on the host platform. Windows only runs via `make wine-pytest` (and the
`wine-pytest` CI job). After changes involving Windows-specific behavior, run
`make wine-pytest` or the suite on a Windows dev machine to verify. Examples of
Windows-specific behavior: path validation and sanitization driven by
`path_compatibility` (e.g. reserved names like `CON`, checked by
`illegal-pathname`), and platform path semantics (e.g. on Windows `a:b` is a
drive-relative path resolved against drive `a:`, not a folder named `a:b`,
which is why some `illegal-pathname` tests are Linux-only).

## Local Windows

The same steps run directly on a Windows machine. Inno Setup must be installed.
If `make` is not installed, the commands can be run individually;
`scripts/wine_build.py` runs the same commands in one place.

## Certificate

The installer is currently unsigned, causing a warning when installing on
Windows and preventing installation on systems with restrictive policies. I
won't spend money on a signing certificate for it, but if there is ever evidence
of an online user community for `albums`, [SignPath](https://signpath.org/apply)
would probably provide a free certificate.
