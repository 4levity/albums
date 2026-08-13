import os
from pathlib import Path
from unittest.mock import call

from albums.app import Context
from albums.checks.path.check_file_extension import CheckFileExtension
from albums.entities import Album, OtherFile, PictureFile, Track
from albums.picture import PictureInfo


class TestCheckFileExtension:
    def test_extension_ok(self):
        album = Album(
            path="foo" + os.sep,
            tracks=[Track(filename="normal.mp3")],
            picture_files=[PictureFile(filename="normal.JPG", picture_info=PictureInfo("image/png", 1, 1, 24, 1, b""))],
            other_files=[OtherFile(filename="random.TXT")],
        )
        assert not CheckFileExtension(Context()).check(album)

    def test_extension_ok_all(self):
        album = Album(
            path="foo" + os.sep,
            tracks=[Track(filename="normal.mp3")],
            picture_files=[PictureFile(filename="normal.jpg", picture_info=PictureInfo("image/png", 1, 1, 24, 1, b""))],
            other_files=[OtherFile(filename="random.txt")],
        )
        ctx = Context()
        ctx.config.checks[CheckFileExtension.name]["lowercase_all"] = True
        assert not CheckFileExtension(ctx).check(album)

    def test_extension_conflict(self):
        album = Album(
            path="foo" + os.sep,
            tracks=[Track(filename="normal.MP4")],
            other_files=[OtherFile(filename="normal.mp4")],
        )
        result = CheckFileExtension(Context()).check(album)
        assert result is not None
        assert (
            'bad file extension, example "normal.MP4" should be "normal.mp4" (automatic fix not possible due to filename conflict)' in result.message
        )
        assert result.fixer is None

    def test_extension_fix(self, mocker):
        album = Album(path="foo" + os.sep, tracks=[Track(filename="upper.MP3")])
        result = CheckFileExtension(Context()).check(album)
        assert result is not None
        assert 'bad file extension, example "upper.MP3" should be "upper.mp3"' in result.message
        assert result.fixer is not None
        assert result.fixer.options == [">> Change file extensions"]
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.path.check_file_extension.rename")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_rename.call_args_list == [
            call(Path(album.path) / "upper.MP3", Path(album.path) / "upper.0"),
            call(Path(album.path) / "upper.0", Path(album.path) / "upper.mp3"),
        ]

    def test_extension_fix_all(self, mocker):
        album = Album(
            path="foo" + os.sep,
            tracks=[Track(filename="TRACK.MP3")],
            picture_files=[PictureFile(filename="COVER.PNG", picture_info=PictureInfo("image/png", 1, 1, 24, 1, b""))],
            other_files=[OtherFile(filename="VIDEO.MP4"), OtherFile(filename="OVERSIZE.BMP")],
        )

        ctx = Context()
        ctx.config.checks[CheckFileExtension.name]["lowercase_all"] = True
        result = CheckFileExtension(ctx).check(album)
        assert result is not None
        assert 'bad file extensions, example "COVER.PNG" should be "COVER.png"' in result.message
        assert result.fixer is not None
        assert result.fixer.options == [">> Change file extensions"]
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.path.check_file_extension.rename")
        assert result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_rename.call_args_list == [
            call(Path(album.path) / "COVER.PNG", Path(album.path) / "COVER.0"),
            call(Path(album.path) / "OVERSIZE.BMP", Path(album.path) / "OVERSIZE.0"),
            call(Path(album.path) / "TRACK.MP3", Path(album.path) / "TRACK.0"),
            call(Path(album.path) / "VIDEO.MP4", Path(album.path) / "VIDEO.0"),
            call(Path(album.path) / "COVER.0", Path(album.path) / "COVER.png"),
            call(Path(album.path) / "OVERSIZE.0", Path(album.path) / "OVERSIZE.bmp"),
            call(Path(album.path) / "TRACK.0", Path(album.path) / "TRACK.mp3"),
            call(Path(album.path) / "VIDEO.0", Path(album.path) / "VIDEO.mp4"),
        ]
