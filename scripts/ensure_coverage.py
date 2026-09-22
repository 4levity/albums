"""Compare code coverage to last value from codecov.io"""

import os
import re
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import NoReturn

COVERAGE_FILE = "build/coverage.xml"
MAX_COVERAGE_AGE_SECONDS = 60


def fail(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def get_local_coverage() -> float:
    if not os.path.isfile(COVERAGE_FILE):
        fail(f"no {COVERAGE_FILE}; run 'make coverage' first")
    age = time.time() - os.path.getmtime(COVERAGE_FILE)
    if age > MAX_COVERAGE_AGE_SECONDS:
        fail(f"{COVERAGE_FILE} is {age:.0f}s old (limit {MAX_COVERAGE_AGE_SECONDS}s); run 'make coverage' first")
    try:
        line_rate = ET.parse(COVERAGE_FILE).getroot().get("line-rate")
    except ET.ParseError as e:
        fail(f"cannot parse {COVERAGE_FILE}: {e}")
    if line_rate is None:
        fail(f"cannot parse {COVERAGE_FILE}: missing line-rate")
    try:
        return 100.0 * float(line_rate)
    except ValueError:
        fail(f"cannot parse {COVERAGE_FILE}: line-rate {line_rate!r} is not a number")


def get_codecov_coverage(branch: str) -> float:
    badge_url = f"https://codecov.io/gh/4levity/albums/branch/{branch}/graph/badge.svg?precision=2"
    req = urllib.request.Request(badge_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as response:
            svg_content = response.read().decode("utf-8")
    except OSError as e:
        print(f"warning: could not retrieve codecov badge for branch {branch} ({e}); assuming 0.00%", file=sys.stderr)
        return 0.0
    match = re.search(r">(\d+(?:\.\d+)?)%</text>", svg_content)
    if match is None:
        print(f"warning: could not parse codecov badge for branch {branch}; assuming 0.00%", file=sys.stderr)
        return 0.0
    return float(match.group(1))


def get_branch() -> str:
    # git symbolic-ref succeeds only when HEAD is on a branch (not detached)
    try:
        result = subprocess.run(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], capture_output=True, text=True)
    except OSError:
        return "main"
    branch = result.stdout.strip()
    return branch if result.returncode == 0 and branch else "main"


def main() -> int:
    local = get_local_coverage()
    branch = get_branch()
    codecov = get_codecov_coverage(branch)
    allowed = local >= codecov
    if not allowed or os.environ.get("QUIET", "") != "1":
        print(f"local coverage: {local:.2f} / codecov coverage (branch {branch}): {codecov:.2f}")
        print(f"code coverage is {'' if allowed else 'not '}high enough")
    return 0 if allowed else 1


if __name__ == "__main__":
    sys.exit(main())
