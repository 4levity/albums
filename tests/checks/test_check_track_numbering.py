from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.check_track_numbering import CheckTrackNumbering
from albums.types import Album, Track


class TestCheckTrackNumbering:
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

    def test_check_tracktotal_policy(self):
        # just make sure config works, policy helper has its own tests for fixer
        album_with_all = Album(
            "",
            [
                Track("1.flac", {"tracknumber": ["1"], "tracktotal": ["2"]}),
                Track("2.flac", {"tracknumber": ["2"], "tracktotal": ["2"]}),
            ],
        )
        album_with_none = Album(
            "",
            [Track("1.flac", {"tracknumber": ["1"]}), Track("2.flac", {"tracknumber": ["2"]})],
        )
        ctx = Context()
        ctx.config["checks"] = {CheckTrackNumbering.name: {"tracktotal_policy": "consistent"}}  # default
        check = CheckTrackNumbering(ctx)
        result = check.check(album_with_all)
        assert result is None
        result = check.check(album_with_none)
        assert result is None

        ctx.config["checks"] = {CheckTrackNumbering.name: {"tracktotal_policy": "always"}}
        check = CheckTrackNumbering(ctx)
        assert check.check(album_with_all) is None
        result = check.check(album_with_none)
        assert result
        assert "tracktotal policy=ALWAYS but it is not on all tracks" in result.message

        ctx.config["checks"] = {CheckTrackNumbering.name: {"tracktotal_policy": "never"}}
        check = CheckTrackNumbering(ctx)
        assert check.check(album_with_none) is None
        result = check.check(album_with_all)
        assert result
        assert "tracktotal policy=NEVER but it appears on tracks" in result.message

    def test_check_track_total_inconsistent(self, mocker):
        album = Album(
            "Foo/",
            [
                Track("1.flac", {"tracknumber": ["1"], "tracktotal": ["2"]}),
                Track("2.flac", {"tracknumber": ["2"], "tracktotal": ["2"]}),
                Track("3.flac", {"tracknumber": ["3"], "tracktotal": ["3"]}),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "some tracks have different track total values" in result.message
        fixer = result.fixer
        assert fixer
        assert fixer.options == [">> Set tracktotal to number of tracks: 3"]
        assert fixer.option_automatic_index == 0
        mock_set_basic_tags = mocker.patch("albums.checks.check_track_numbering.set_basic_tags")
        assert fixer.fix(fixer.options[fixer.option_automatic_index])
        path = Path(album.path)
        assert mock_set_basic_tags.call_args_list == [
            call(path / album.tracks[0].filename, [("tracktotal", "3")]),
            call(path / album.tracks[1].filename, [("tracktotal", "3")]),
        ]

    def test_check_track_number_missing(self, mocker):
        album = Album("Foo/", [Track("1.flac"), Track("2.flac"), Track("3.flac")])
        result = CheckTrackNumbering(Context()).check(album)
        assert "missing track numbers {1, 2, 3}" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Automatically renumber 3 tracks based on filenames"]
        assert result.fixer.option_automatic_index == 0
        mock_set_basic_tags = mocker.patch("albums.checks.check_track_numbering.set_basic_tags")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        path = Path(album.path)
        assert mock_set_basic_tags.call_args_list == [
            call(path / album.tracks[0].filename, [("tracknumber", "1")]),
            call(path / album.tracks[1].filename, [("tracknumber", "2")]),
            call(path / album.tracks[2].filename, [("tracknumber", "3")]),
        ]

    def test_check_track_number_missing_on_one_disc(self, mocker):
        album = Album(
            "Foo/",
            [
                Track("1-1.flac", {"discnumber": ["1"]}),
                Track("1-2.flac", {"discnumber": ["1"]}),
                Track("2-1.flac", {"tracknumber": ["1"], "discnumber": ["2"]}),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "missing track numbers on disc 1 {1, 2}" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Automatically renumber 2 tracks based on filenames"]
        assert result.fixer.option_automatic_index == 0
        mock_set_basic_tags = mocker.patch("albums.checks.check_track_numbering.set_basic_tags")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        path = Path(album.path)
        assert mock_set_basic_tags.call_args_list == [
            call(path / album.tracks[0].filename, [("tracknumber", "1")]),
            call(path / album.tracks[1].filename, [("tracknumber", "2")]),
        ]

    def test_check_unexpected_track_number(self):
        album = Album(
            "Foo/",
            [
                Track("1.flac", {"tracknumber": ["1"], "tracktotal": ["2"]}),
                Track("2.flac", {"tracknumber": ["2"], "tracktotal": ["2"]}),
                Track("3.flac", {"tracknumber": ["3"], "tracktotal": ["2"]}),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "unexpected track numbers {3}" in result.message
        assert result.fixer is None

    def test_check_duplicate_track_number(self):
        album = Album(
            "Foo/",
            [
                Track("1 foo.flac", {"tracknumber": ["1"]}),
                Track("2 bar.flac", {"tracknumber": ["2"]}),
                Track("2 baz.flac", {"tracknumber": ["2"]}),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "duplicate track numbers [2]" in result.message
        assert result.fixer is None

    def test_check_missing_track_with_totals(self):
        album = Album(
            "Foo/",
            [
                Track("1.flac", {"tracknumber": ["1"], "tracktotal": ["4"]}),
                Track("2.flac", {"tracknumber": ["2"], "tracktotal": ["4"]}),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "tracks missing from album {3, 4}" in result.message
        assert result.fixer is None

    def test_check_missing_track_in_set(self):
        album = Album(
            "Foo/",
            [
                Track("1-1.flac", {"tracknumber": ["1"], "discnumber": ["1"]}),
                Track("1-2.flac", {"tracknumber": ["2"], "discnumber": ["1"]}),
                Track("2-1.flac", {"tracknumber": ["1"], "discnumber": ["2"]}),
                Track("2-4.flac", {"tracknumber": ["4"], "discnumber": ["2"]}),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "tracks missing from album on disc 2 {2, 3}" in result.message
        assert result.fixer is None

    def test_check_missing_track_without_totals(self):
        album = Album(
            "Foo/",
            [
                Track("1.flac", {"tracknumber": ["1"]}),
                Track("4.flac", {"tracknumber": ["4"]}),
            ],
        )
        result = CheckTrackNumbering(Context()).check(album)
        assert "tracks missing from album {2, 3}" in result.message
        assert result.fixer is None
