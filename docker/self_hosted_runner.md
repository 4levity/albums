# Self-Hosted Wine Runner

The `wine-pytest` and `wine-build` jobs in `.github/workflows/build-test.yml`
run on self-hosted runners (label `wine`) in a purpose-built Docker image
from this folder: ubuntu 24.04 with wine 11 (WineHQ stable; the distro wine
is too old for the build scripts), uv, xvfb, and a warm wine environment
(prefix, uv, Windows Python, Inno Setup) baked in by `scripts/wine_setup.py`,
so the jobs skip the multi-minute wine apt install that `ubuntu-latest`
needs.

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
make targets on the host without Docker (below).

## Linux with wine

No Windows machine is needed: wine runs the same Windows build.

Wine prefixes are large: `.cache/wine/` (the wine environment) uses about
2.5 GB and `build/wine-e2e/` (the e2e prefix) another 1.4 GB. `make clean`
removes the e2e prefix but keeps `.cache/wine/`; remove it manually to
reclaim the space, it is re-created as needed.

- Prerequisites: `wine` 11.0+ and, on headless systems, `xvfb`.
- `make wine-setup` idempotently creates the environment in the gitignored
  `.cache/wine/` folder: a wine prefix, uv (which downloads the Windows
  Python), and Inno Setup. The Inno Setup silent installer needs a display;
  without one, the setup runs it under xvfb-run.
- `make wine-build` performs the build steps from
  [Windows Builds](../docs/developing_windows.md) and writes
  `dist/installer/albums_win_x86_64-<version>-setup.exe`.

## Testing

Tests run natively with `make test` on Linux and Windows.

`make wine-pytest` runs the test suite in the wine venv. It needs the wine
environment, so the target depends on `wine-setup`.

`make wine-e2e` tests the installer in a temporary wine prefix: it installs
it with `/VERYSILENT /SUPPRESSMSGBOXES`, checks that albums is installed,
added to the user PATH and runs, then uninstalls it and checks that it is
gone. Like the Inno Setup install in `make wine-setup`, installing and
uninstalling need a display, or xvfb when headless.

`make wine-e2e` does not build the installer by default: it uses the
installer in `dist/installer/` whose name matches the current version (built
by `make wine-build`), warns that it is an existing build that may be stale,
and fails if no matching installer is found. Run
`uv run python scripts/wine_e2e.py --build` to build a fresh installer first
(the wine environment is created if needed); the stale-build warning is then
skipped.
