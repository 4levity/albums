#!/bin/sh
# Run the CI wine job (test suite + Windows installer build) locally, in a
# container from the self-hosted runner image (docker/build-image.sh).
#
# Like the wine job in .github/workflows/build-test.yml: install
# dependencies, use the wine environment baked into the image (copied into
# .cache/wine/, replacing any existing one, while its fingerprint matches
# the wine scripts; a missing or stale environment is an error, rebuild the
# image with docker/build-image.sh), then run the test suite under wine and
# build the installer. The container runs as the current user, since the
# image's runner user (uid 1001) would not match the checkout's ownership,
# so the outputs (.cache/, build/, dist/, .venv/) keep the developer's
# ownership.
#
# The regular local procedure is still the wine-* make targets on the host
# without Docker; this script exists to exercise the runner image.
#
# Usage: sh docker/wine-local.sh
set -eu

cd "$(dirname "$0")/.."
IMAGE=ghcr.io/4levity/albums-runner:local

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "error: image $IMAGE not found; run docker/build-image.sh first" >&2
    exit 1
fi

docker run --rm -i \
    --user "$(id -u):$(id -g)" \
    --entrypoint sh \
    -v "$PWD":/work \
    -e HOME=/work \
    "$IMAGE" -s <<'EOF'
set -eu
cd /work
echo "uv:   $(uv --version)"
echo "wine: $(wine --version)"
echo "== make install"
make install
# The wine environment, like the wine job in build-test.yml: use the
# baked-in one while its fingerprint matches the wine scripts. It is a
# copy, not a link, because the image's /opt/wine is owned by the runner
# user (uid 1001) and the wine scripts need to write .cache/wine.
if [ -d /opt/wine/env ] && [ ! -e /opt/wine/env/prefix/.lock ] && sha256sum -c /opt/wine/env/fingerprint --quiet; then
    echo "using baked-in wine environment"
    rm -rf .cache/wine
    cp -a /opt/wine/env .cache/wine
else
    echo "error: baked-in wine environment missing or stale; rebuild the image (docker/build-image.sh)"
    # if we just remove the .cache/wine it would be rebuilt, but for this script it's an error
    # rm -rf .cache/wine
    exit 1
fi
# the environment must provide uv and Inno Setup (baked in, not reinstalled)
test -d .cache/wine/prefix/drive_c
test -f .cache/wine/bin/uv.exe
test -f .cache/wine/prefix/drive_c/InnoSetup7/ISCC.exe
echo "== make wine-pytest"
make wine-pytest
echo "== make wine-build"
make wine-build
ls -l dist/installer/
EOF
