import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.path.check_track_filename import CheckTrackFilename
from albums.types import Album, BasicTag, Track


class TestCheckTrackFilename:
    def test_track_filename_ok(self):
        tracks = [
            Track("1 foo.flac", {BasicTag.TRACKNUMBER: ["1"], BasicTag.TITLE: ["foo"]}),
            Track("2 bar.flac", {BasicTag.TRACKNUMBER: ["2"], BasicTag.TITLE: ["bar"]}),
        ]
        assert not CheckTrackFilename(Context()).check(Album("", tracks))

    def test_track_filename_ok_custom_format(self):
        tracks = [
            Track("1 - foo.flac", {BasicTag.TRACKNUMBER: ["1"], BasicTag.TITLE: ["foo"]}),
            Track("2 - bar.flac", {BasicTag.TRACKNUMBER: ["2"], BasicTag.TITLE: ["bar"]}),
        ]
        ctx = Context()
        ctx.config.checks["track-filename"]["format"] = "$track_auto - $title_auto"
        assert not CheckTrackFilename(ctx).check(Album("", tracks))

    def test_track_filename_ok_custom_format_more(self):
        tracks = [
            Track(
                "[disc 1 track 1] baz - foo.flac",
                {BasicTag.DISCNUMBER: ["1"], BasicTag.TRACKNUMBER: ["1"], BasicTag.ARTIST: ["baz"], BasicTag.TITLE: ["foo"]},
            ),
            Track(
                "[disc 1 track 2] baz - bar.flac",
                {BasicTag.DISCNUMBER: ["1"], BasicTag.TRACKNUMBER: ["2"], BasicTag.ARTIST: ["baz"], BasicTag.TITLE: ["bar"]},
            ),
        ]
        ctx = Context()
        ctx.config.checks["track-filename"]["format"] = "[disc $discnumber track $tracknumber] $artist / $title"  # "/" will become "-"
        assert not CheckTrackFilename(ctx).check(Album("", tracks))

    def test_track_filename_ok_no_title(self):
        tracks = [
            Track("1 Track 1.flac", {BasicTag.TRACKNUMBER: ["1"]}),
            Track("2 Track 2.flac", {BasicTag.TRACKNUMBER: ["2"]}),
        ]
        assert not CheckTrackFilename(Context()).check(Album("", tracks))

    def test_track_filename_disc_ok(self):
        tracks = [
            Track("2-01 foo.flac", {BasicTag.DISCNUMBER: ["2"], BasicTag.TRACKNUMBER: ["01"], BasicTag.TITLE: ["foo"]}),
            Track("2-02 bar.flac", {BasicTag.DISCNUMBER: ["2"], BasicTag.TRACKNUMBER: ["02"], BasicTag.TITLE: ["bar"]}),
        ]
        assert not CheckTrackFilename(Context()).check(Album("", tracks))

    def test_track_filename_albumartist_ok(self):
        tracks = [
            Track(
                "1 baz - foo.flac",
                {BasicTag.TRACKNUMBER: ["1"], BasicTag.TITLE: ["foo"], BasicTag.ARTIST: ["baz"], BasicTag.ALBUMARTIST: ["Various Artists"]},
            ),
            Track(
                "2 mob - bar.flac",
                {BasicTag.TRACKNUMBER: ["2"], BasicTag.TITLE: ["bar"], BasicTag.ARTIST: ["mob"], BasicTag.ALBUMARTIST: ["Various Artists"]},
            ),
        ]
        assert not CheckTrackFilename(Context()).check(Album("", tracks))

    def test_track_filename_guest_artist_ok(self):
        tracks = [
            Track("1 foo.flac", {BasicTag.TRACKNUMBER: ["1"], BasicTag.TITLE: ["foo"], BasicTag.ARTIST: ["baz"], BasicTag.ALBUMARTIST: ["baz"]}),
            Track(
                "2 mob - bar.flac", {BasicTag.TRACKNUMBER: ["2"], BasicTag.TITLE: ["bar"], BasicTag.ARTIST: ["mob"], BasicTag.ALBUMARTIST: ["baz"]}
            ),
        ]
        assert not CheckTrackFilename(Context()).check(Album("", tracks))

    def test_track_filename_not_unique(self):
        tracks = [
            Track("1.flac", {BasicTag.TRACKNUMBER: ["1"], BasicTag.TITLE: ["foo"]}),
            Track("2.flac", {BasicTag.TRACKNUMBER: ["1"], BasicTag.TITLE: ["foo"]}),
        ]
        result = CheckTrackFilename(Context()).check(Album("", tracks))
        assert result
        assert "unable to generate unique filenames" in result.message

    def test_track_filename_blank(self):
        tracks = [
            Track("1.flac", {BasicTag.TRACKNUMBER: ["1"], BasicTag.TITLE: ["foo"]}),
            Track("2.flac"),
        ]
        result = CheckTrackFilename(Context()).check(Album("", tracks))
        assert result
        assert "cannot generate filenames that start with . character" in result.message

    def test_track_filename_set(self, mocker):
        tracks = [
            Track("1.flac", {BasicTag.TRACKNUMBER: ["1"], BasicTag.TITLE: ["foo"]}),
            Track("2.flac", {BasicTag.TRACKNUMBER: ["2"], BasicTag.TITLE: ["bar"]}),
            Track("3 is correct.flac", {BasicTag.TRACKNUMBER: ["3"], BasicTag.TITLE: ["is correct"]}),
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

    def test_track_filename_pad_m4a(self, mocker):
        # these track numbers get padding per default zero-pad-numbers settings because m4a track numbers are numeric and cannot store formatting
        tracks = [
            Track("1.m4a", {BasicTag.TRACKNUMBER: ["1"], BasicTag.TITLE: ["one"]}),
            Track("2.m4a", {BasicTag.TRACKNUMBER: ["2"], BasicTag.TITLE: ["two"]}),
            Track("3.m4a", {BasicTag.TRACKNUMBER: ["3"], BasicTag.TITLE: ["three"]}),
            Track("4.m4a", {BasicTag.TRACKNUMBER: ["4"], BasicTag.TITLE: ["four"]}),
            Track("5.m4a", {BasicTag.TRACKNUMBER: ["5"], BasicTag.TITLE: ["five"]}),
            Track("6.m4a", {BasicTag.TRACKNUMBER: ["6"], BasicTag.TITLE: ["six"]}),
            Track("7.m4a", {BasicTag.TRACKNUMBER: ["7"], BasicTag.TITLE: ["seven"]}),
            Track("8.m4a", {BasicTag.TRACKNUMBER: ["8"], BasicTag.TITLE: ["eight"]}),
            Track("9.m4a", {BasicTag.TRACKNUMBER: ["9"], BasicTag.TITLE: ["nine"]}),
            Track("10.m4a", {BasicTag.TRACKNUMBER: ["10"], BasicTag.TITLE: ["ten"]}),
        ]
        album = Album("foo" + os.sep, tracks)
        result = CheckTrackFilename(Context()).check(album)
        assert result
        assert "track filenames do not match configured pattern" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Use generated filenames"]
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.path.check_track_filename.rename")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_rename.call_args_list == [
            call(Path(album.path) / "1.m4a", Path(album.path) / "01 one.m4a"),
            call(Path(album.path) / "2.m4a", Path(album.path) / "02 two.m4a"),
            call(Path(album.path) / "3.m4a", Path(album.path) / "03 three.m4a"),
            call(Path(album.path) / "4.m4a", Path(album.path) / "04 four.m4a"),
            call(Path(album.path) / "5.m4a", Path(album.path) / "05 five.m4a"),
            call(Path(album.path) / "6.m4a", Path(album.path) / "06 six.m4a"),
            call(Path(album.path) / "7.m4a", Path(album.path) / "07 seven.m4a"),
            call(Path(album.path) / "8.m4a", Path(album.path) / "08 eight.m4a"),
            call(Path(album.path) / "9.m4a", Path(album.path) / "09 nine.m4a"),
            call(Path(album.path) / "10.m4a", Path(album.path) / "10 ten.m4a"),
        ]

    def test_track_filename_use_formatted_tag(self, mocker):
        # unlike above test, these track numbers will not get padding because ID3 track numbers are formatted strings
        tracks = [
            Track("1.mp3", {BasicTag.TRACKNUMBER: ["1"], BasicTag.TITLE: ["one"]}),
            Track("2.mp3", {BasicTag.TRACKNUMBER: ["2"], BasicTag.TITLE: ["two"]}),
            Track("3.mp3", {BasicTag.TRACKNUMBER: ["3"], BasicTag.TITLE: ["three"]}),
            Track("4.mp3", {BasicTag.TRACKNUMBER: ["4"], BasicTag.TITLE: ["four"]}),
            Track("5.mp3", {BasicTag.TRACKNUMBER: ["5"], BasicTag.TITLE: ["five"]}),
            Track("6.mp3", {BasicTag.TRACKNUMBER: ["6"], BasicTag.TITLE: ["six"]}),
            Track("7.mp3", {BasicTag.TRACKNUMBER: ["7"], BasicTag.TITLE: ["seven"]}),
            Track("8.mp3", {BasicTag.TRACKNUMBER: ["8"], BasicTag.TITLE: ["eight"]}),
            Track("9.mp3", {BasicTag.TRACKNUMBER: ["9"], BasicTag.TITLE: ["nine"]}),
            Track("10.mp3", {BasicTag.TRACKNUMBER: ["10"], BasicTag.TITLE: ["ten"]}),
        ]
        album = Album("foo" + os.sep, tracks)
        result = CheckTrackFilename(Context()).check(album)
        assert result
        assert "track filenames do not match configured pattern" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Use generated filenames"]
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.path.check_track_filename.rename")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_rename.call_args_list == [
            call(Path(album.path) / "1.mp3", Path(album.path) / "1 one.mp3"),
            call(Path(album.path) / "2.mp3", Path(album.path) / "2 two.mp3"),
            call(Path(album.path) / "3.mp3", Path(album.path) / "3 three.mp3"),
            call(Path(album.path) / "4.mp3", Path(album.path) / "4 four.mp3"),
            call(Path(album.path) / "5.mp3", Path(album.path) / "5 five.mp3"),
            call(Path(album.path) / "6.mp3", Path(album.path) / "6 six.mp3"),
            call(Path(album.path) / "7.mp3", Path(album.path) / "7 seven.mp3"),
            call(Path(album.path) / "8.mp3", Path(album.path) / "8 eight.mp3"),
            call(Path(album.path) / "9.mp3", Path(album.path) / "9 nine.mp3"),
            call(Path(album.path) / "10.mp3", Path(album.path) / "10 ten.mp3"),
        ]

    def test_track_filename_swap(self, mocker):
        tracks = [
            Track("1 foo.flac", {BasicTag.TRACKNUMBER: ["2"], BasicTag.TITLE: ["bar"]}),
            Track("2 bar.flac", {BasicTag.TRACKNUMBER: ["1"], BasicTag.TITLE: ["foo"]}),
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
            Track("1.flac", {BasicTag.TRACKNUMBER: ["1"], BasicTag.TITLE: ["foo?bar"]}),
            Track("2.flac", {BasicTag.TRACKNUMBER: ["2"], BasicTag.TITLE: ["baz/baz"]}),
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
            Track("1.flac", {BasicTag.TRACKNUMBER: ["1"], BasicTag.TITLE: ["foo?bar"]}),
            Track("2.flac", {BasicTag.TRACKNUMBER: ["2"], BasicTag.TITLE: ["baz/baz"]}),
        ]
        album = Album("foobar" + os.sep, tracks)
        ctx = Context()
        ctx.config.path_replace_invalid = "_"
        ctx.config.path_replace_slash = ", "
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
