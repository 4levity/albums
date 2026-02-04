from pathlib import Path

from albums.app import Context
from albums.checks.check_track_numbering import CheckTrackNumbering
from albums.types import Album, Track


class TestCheckTrackNumbering:
    def test_check_track_number_missing(self):
        album = Album("Foo/", [Track("1.flac"), Track("2.flac"), Track("3.flac")])
        result = CheckTrackNumbering(Context()).check(album)
        assert "missing track numbers or tags {1, 2, 3}" in result.message

    def test_check_track_number_missing_disc(self):
        album = Album(
            "Foo/",
            [
                Track("1-1.flac", {"discnumber": ["1"]}),
                Track("1-2.flac", {"discnumber": ["1"]}),
                Track("2-1.flac", {"tracknumber": ["1"], "discnumber": ["2"]}),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "missing track numbers or tags on disc 1 {1, 2}" in result.message

    def test_check_track_numbering_ok(self):
        album = Album(
            "Foo/",
            [
                Track("1.flac", {"tracknumber": ["1"]}),
                Track("2.flac", {"tracknumber": ["2"]}),
                Track("3.flac", {"tracknumber": ["3"]}),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
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
        result = CheckTrackNumbering(Context()).check(album)
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
        result = CheckTrackNumbering(Context()).check(album)
        assert result is None

    def test_check_track_total_missing(self, mocker):
        album = Album(
            "Foo/",
            [
                Track("1.flac", {"tracknumber": ["1"], "tracktotal": ["3"]}),
                Track("2.flac", {"tracknumber": ["2"], "tracktotal": ["3"]}),
                Track("3.flac", {"tracknumber": ["3"]}),
            ],
        )
        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        result = CheckTrackNumbering(ctx).check(album)
        assert "tracktotal = 3 is not set on all tracks" in result.message
        fixer = result.fixer
        assert fixer
        assert fixer.options == [">> Set tracktotal to number of tracks: 3", ">> Set tracktotal to maximum value seen: 3"]
        mock_set_basic_tags = mocker.patch("albums.checks.check_track_numbering.set_basic_tags")
        assert fixer.fix(fixer.options[0])
        assert mock_set_basic_tags.call_count == 1
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album.path / album.tracks[2].filename, [("tracktotal", "3")])

    def test_check_track_total_missing_and_disagrees(self, mocker):
        album = Album(
            "Foo/",
            [
                Track("1.flac", {"tracknumber": ["1"], "tracktotal": ["4"]}),
                Track("2.flac", {"tracknumber": ["2"], "tracktotal": ["4"]}),
                Track("3.flac", {"tracknumber": ["3"]}),
            ],
        )
        ctx = Context()
        ctx.library_root = Path("/path/to/library")
        result = CheckTrackNumbering(ctx).check(album)
        assert "tracktotal = 4 is set on 2/3 tracks" in result.message
        fixer = result.fixer
        assert fixer
        assert fixer.options == [">> Set tracktotal to number of tracks: 3", ">> Set tracktotal to maximum value seen: 4"]
        mock_set_basic_tags = mocker.patch("albums.checks.check_track_numbering.set_basic_tags")
        assert fixer.fix(fixer.options[0])
        assert mock_set_basic_tags.call_count == 3
        assert mock_set_basic_tags.call_args.args == (ctx.library_root / album.path / album.tracks[2].filename, [("tracktotal", "3")])
