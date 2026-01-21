from albums.app import Context
from albums.checks.check_track_number import CheckTrackNumber
from albums.types import Album, Track


class TestCheckTrackNumber:
    def test_check_track_number_missing(self):
        album = Album("Foo/", [Track("1.flac"), Track("2.flac"), Track("3.flac")])
        result = CheckTrackNumber(Context()).check(album)
        assert "missing expected track numbers {1, 2, 3}" in result.message

    def test_check_track_number_missing_disc(self):
        album = Album(
            "Foo/",
            [
                Track("1-1.flac", {"discnumber": ["1"]}),
                Track("1-2.flac", {"discnumber": ["1"]}),
                Track("2-1.flac", {"tracknumber": ["1"], "discnumber": ["2"]}),
            ],
        )
        result = CheckTrackNumber(Context()).check(album)
        assert "missing expected track numbers on disc 1 {1, 2}" in result.message

    def test_check_track_number_ok(self):
        album = Album(
            "Foo/",
            [
                Track("1.flac", {"tracknumber": ["1"]}),
                Track("2.flac", {"tracknumber": ["2"]}),
                Track("3.flac", {"tracknumber": ["3"]}),
            ],
        )
        result = CheckTrackNumber(Context()).check(album)
        assert result is None

    def test_check_track_number_total_ok(self):
        album = Album(
            "Foo/",
            [
                Track("1.flac", {"tracknumber": ["1"], "tracktotal": ["3"]}),
                Track("2.flac", {"tracknumber": ["2"], "tracktotal": ["3"]}),
                Track("3.flac", {"tracknumber": ["3"], "tracktotal": ["3"]}),
            ],
        )
        result = CheckTrackNumber(Context()).check(album)
        assert result is None

    def test_check_track_number_discs_total_ok(self):
        album = Album(
            "Foo/",
            [
                Track("1-1.flac", {"tracknumber": ["1"], "tracktotal": ["2"], "discnumber": ["1"], "disctotal": ["2"]}),
                Track("1-2.flac", {"tracknumber": ["2"], "tracktotal": ["2"], "discnumber": ["1"], "disctotal": ["2"]}),
                Track("2-1.flac", {"tracknumber": ["1"], "tracktotal": ["2"], "discnumber": ["2"], "disctotal": ["2"]}),
                Track("2-2.flac", {"tracknumber": ["2"], "tracktotal": ["2"], "discnumber": ["2"], "disctotal": ["2"]}),
            ],
        )
        result = CheckTrackNumber(Context()).check(album)
        assert result is None

    def test_check_track_number_discnumber_inconsistent(self):
        album = Album(
            "Foo/",
            [
                Track("1-1.flac", {"tracknumber": ["1"], "discnumber": ["1"]}),
                Track("1-2.flac", {"tracknumber": ["2"]}),
                Track("2-1.flac", {"tracknumber": ["1"], "discnumber": ["2"]}),
                Track("2-2.flac", {"tracknumber": ["2"], "discnumber": ["2"]}),
            ],
        )
        result = CheckTrackNumber(Context()).check(album)
        assert "some tracks have discnumber tag and some do not" in result.message

    def test_check_track_number_disctotal_inconsistent(self):
        album = Album(
            "Foo/",
            [
                Track("1-1.flac", {"tracknumber": ["1"], "discnumber": ["1"]}),
                Track("1-2.flac", {"tracknumber": ["2"], "discnumber": ["1"]}),
                Track("2-1.flac", {"tracknumber": ["1"], "discnumber": ["2"], "disctotal": ["2"]}),
                Track("2-2.flac", {"tracknumber": ["2"], "discnumber": ["2"], "disctotal": ["2"]}),
            ],
        )
        result = CheckTrackNumber(Context()).check(album)
        assert "some tracks have disctotal tag and some do not" in result.message

    def test_check_track_number_disc_in_tracknumber(self):
        album = Album(
            "Foo/",
            [
                Track("1-1.flac", {"tracknumber": ["1-1"]}),
                Track("1-2.flac", {"tracknumber": ["1-2"]}),
                Track("2-1.flac", {"tracknumber": ["2-1"]}),
                Track("2-2.flac", {"tracknumber": ["2-2"]}),
            ],
        )
        result = CheckTrackNumber(Context()).check(album)
        assert result.message == "issues: tracknumber tag contains disc number"

    def test_check_track_number_disc_in_tracknumber_parsed(self):
        album = Album(
            "Foo/",
            [
                Track("1-1.flac", {"tracknumber": ["1-1"]}),
                Track("1-2.flac", {"tracknumber": ["1-2"]}),
                Track("2-1.flac", {"tracknumber": ["2-1"], "tracktotal": ["3"]}),
                Track("2-2.flac", {"tracknumber": ["2-2"], "tracktotal": ["3"]}),
            ],
        )
        result = CheckTrackNumber(Context()).check(album)
        # reports problems on disc 2 based on parsing track number
        assert result.message == "issues: tracktotal = 3 is set on 2/2 tracks on disc 2, tracknumber tag contains disc number"
