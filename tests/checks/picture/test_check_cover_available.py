import os
from pathlib import Path
from unittest.mock import call, mock_open, patch

from albums.app import Context
from albums.checks.picture.check_cover_available import CheckCoverAvailable
from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import Picture, PictureType, StreamInfo, TaggerFile
from albums.types import Album, PictureFile, Track

from ...fixtures.create_library import make_image_data


class TestCheckCoverAvailable:
    def test_cover_missing_ok(self):
        album = Album("", [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC")), Track("2.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"))])
        assert not CheckCoverAvailable(Context()).check(album)

    def test_cover_missing_required(self):
        album = Album("", [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC")), Track("2.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"))])
        ctx = Context()
        ctx.config.checks = {CheckCoverAvailable.name: {"cover_required": True}}
        result = CheckCoverAvailable(ctx).check(album)
        assert result is not None
        assert "album does not have a COVER_FRONT picture" in result.message

    def test_album_pictures_but_no_front_cover(self, mocker):
        album = Album(
            "foo" + os.sep,
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_BACK, "", ())],
                ),
                Track(
                    "2.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_BACK, "", ())],
                ),
            ],
        )
        result = CheckCoverAvailable(Context()).check(album)
        assert result is not None
        assert "album has pictures but none is COVER_FRONT picture" in result.message
        assert result.fixer is not None
        assert result.fixer.options == ["1.flac (and 1 more) image/png COVER_BACK"]
        assert result.fixer.option_automatic_index == 0

        tagger = TaggerFile()
        image_data = make_image_data()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_get_image_data = mocker.patch.object(tagger, "get_image_data", return_value=image_data)

        m_open = mock_open()
        with patch("builtins.open", m_open):
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_get_image_data.call_count == 1
        m_open.assert_has_calls(
            [
                call(Path(".") / album.path / "cover.png", "wb"),
                call().__enter__(),
                call().write(image_data),
                call().__exit__(None, None, None),
            ],
        )

    def test_album_picture_files_no_front_cover(self, mocker):
        album = Album(
            "",
            [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC")), Track("2.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"))],
            [],
            [],
            {"other.png": PictureFile(Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.OTHER, "", ()), 0, False)},
        )
        result = CheckCoverAvailable(Context()).check(album)
        assert result is not None
        assert "album has pictures but none is COVER_FRONT picture" in result.message

        assert result.fixer is not None
        assert result.fixer.options == ["other.png image/png OTHER"]
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.picture.check_cover_available.rename")
        result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_rename.call_args_list == [call(Path(".") / album.path / "other.png", Path(".") / album.path / "cover.png")]

    def test_no_cover_prefer_rename(self, mocker):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.OTHER, "", ())],
                ),
                Track(
                    "2.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.OTHER, "", ())],
                ),
            ],
            [],
            [],
            {"other.png": PictureFile(Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.OTHER, "", ()), 0, False)},
        )
        result = CheckCoverAvailable(Context()).check(album)
        assert result is not None
        assert "album has pictures but none is COVER_FRONT picture" in result.message

        assert result.fixer is not None
        assert result.fixer.options == ["1.flac (and 2 more) image/png OTHER"]
        assert result.fixer.option_automatic_index == 0

        # same image was found embedded and in other.png - rename other.png instead of creating new cover.png
        mock_rename = mocker.patch("albums.checks.picture.check_cover_available.rename")
        result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_rename.call_args_list == [call(Path(".") / album.path / "other.png", Path(".") / album.path / "cover.png")]
