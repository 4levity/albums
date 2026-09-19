# Self-Hosted Wine Runner

## CI

The `wine-pytest` and `wine-build` jobs in `.github/workflows/build-test.yml`
run on self-hosted runners (label `wine`) in a purpose-built Docker image
from this folder: ubuntu 24.04 with wine 11, uv, xvfb, and a warm wine
environment (prefix, uv, Windows Python, Inno Setup) baked in by
`scripts/wine_setup.py`, so the jobs skip the multi-minute wine apt install
that `ubuntu-latest` needs.

The image is built by the `.github/workflows/runner-image.yml` workflow
(manual dispatch) and published to `ghcr.io/4levity/albums-runner`. Rerun it
after changes to `docker/` or the wine scripts' pins: the image bakes a warm
wine environment, and the jobs link it in only while its fingerprint matches
the wine scripts (they then build a fresh environment).

## Starting two runners

Two runners run the two wine jobs in parallel. On a machine with Docker,
generate two runner tokens (Settings > Actions > Runners > New self-hosted
runner, Linux/x64, one per runner) and start two containers, each with its
own name, work volume and wine volume:

```bash
docker run -d --name albums-wine-1 --restart unless-stopped \
  -e RUNNER_TOKEN=<token-1> \
  -e RUNNER_NAME=albums-wine-1 \
  -v albums-runner-work-1:/home/runner/_work \
  -v albums-runner-wine-1:/opt/wine \
  ghcr.io/4levity/albums-runner:latest
```

```bash
docker run -d --name albums-wine-2 --restart unless-stopped \
  -e RUNNER_TOKEN=<token-2> \
  -e RUNNER_NAME=albums-wine-2 \
  -v albums-runner-work-2:/home/runner/_work \
  -v albums-runner-wine-2:/opt/wine \
  ghcr.io/4levity/albums-runner:latest
```

Both containers keep the default label `wine`, so either job can land on
either idle runner. Keep both running: with only one `wine` runner
available, the second wine job queues instead of running.

