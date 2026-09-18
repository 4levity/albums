#!/bin/sh
# Build the self-hosted wine runner image locally (docker/runner.Dockerfile,
# the image the "Runner Image" workflow publishes to ghcr.io).
#
# Usage: sh docker/build-image.sh
set -eu

cd "$(dirname "$0")/.."
docker build -f docker/runner.Dockerfile -t ghcr.io/4levity/albums-runner:local .
