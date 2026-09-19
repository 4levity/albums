#!/bin/sh
# GitHub Actions runner entrypoint.
#
#   docker run -d --name albums-runner \
#     -e RUNNER_TOKEN=<token> -e RUNNER_NAME=albums-wine \
#     -v albums-runner-home:/home/runner -v albums-runner-wine:/opt/wine \
#     ghcr.io/4levity/albums-runner:latest
#
# Modes: register (default: configure if needed, then run), run (start an
# already configured runner), remove (unregister). RUNNER_TOKEN is only
# needed for the first registration; restarts reuse the stored config, so a
# stopped container starts again with `docker start`.

set -eu

case "${1:-register}" in
  register)
    if [ ! -d .runner ]; then
      : "${RUNNER_TOKEN:?create one under Settings > Actions > Runners > New self-hosted runner}"
      ./config.sh --replace --unattended \
        --url "${RUNNER_URL:-https://github.com/4levity/albums}" \
        --token "${RUNNER_TOKEN}" \
        --name "${RUNNER_NAME:-$(hostname)}" \
        --labels "${RUNNER_LABELS:-wine}"
    fi
    exec ./run.sh
    ;;
  run)
    exec ./run.sh
    ;;
  remove)
    exec ./config.sh remove
    ;;
  *)
    echo "usage: entrypoint.sh [register|run|remove]" >&2
    exit 1
    ;;
esac
