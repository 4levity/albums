import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.path.check_track_filename import CheckTrackFilename
from albums.database.models import AlbumEntity, TrackEntity, TrackTagEntity
from albums.types import BasicTag


class TestCheckTrackFilename:
    def test_track_filename_ok(self):
        tracks = [
            TrackEntity(
                filename="1 foo.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TITLE, value="foo")]
            ),
            TrackEntity(
                filename="2 bar.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"), TrackTagEntity(tag=BasicTag.TITLE, value="bar")]
            ),
        ]
        assert not CheckTrackFilename(Context()).check(AlbumEntity(path="", tracks=tracks))

    def test_track_filename_ok_custom_format(self):
        tracks = [
            TrackEntity(
                filename="1 - foo.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TITLE, value="foo")]
            ),
            TrackEntity(
                filename="2 - bar.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"), TrackTagEntity(tag=BasicTag.TITLE, value="bar")]
            ),
        ]
        ctx = Context()
        ctx.config.checks["track-filename"]["format"] = "$track_auto - $title_auto"
        assert not CheckTrackFilename(ctx).check(AlbumEntity(path="", tracks=tracks))

    def test_track_filename_ok_custom_format_more(self):
        tracks = [
            TrackEntity(
                filename="[disc 1 track 1] baz - foo.flac",
                tags=[
                    TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1"),
                    TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"),
                    TrackTagEntity(tag=BasicTag.ARTIST, value="baz"),
                    TrackTagEntity(tag=BasicTag.TITLE, value="foo"),
                ],
            ),
            TrackEntity(
                filename="[disc 1 track 2] baz - bar.flac",
                tags=[
                    TrackTagEntity(tag=BasicTag.DISCNUMBER, value="1"),
                    TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"),
                    TrackTagEntity(tag=BasicTag.ARTIST, value="baz"),
                    TrackTagEntity(tag=BasicTag.TITLE, value="bar"),
                ],
            ),
        ]
        ctx = Context()
        ctx.config.checks["track-filename"]["format"] = "[disc $discnumber track $tracknumber] $artist / $title"  # "/" will become "-"
        assert not CheckTrackFilename(ctx).check(AlbumEntity(path="", tracks=tracks))

    def test_track_filename_ok_no_title(self):
        tracks = [
            TrackEntity(filename="1 Track 1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1")]),
            TrackEntity(filename="2 Track 2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2")]),
        ]
        assert not CheckTrackFilename(Context()).check(AlbumEntity(path="", tracks=tracks))

    def test_track_filename_disc_ok(self):
        tracks = [
            TrackEntity(
                filename="2-01 foo.flac",
                tags=[
                    TrackTagEntity(tag=BasicTag.DISCNUMBER, value="2"),
                    TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="01"),
                    TrackTagEntity(tag=BasicTag.TITLE, value="foo"),
                ],
            ),
            TrackEntity(
                filename="2-02 bar.flac",
                tags=[
                    TrackTagEntity(tag=BasicTag.DISCNUMBER, value="2"),
                    TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="02"),
                    TrackTagEntity(tag=BasicTag.TITLE, value="bar"),
                ],
            ),
        ]
        assert not CheckTrackFilename(Context()).check(AlbumEntity(path="", tracks=tracks))

    def test_track_filename_albumartist_ok(self):
        tracks = [
            TrackEntity(
                filename="1 baz - foo.flac",
                tags=[
                    TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"),
                    TrackTagEntity(tag=BasicTag.TITLE, value="foo"),
                    TrackTagEntity(tag=BasicTag.ARTIST, value="baz"),
                    TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Various Artists"),
                ],
            ),
            TrackEntity(
                filename="2 mob - bar.flac",
                tags=[
                    TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"),
                    TrackTagEntity(tag=BasicTag.TITLE, value="bar"),
                    TrackTagEntity(tag=BasicTag.ARTIST, value="mob"),
                    TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="Various Artists"),
                ],
            ),
        ]
        assert not CheckTrackFilename(Context()).check(AlbumEntity(path="", tracks=tracks))

    def test_track_filename_guest_artist_ok(self):
        tracks = [
            TrackEntity(
                filename="1 foo.flac",
                tags=[
                    TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"),
                    TrackTagEntity(tag=BasicTag.TITLE, value="foo"),
                    TrackTagEntity(tag=BasicTag.ARTIST, value="baz"),
                    TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="baz"),
                ],
            ),
            TrackEntity(
                filename="2 mob - bar.flac",
                tags=[
                    TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"),
                    TrackTagEntity(tag=BasicTag.TITLE, value="bar"),
                    TrackTagEntity(tag=BasicTag.ARTIST, value="mob"),
                    TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="baz"),
                ],
            ),
        ]
        assert not CheckTrackFilename(Context()).check(AlbumEntity(path="", tracks=tracks))

    def test_track_filename_not_unique(self):
        tracks = [
            TrackEntity(
                filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TITLE, value="foo")]
            ),
            TrackEntity(
                filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TITLE, value="foo")]
            ),
        ]
        result = CheckTrackFilename(Context()).check(AlbumEntity(path="", tracks=tracks))
        assert result
        assert "unable to generate unique filenames" in result.message

    def test_track_filename_blank(self):
        tracks = [
            TrackEntity(
                filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TITLE, value="foo")]
            ),
            TrackEntity(filename="2.flac"),
        ]
        result = CheckTrackFilename(Context()).check(AlbumEntity(path="", tracks=tracks))
        assert result
        assert "cannot generate filenames that start with . character" in result.message

    def test_track_filename_set(self, mocker):
        tracks = [
            TrackEntity(
                filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TITLE, value="foo")]
            ),
            TrackEntity(
                filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"), TrackTagEntity(tag=BasicTag.TITLE, value="bar")]
            ),
            TrackEntity(
                filename="3 is correct.flac",
                tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="3"), TrackTagEntity(tag=BasicTag.TITLE, value="is correct")],
            ),
        ]
        album = AlbumEntity(path="foobar" + os.sep, tracks=tracks)
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
            TrackEntity(
                filename="1.m4a", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TITLE, value="one")]
            ),
            TrackEntity(
                filename="2.m4a", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"), TrackTagEntity(tag=BasicTag.TITLE, value="two")]
            ),
            TrackEntity(
                filename="3.m4a", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="3"), TrackTagEntity(tag=BasicTag.TITLE, value="three")]
            ),
            TrackEntity(
                filename="4.m4a", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="4"), TrackTagEntity(tag=BasicTag.TITLE, value="four")]
            ),
            TrackEntity(
                filename="5.m4a", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="5"), TrackTagEntity(tag=BasicTag.TITLE, value="five")]
            ),
            TrackEntity(
                filename="6.m4a", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="6"), TrackTagEntity(tag=BasicTag.TITLE, value="six")]
            ),
            TrackEntity(
                filename="7.m4a", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="7"), TrackTagEntity(tag=BasicTag.TITLE, value="seven")]
            ),
            TrackEntity(
                filename="8.m4a", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="8"), TrackTagEntity(tag=BasicTag.TITLE, value="eight")]
            ),
            TrackEntity(
                filename="9.m4a", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="9"), TrackTagEntity(tag=BasicTag.TITLE, value="nine")]
            ),
            TrackEntity(
                filename="10.m4a", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="10"), TrackTagEntity(tag=BasicTag.TITLE, value="ten")]
            ),
        ]
        album = AlbumEntity(path="foo" + os.sep, tracks=tracks)
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
            TrackEntity(
                filename="1.mp3", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TITLE, value="one")]
            ),
            TrackEntity(
                filename="2.mp3", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"), TrackTagEntity(tag=BasicTag.TITLE, value="two")]
            ),
            TrackEntity(
                filename="3.mp3", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="3"), TrackTagEntity(tag=BasicTag.TITLE, value="three")]
            ),
            TrackEntity(
                filename="4.mp3", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="4"), TrackTagEntity(tag=BasicTag.TITLE, value="four")]
            ),
            TrackEntity(
                filename="5.mp3", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="5"), TrackTagEntity(tag=BasicTag.TITLE, value="five")]
            ),
            TrackEntity(
                filename="6.mp3", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="6"), TrackTagEntity(tag=BasicTag.TITLE, value="six")]
            ),
            TrackEntity(
                filename="7.mp3", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="7"), TrackTagEntity(tag=BasicTag.TITLE, value="seven")]
            ),
            TrackEntity(
                filename="8.mp3", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="8"), TrackTagEntity(tag=BasicTag.TITLE, value="eight")]
            ),
            TrackEntity(
                filename="9.mp3", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="9"), TrackTagEntity(tag=BasicTag.TITLE, value="nine")]
            ),
            TrackEntity(
                filename="10.mp3", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="10"), TrackTagEntity(tag=BasicTag.TITLE, value="ten")]
            ),
        ]
        album = AlbumEntity(path="foo" + os.sep, tracks=tracks)
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
            TrackEntity(
                filename="1 foo.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"), TrackTagEntity(tag=BasicTag.TITLE, value="bar")]
            ),
            TrackEntity(
                filename="2 bar.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TITLE, value="foo")]
            ),
        ]
        album = AlbumEntity(path="foobar" + os.sep, tracks=tracks)
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
            TrackEntity(
                filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TITLE, value="foo?bar")]
            ),
            TrackEntity(
                filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"), TrackTagEntity(tag=BasicTag.TITLE, value="baz/baz")]
            ),
        ]
        album = AlbumEntity(path="foobar" + os.sep, tracks=tracks)
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
            TrackEntity(
                filename="1.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"), TrackTagEntity(tag=BasicTag.TITLE, value="foo?bar")]
            ),
            TrackEntity(
                filename="2.flac", tags=[TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="2"), TrackTagEntity(tag=BasicTag.TITLE, value="baz/baz")]
            ),
        ]
        album = AlbumEntity(path="foobar" + os.sep, tracks=tracks)
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
