import pytest
from rich.console import Console

from albums.checks.check_timing import CheckTiming, check_timing_table, estimate_seconds, format_album_count, format_seconds


class TestCheckTiming:
    def test_record(self):
        timing = CheckTiming()
        assert timing.call_count == 0
        assert timing.total_seconds == 0
        timing.record(False, 0.001)
        timing.record(True, 0.002)
        assert timing.pass_count == 1
        assert timing.pass_seconds == 0.001
        assert timing.fail_count == 1
        assert timing.fail_seconds == 0.002
        assert timing.call_count == 2
        assert timing.total_seconds == pytest.approx(0.003)

    def test_format_seconds(self):
        assert format_seconds(0.0) == "0µs"
        assert format_seconds(0.0000012) == "1µs"
        assert format_seconds(0.0001234) == "123µs"
        assert format_seconds(0.01234) == "12.3ms"
        assert format_seconds(1.0) == "1.00s"
        assert format_seconds(12.348) == "12.35s"

    def test_format_album_count(self):
        assert format_album_count(10_000) == "10k"
        assert format_album_count(100_000) == "100k"
        assert format_album_count(1_000_000) == "1M"

    def test_estimate_seconds(self):
        # measured over 2 albums: init 1s total, 0.03s of check calls per album
        timings = {
            "a": CheckTiming(init_seconds=1.0, pass_seconds=0.04, pass_count=2),
            "b": CheckTiming(fail_seconds=0.02, fail_count=1),
        }
        assert estimate_seconds(timings, 2, 10) == pytest.approx(1.3)
        assert estimate_seconds(timings, 0, 10) == 0.0

    def test_check_timing_table(self):
        timings = {
            "a": CheckTiming(init_seconds=0.001, pass_seconds=0.002, pass_count=2),
            "b": CheckTiming(fail_seconds=0.005, fail_count=1),
        }
        table = check_timing_table(timings, ["a", "b", "not-timed"])
        console = Console(record=True, width=120)
        console.print(table)
        output = console.export_text()
        assert "init (1x)" in output
        assert "a" in output
        assert "b" in output
        assert "not-timed" not in output
        assert "1.0ms" in output
        assert "2 × 1.0ms = 2.0ms" in output
        assert "-" in output
        assert "1 × 5.0ms = 5.0ms" in output
        assert "3.0ms" in output
