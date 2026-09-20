"""Per-check wall-clock timing for a check run (``albums check --timing``).

For each enabled check, a run measures:

- init: the time to construct the check instance, once per run. Most checks do trivial
  config parsing here, but duplicate-album and duplicate-folder-name build whole-library
  indexes in their constructors.
- pass: every ``check(album)`` call that found no problem.
- fail: every ``check(album)`` call that found a problem. Re-runs of a check after an
  applied fix are counted like any other call.

The report shows the measured values plus a linear estimate of the total time for other
library sizes, assuming the same per-album cost and issue rate.
"""

from dataclasses import dataclass
from typing import Iterable, Mapping

from rich.table import Table


@dataclass
class CheckTiming:
    """Accumulated wall-clock time for one check during a single check run."""

    init_seconds: float = 0.0
    pass_seconds: float = 0.0
    pass_count: int = 0
    fail_seconds: float = 0.0
    fail_count: int = 0

    def record(self, found: bool, seconds: float):
        """Record one ``check(album)`` call (``found`` is True when a problem was reported)."""
        if found:
            self.fail_seconds += seconds
            self.fail_count += 1
        else:
            self.pass_seconds += seconds
            self.pass_count += 1

    @property
    def call_count(self) -> int:
        return self.pass_count + self.fail_count

    @property
    def total_seconds(self) -> float:
        return self.init_seconds + self.pass_seconds + self.fail_seconds


def format_seconds(seconds: float) -> str:
    """Format seconds in the largest unit (s, ms, µs) that keeps the value at least 1."""
    if seconds >= 1:
        return f"{seconds:.2f}s"
    if seconds >= 0.001:
        return f"{seconds * 1000:.1f}ms"
    return f"{seconds * 1_000_000:.0f}µs"


def format_album_count(count: int) -> str:
    """Format an album count with a k/M suffix (e.g. 100000 -> "100k")."""
    if count >= 1_000_000:
        return f"{count // 1_000_000}M"
    return f"{count // 1000}k"


def _format_calls(count: int, total_seconds: float) -> str:
    if count == 0:
        return "-"
    return f"{count} × {format_seconds(total_seconds / count)} = {format_seconds(total_seconds)}"


def check_timing_table(timings: Mapping[str, CheckTiming], order: Iterable[str]) -> Table:
    """Rich table with one row per check: init time, pass and fail call statistics, total time."""
    table = Table("check", "init (1x)", "pass (n × avg = total)", "fail (n × avg = total)", "total")
    for name in order:
        if name not in timings:
            continue
        timing = timings[name]
        table.add_row(
            name,
            format_seconds(timing.init_seconds),
            _format_calls(timing.pass_count, timing.pass_seconds),
            _format_calls(timing.fail_count, timing.fail_seconds),
            format_seconds(timing.total_seconds),
        )
    return table


def estimate_seconds(timings: Mapping[str, CheckTiming], albums: int, n_albums: int) -> float:
    """Linear estimate of the total check time for n_albums albums.

    The per-album cost and issue rate are assumed to stay the same as in the run that
    measured ``albums`` albums, and the measured init time is treated as a constant (in
    practice it grows with library size, e.g. duplicate-album indexes all albums).
    """
    if albums <= 0:
        return 0.0
    per_album_seconds = sum(timing.pass_seconds + timing.fail_seconds for timing in timings.values()) / albums
    init_seconds = sum(timing.init_seconds for timing in timings.values())
    return init_seconds + per_album_seconds * n_albums