Give each container its own wine volume, and do not share one between the
two: the jobs link the image's baked-in environment into the checkout, and a
shared volume would let two concurrent jobs use one wine prefix at once,
which corrupts it (the workflow's lock check is only a heuristic). The first
job on a container creates the wine venv in its volume; later jobs reuse it,
and `uv sync --locked` tops up lockfile changes.

## Container lifecycle

After a stop or host reboot, `docker start albums-wine-1` is enough: the
runner registration lives in container storage, which a stop does not touch.
To upgrade the image, pull it and recreate the container with the same
command (a container cannot change its image); the entrypoint re-registers
the runner by name (`config.sh --replace`), keeping its name and labels.

The volumes exist because a container's own storage (its writable layer)
dies with `docker rm`, and an upgrade is always rm plus recreate: anything
that must survive an upgrade lives in a volume. On a Linux host a volume is
just a directory on the host disk, so a volume buys lifetime and host
visibility, not performance.

- `/opt/wine` holds what is expensive to recreate: the wine venv and uv
  cache the first job creates. The wine environment itself (prefix, Windows
  Python, Inno Setup, uv) is baked into the image and comes back with every
  image: an empty volume is initialized from the image on first start, so
  the volume starts as a copy of the baked environment and accumulates the
  venv. Each container has its own volume, which is what keeps the two
  runners' wine prefixes apart. To pick up a new image's baked
  environment, delete the wine volume before recreating the container; until
  then the fingerprint guard makes the stale volume safe (jobs build a
  fresh environment instead of linking it).
- `/home/runner/_work` holds disposable job checkouts; the volume is only
  for host-side inspection, e.g. looking at a failed job's workspace after
  the container is gone.
- `/home/runner` itself is deliberately not mounted: the runner
  installation is pinned per image version and must come from the image,
  and a volume would mask it with stale content.

## Local runner use

The runner image can also run the wine jobs locally, on a machine with
Docker but no runner: `docker/build-image.sh` builds it locally (tag
`ghcr.io/4levity/albums-runner:local`), and `docker/wine-local.sh` runs the
wine jobs' steps in a container from that image. The container runs as the
current user (the image's runner user, uid 1001, would not match the
checkout's ownership), so `.cache/`, `build/`, `dist/` and `.venv/` keep the
developer's ownership. The preferred local procedure is still the `wine-*`
make targets on the host without Docker (see
[Windows Builds](../docs/developing_windows.md)).

## Wine on default GHA runners

Before commit `1dd51b7f3b8`, the wine job ran on `ubuntu-latest`: wine 11 was
installed per build, and the wine environment was cached with
`actions/cache` (full job:
`git show 1dd51b7f3b8^:.github/workflows/build-test.yml`):

```yaml
wine:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v5
      with:
        fetch-depth: 0
    - uses: astral-sh/setup-uv@v10.0.1
      with:
        python-version: "3.14"
    - name: Install wine
      # the distro wine is too old (the scripts require 11+); WineHQ ships
      # current releases, and the wine packages require the i386
      # architecture. No recommends needed: headless build, and the runner
      # image already has the display/fonts.
      run: |
        sudo dpkg --add-architecture i386
        sudo curl -fsSL https://dl.winehq.org/wine-builds/winehq.key -o /etc/apt/keyrings/winehq.key
        codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
        echo "deb [signed-by=/etc/apt/keyrings/winehq.key] https://dl.winehq.org/wine-builds/ubuntu/ ${codename} main" | sudo tee /etc/apt/sources.list.d/winehq.list
        sudo apt-get update
        sudo apt-get install --no-install-recommends winehq-stable
    - name: Check wine version
      run: wine --version
    - name: Install dependencies
      run: make install
    - name: Cache wine environment
      uses: actions/cache@v6
      with:
        # cache keys are immutable, so include uv.lock: a lock change saves a
        # fresh warm state under the new key, and the restore-keys fallback
        # (same tool pins) gives a near-warm restore that wine_build's
        # `uv sync --locked` tops up with the small delta
        path: .cache/wine
        key: wine-${{ runner.os }}-${{ hashFiles('scripts/wine_setup.py', 'scripts/wine_common.py') }}-${{ hashFiles('uv.lock') }}
        restore-keys: |
          wine-${{ runner.os }}-${{ hashFiles('scripts/wine_setup.py', 'scripts/wine_common.py') }}-
    - name: Run test suite under wine
      run: make wine-pytest
    - name: Build Windows installer
      run: make wine-build
    - name: Test installer end-to-end
      run: make wine-e2e
```

## Windows GHA runners

Before commit `1b6aaa33143`, the installer was built on `windows-latest` with
its preinstalled Inno Setup (`iscc` on PATH), no wine. The Windows runner image
has no `make`, so the build steps ran directly (full job:
`git show 1b6aaa33143^:.github/workflows/pyinstaller.yml`). There was no Windows
testing.

```yaml
build-win:
  runs-on: windows-latest
  steps:
    - uses: actions/checkout@v5
      with:
        fetch-depth: 0
    - uses: astral-sh/setup-uv@v10.0.1
      with:
        python-version: "3.14"
    # the windows runner image has no make, so run the make pyinstaller steps directly
    - name: Install dependencies
      run: uv sync --locked
      shell: bash
    - name: Render project icon
      run: uv run python scripts/render_icon.py
      shell: bash
    - name: Build executable
      run: |
        uv run python scripts/version.py write
        platform=$(uv run python -c "import sysconfig; print(sysconfig.get_platform().replace('-', '_'))")
        uv run pyinstaller src/albums/__main__.py --onedir --name albums --noconfirm --clean \
          --collect-data albums \
          --icon "$(pwd)/build/icon.ico" \
          --workpath "build/$platform" --distpath "dist/pyinstaller/$platform" \
          --specpath "build/$platform/.specs" --contents-directory _albums_internal
        ls -l "dist/pyinstaller/$platform/albums"
      shell: bash
    - name: Create installer script
      run: uv run python scripts/render_iss.py
      shell: bash
    - name: Build installer
      run: |
        iscc build/albums.iss
        ls -l dist/installer
      shell: bash
```
