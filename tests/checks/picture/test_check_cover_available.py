import os
from pathlib import Path
from unittest.mock import call, mock_open, patch

from albums.app import Context
from albums.checks.picture.check_cover_available import CheckCoverAvailable
from albums.types import Album, Picture, PictureType, Stream, Track

from ...fixtures.create_library import make_image_data


class TestCheckCoverAvailable:
    def test_cover_missing_ok(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC")), Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))])
        assert not CheckCoverAvailable(Context()).check(album)

    def test_cover_missing_required(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC")), Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))])
        ctx = Context()
        ctx.config.checks = {CheckCoverAvailable.name: {"cover_required": True}}
        result = CheckCoverAvailable(ctx).check(album)
        assert result is not None
        assert "album does not have a COVER_FRONT picture" in result.message

    def test_album_pictures_but_no_front_cover(self, mocker):
        album = Album(
            "foo" + os.sep,
            [
                Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")]),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")]),
            ],
        )
        result = CheckCoverAvailable(Context()).check(album)
        assert result is not None
        assert "album has pictures but none is COVER_FRONT picture" in result.message
        assert result.fixer is not None
        assert result.fixer.options == ["1.flac#0 (and 1 more) image/png COVER_BACK"]
        assert result.fixer.option_automatic_index == 0

        image_data = make_image_data()
        mock_get_embedded_image_data = mocker.patch("albums.checks.picture.check_cover_available.get_embedded_image_data", return_value=[image_data])

        m_open = mock_open()
        with patch("builtins.open", m_open):
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_get_embedded_image_data.call_count == 1
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
            [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC")), Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))],
            [],
            [],
            {"other.png": Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")},
        )
        result = CheckCoverAvailable(Context()).check(album)
        assert result is not None
        assert "album has pictures but none is COVER_FRONT picture" in result.message

        assert result.fixer is not None
        assert result.fixer.options == ["other.png image/png COVER_BACK"]
        assert result.fixer.option_automatic_index == 0

        mock_rename = mocker.patch("albums.checks.picture.check_cover_available.rename")
        result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_rename.call_args_list == [call(Path(".") / album.path / "other.png", Path(".") / album.path / "cover.png")]

    def test_no_cover_prefer_rename(self, mocker):
        album = Album(
            "",
            [
                Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")]),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")]),
            ],
            [],
            [],
            {"other.png": Picture(PictureType.COVER_BACK, "image/png", 400, 400, 0, b"")},
        )
        result = CheckCoverAvailable(Context()).check(album)
        assert result is not None
        assert "album has pictures but none is COVER_FRONT picture" in result.message

        assert result.fixer is not None
        assert result.fixer.options == ["1.flac#0 (and 2 more) image/png COVER_BACK"]
        assert result.fixer.option_automatic_index == 0

        # same image was found embedded and in other.png - rename other.png instead of creating new cover.png
        mock_rename = mocker.patch("albums.checks.picture.check_cover_available.rename")
        result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_rename.call_args_list == [call(Path(".") / album.path / "other.png", Path(".") / album.path / "cover.png")]
