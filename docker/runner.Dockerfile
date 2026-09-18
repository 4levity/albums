# Self-hosted runner image for the wine (Windows build) job.
#
# ubuntu 24.04 (same distro as ubuntu-latest) with wine 11 (WineHQ stable;
# the distro wine is too old for the build scripts), xvfb + fonts (the Inno
# Setup GUI installers run headless), and a GitHub Actions runner.
#
# A warm wine environment (prefix, uv, Windows Python, Inno Setup) is baked
# in by running scripts/wine_setup.py at image build time. The wine venv is
# not baked in: the first job on the runner creates it, it then persists in
# the /opt/wine volume, and `uv sync --locked` tops up lockfile changes.
#
# Built and published by the "Runner Image" workflow (manual dispatch) to
# ghcr.io/4levity/albums-runner; see docs/developing_windows.md.

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8

# Base system dependencies: git/make/python3 for the build, and libicu74 +
# liblttng-ust1t64, which the .NET runner binary needs. No recommends:
# headless build.
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        ca-certificates curl git libicu74 liblttng-ust1t64 make python3 zip unzip \
    && rm -rf /var/lib/apt/lists/*

# uv for the native build tooling (`make install`, `uv run`), so the wine job
# needs no setup-uv step. Pinned and sha256-checked, like the Windows uv in
# scripts/wine_setup.py.
ARG UV_VERSION=0.12.16
ARG UV_SHA256=a01206ffbd60f3a7ee30949be1863527986f5307494a064042c69ce7e6d44799
RUN set -eux; \
    curl -fsSL -o /tmp/uv.tar.gz \
        "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-musl.tar.gz"; \
    echo "${UV_SHA256}  /tmp/uv.tar.gz" | sha256sum -c -; \
    tar xzf /tmp/uv.tar.gz -C /usr/local/bin --strip-components=1; \
    rm /tmp/uv.tar.gz; \
    uv --version

# wine 11 from WineHQ: the wine packages require the i386 architecture, and
# the fonts are for the GUI installers under xvfb.
RUN dpkg --add-architecture i386 && \
    curl -fsSL https://dl.winehq.org/wine-builds/winehq.key -o /etc/apt/keyrings/winehq.key && \
    echo "deb [signed-by=/etc/apt/keyrings/winehq.key] https://dl.winehq.org/wine-builds/ubuntu/ noble main" > /etc/apt/sources.list.d/winehq.list && \
    apt-get update && \
    apt-get install --no-install-recommends -y \
        winehq-stable xvfb fonts-liberation fonts-dejavu-core xfonts-base && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    wine --version

# Warm wine environment: scripts/wine_setup.py creates the prefix and
# installs uv, Windows Python and Inno Setup into it (all pinned and
# sha256-checked in the script). The fingerprint records the wine scripts so
# the workflow can detect stale pins (it then builds a fresh environment
# instead of linking this one).
COPY scripts/ /tmp/repo/scripts/
RUN set -eux; \
    cd /tmp/repo; \
    python3 scripts/wine_setup.py; \
    mkdir -p /opt/wine; \
    mv .cache/wine /opt/wine/env; \
    # download() writes mode-600 files (mkstemp); make the environment
    # world-readable so any user can copy it out of the image
    chmod -R a+rX /opt/wine/env; \
    sha256sum scripts/wine_setup.py scripts/wine_common.py > /opt/wine/env/fingerprint; \
    test -d /opt/wine/env/prefix/drive_c; \
    test -f /opt/wine/env/bin/uv.exe; \
    test -f /opt/wine/env/prefix/drive_c/InnoSetup7/ISCC.exe; \
    rm -rf /tmp/repo

# GitHub Actions runner (the release tarball, as the official image installs
# it), running as the 'runner' user, like the official image.
ARG RUNNER_VERSION=2.337.0
RUN adduser --disabled-password --gecos "" --uid 1001 runner && \
    curl -fsSL -o /tmp/runner.tar.gz \
        https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz && \
    mkdir -p /home/runner && \
    tar xzf /tmp/runner.tar.gz -C /home/runner && \
    rm /tmp/runner.tar.gz
COPY docker/entrypoint.sh /home/runner/entrypoint.sh
RUN chown -R runner:runner /home/runner /opt/wine && chmod 755 /home/runner/entrypoint.sh

WORKDIR /home/runner
USER runner
# Like the official image: trap signals manually and print job logs to stdout
ENV RUNNER_MANUALLY_TRAP_SIG=1
ENV ACTIONS_RUNNER_PRINT_LOG_TO_STDOUT=1
ENTRYPOINT ["/home/runner/entrypoint.sh"]
