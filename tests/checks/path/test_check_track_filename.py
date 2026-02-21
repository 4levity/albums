import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.path.check_track_filename import CheckTrackFilename
from albums.types import Album, Track


class TestCheckTrackFilename:
    def test_track_filename_ok(self):
        tracks = [
            Track("1 foo.flac", {"tracknumber": ["1"], "title": ["foo"]}),
            Track("2 bar.flac", {"tracknumber": ["2"], "title": ["bar"]}),
        ]
        assert not CheckTrackFilename(Context()).check(Album("", tracks))

    def test_track_filename_ok_custom_suffix(self):
        tracks = [
            Track("1 - foo.flac", {"tracknumber": ["1"], "title": ["foo"]}),
            Track("2 - bar.flac", {"tracknumber": ["2"], "title": ["bar"]}),
        ]
        ctx = Context()
        ctx.config.checks["track-filename"]["track_number_suffix"] = " - "
        assert not CheckTrackFilename(ctx).check(Album("", tracks))

    def test_track_filename_ok_no_title(self):
        tracks = [
            Track("1 Track 1.flac", {"tracknumber": ["1"]}),
            Track("2 Track 2.flac", {"tracknumber": ["2"]}),
        ]
        assert not CheckTrackFilename(Context()).check(Album("", tracks))

    def test_track_filename_disc_ok(self):
        tracks = [
            Track("2-01 foo.flac", {"discnumber": ["2"], "tracknumber": ["01"], "title": ["foo"]}),
            Track("2-02 bar.flac", {"discnumber": ["2"], "tracknumber": ["02"], "title": ["bar"]}),
        ]
        assert not CheckTrackFilename(Context()).check(Album("", tracks))

    def test_track_filename_albumartist_ok(self):
        tracks = [
            Track("1 baz - foo.flac", {"tracknumber": ["1"], "title": ["foo"], "artist": ["baz"], "albumartist": ["Various Artists"]}),
            Track("2 mob - bar.flac", {"tracknumber": ["2"], "title": ["bar"], "artist": ["mob"], "albumartist": ["Various Artists"]}),
        ]
        assert not CheckTrackFilename(Context()).check(Album("", tracks))

    def test_track_filename_guest_artist_ok(self):
        tracks = [
            Track("1 foo.flac", {"tracknumber": ["1"], "title": ["foo"], "artist": ["baz"], "albumartist": ["baz"]}),
            Track("2 mob - bar.flac", {"tracknumber": ["2"], "title": ["bar"], "artist": ["mob"], "albumartist": ["baz"]}),
        ]
        assert not CheckTrackFilename(Context()).check(Album("", tracks))

    def test_track_filename_not_unique(self):
        tracks = [
            Track("1.flac", {"tracknumber": ["1"], "title": ["foo"]}),
            Track("2.flac", {"tracknumber": ["1"], "title": ["foo"]}),
        ]
        result = CheckTrackFilename(Context()).check(Album("", tracks))
        assert result
        assert "unable to generate unique filenames" in result.message

    def test_track_filename_blank(self):
        tracks = [
            Track("1.flac", {"tracknumber": ["1"], "title": ["foo"]}),
            Track("2.flac"),
        ]
        result = CheckTrackFilename(Context()).check(Album("", tracks))
        assert result
        assert "cannot generate filenames that start with . character" in result.message

    def test_track_filename_set(self, mocker):
        tracks = [
            Track("1.flac", {"tracknumber": ["1"], "title": ["foo"]}),
            Track("2.flac", {"tracknumber": ["2"], "title": ["bar"]}),
            Track("3 is correct.flac", {"tracknumber": ["3"], "title": ["is correct"]}),
        ]
        album = Album("foobar" + os.sep, tracks)
        result = CheckTrackFilename(Context()).check(album)
        assert result
        assert "track filenames do not match configured pattern" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Use generated filenames"]
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.path.check_track_filename.rename")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_rename.call_args_list == [
            call(Path(album.path) / "1.flac", Path(album.path) / "1 foo.flac"),
            call(Path(album.path) / "2.flac", Path(album.path) / "2 bar.flac"),
        ]

    def test_track_filename_swap(self, mocker):
        tracks = [
            Track("1 foo.flac", {"tracknumber": ["2"], "title": ["bar"]}),
            Track("2 bar.flac", {"tracknumber": ["1"], "title": ["foo"]}),
        ]
        album = Album("foobar" + os.sep, tracks)
        result = CheckTrackFilename(Context()).check(album)
        assert result
        assert "track filenames do not match configured pattern" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Use generated filenames"]
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.path.check_track_filename.rename")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_rename.call_args_list == [
            call(Path(album.path) / "1 foo.flac", Path(album.path) / "1 foo.0"),
            call(Path(album.path) / "2 bar.flac", Path(album.path) / "2 bar.0"),
            call(Path(album.path) / "1 foo.0", Path(album.path) / "2 bar.flac"),
            call(Path(album.path) / "2 bar.0", Path(album.path) / "1 foo.flac"),
        ]

    def test_track_filename_set_illegal(self, mocker):
        tracks = [
            Track("1.flac", {"tracknumber": ["1"], "title": ["foo?bar"]}),
            Track("2.flac", {"tracknumber": ["2"], "title": ["baz/baz"]}),
        ]
        album = Album("foobar" + os.sep, tracks)
        result = CheckTrackFilename(Context()).check(album)
        assert result
        assert "track filenames do not match configured pattern" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Use generated filenames"]
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.path.check_track_filename.rename")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_rename.call_args_list == [
            call(Path(album.path) / "1.flac", Path(album.path) / "1 foobar.flac"),
            call(Path(album.path) / "2.flac", Path(album.path) / "2 baz-baz.flac"),
        ]

    def test_track_filename_set_illegal_custom(self, mocker):
        tracks = [
            Track("1.flac", {"tracknumber": ["1"], "title": ["foo?bar"]}),
            Track("2.flac", {"tracknumber": ["2"], "title": ["baz/baz"]}),
        ]
        album = Album("foobar" + os.sep, tracks)
        ctx = Context()
        ctx.config.checks["track-filename"]["replace_invalid"] = "_"
        ctx.config.checks["track-filename"]["replace_slash"] = ", "
        result = CheckTrackFilename(ctx).check(album)
        assert result
        assert "track filenames do not match configured pattern" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Use generated filenames"]
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.path.check_track_filename.rename")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_rename.call_args_list == [
            call(Path(album.path) / "1.flac", Path(album.path) / "1 foo_bar.flac"),
            call(Path(album.path) / "2.flac", Path(album.path) / "2 baz, baz.flac"),
        ]
