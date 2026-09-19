#!/bin/sh
# GitHub Actions runner entrypoint.
#
#   docker run -d --name albums-runner --restart unless-stopped \
#     -e RUNNER_TOKEN=<token> -e RUNNER_NAME=albums-wine \
#     -v albums-runner-work:/home/runner/_work -v albums-runner-wine:/opt/wine \
#     ghcr.io/4levity/albums-runner:latest
#
# Takes no argument in normal use: the first start registers the runner
# (which needs RUNNER_TOKEN) and starts it, later starts (docker start,
# host reboot) just start the already registered runner, so a stopped
# container starts again with `docker start albums-runner`, no new token
# needed. Pass `remove` to unregister the runner:
#
#   docker run --rm ghcr.io/4levity/albums-runner:latest remove

set -eu

cd "$(dirname "$0")" || exit 1

case "${1:-run}" in
  run|register)
    # the runner stores its config in the .runner file; .runner_migrated is
    # the newer config file name (both checked, as the runner does)
    if [ ! -e .runner ] && [ ! -e .runner_migrated ]; then
      : "${RUNNER_TOKEN:?create one under Settings > Actions > Runners > New self-hosted runner}"
      echo "registering runner ${RUNNER_NAME:-$(hostname)}"
      ./config.sh --replace --unattended \
        --url "${REPO_URL:-https://github.com/4levity/albums}" \
        --token "${RUNNER_TOKEN}" \
        --name "${RUNNER_NAME:-$(hostname)}" \
        --labels "${RUNNER_LABELS:-wine}"
    else
      echo "runner already registered, starting"
    fi
    exec ./run.sh
    ;;
  remove)
    exec ./config.sh remove
    ;;
  *)
    echo "usage: entrypoint.sh [run|register|remove]" >&2
    exit 1
    ;;
esac
