from albums.app import Context
from albums.checks.check_disc_numbering import CheckDiscNumbering
from albums.types import Album, Track


class TestCheckDiscNumbering:
    def test_disc_numbering_ok(self):
        album = Album(
            "",
            [
                Track("1-01.flac", {"discnumber": ["1"], "disctotal": ["2"]}),
                Track("1-02.flac", {"discnumber": ["1"], "disctotal": ["2"]}),
                Track("2-01.flac", {"discnumber": ["2"], "disctotal": ["2"]}),
                Track("2-02.flac", {"discnumber": ["2"], "disctotal": ["2"]}),
            ],
        )
        result = CheckDiscNumbering(Context()).check(album)
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
        result = CheckDiscNumbering(Context()).check(album)
        assert "some tracks have disc number and some do not" in result.message
        assert result.fixer is None

    # TODO missing/unexpected disc numbers
