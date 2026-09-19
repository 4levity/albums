#!/bin/sh
# Link the self-hosted runner image's baked-in wine environment into the
# checkout's .cache/wine, or warn why not and let wine-setup build a fresh
# one. Used by the wine jobs in .github/workflows/build-test.yml.
#
# Guards, in order (the first failure wins):
#   .cache/wine present    reuse it, link nothing
#   $WINE_ENV exists       the volume is seeded from the image on first start
#   no $WINE_ENV/prefix/.lock  no wineserver (concurrent or stuck job) uses it
#   $WINE_ENV/fingerprint matches the wine scripts of the checked-out commit
#
# A failed guard prints a GitHub Actions warning annotation (visible in the
# check run, never a failure) naming the likely fix, then the
# "building a fresh wine environment" line so the log is easy to search.
# The fingerprint check runs without --quiet so the log shows which script
# mismatched.
#
# Usage: sh docker/wine_link_env.sh [WINE_ENV_DIR]   (default /opt/wine/env)
set -eu

WINE_ENV=${1:-/opt/wine/env}

if [ -e .cache/wine ]; then
    echo "wine environment already in checkout; reusing it"
elif [ ! -d "$WINE_ENV" ]; then
    echo "::warning::no wine environment at $WINE_ENV (stale runner image or wine volume). Rebuild the image via the runner-image workflow, delete the wine volume, and recreate the runner (docker/self_hosted_runner.md)"
    echo "building a fresh wine environment"
elif [ -e "$WINE_ENV/prefix/.lock" ]; then
    echo "::warning::wine environment at $WINE_ENV is locked (a wineserver from an earlier job is still running); building a fresh one instead. If this repeats, kill the stuck wineserver in the runner container."
    echo "building a fresh wine environment"
elif ! sha256sum -c "$WINE_ENV/fingerprint"; then
    echo "::warning::wine environment at $WINE_ENV does not match the wine scripts (stale runner image). Rebuild the image via the runner-image workflow, delete the wine volume, and recreate the runner (docker/self_hosted_runner.md)"
    echo "building a fresh wine environment"
else
    mkdir -p .cache
    ln -s "$(cd "$WINE_ENV" && pwd)" .cache/wine
    echo "using baked-in wine environment"
fi
