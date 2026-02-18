import io
import os
from pathlib import Path
from unittest.mock import call, mock_open, patch

from PIL import Image

from albums.app import Context
from albums.checks.check_front_cover_dimensions import CheckFrontCoverDimensions
from albums.types import Album, Picture, PictureType, Stream, Track


class TestCheckFrontCoverDimensions:
    def test_cover_square_enough(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 401, 400, 0, b"")])])
        result = CheckFrontCoverDimensions(Context()).check(album)
        assert result is None

    def test_cover_not_square_enough_embedded(self, mocker):
        cover = Picture(PictureType.COVER_FRONT, "image/jpeg", 800, 1000, 0, b"")
        album = Album("foo" + os.sep, [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [cover])], [], [], {}, 1)
        ctx = Context()
        ctx.db = True
        result = CheckFrontCoverDimensions(ctx).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (800x1000)"
        assert result.fixer
        assert len(result.fixer.options) == 1
        assert result.fixer.option_automatic_index == 0
        read_image_value = (Image.new("RGB", (cover.width, cover.height), color="blue"), b"")
        mock_read_image = mocker.patch("albums.checks.check_front_cover_dimensions.read_image", return_value=read_image_value)
        mocker.patch("albums.checks.check_front_cover_dimensions.render_image_table", return_value=[[]])
        mock_update_picture_files = mocker.patch("albums.checks.check_front_cover_dimensions.update_picture_files")
        m_open = mock_open()
        with patch("builtins.open", m_open):
            assert result.fixer.get_table()
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_read_image.call_count == 1
        assert mock_update_picture_files.call_count == 1
        assert mock_update_picture_files.call_args.args == (True, 1, {"cover.png": Picture(PictureType.COVER_FRONT, "image/png", 0, 0, 0, b"")})
        mock_handle = m_open.return_value
        image_data_written = mock_handle.write.call_args[0][0]
        m_open.assert_has_calls([call(Path(".") / album.path / "cover.png", "wb")])
        new_cover = Image.open(io.BytesIO(image_data_written))
        assert new_cover.width == new_cover.height == min(cover.width, cover.height)

    def test_cover_not_square_enough_jpg_file(self, mocker):
        cover = Picture(PictureType.COVER_FRONT, "image/jpeg", 1000, 800, 0, b"", "", None, 999, 0, True)
        album = Album("foo" + os.sep, [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))], [], [], {"folder.jpg": cover}, 1)
        ctx = Context()
        ctx.db = True
        result = CheckFrontCoverDimensions(ctx).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (1000x800)"
        assert result.fixer
        assert len(result.fixer.options) == 1
        assert result.fixer.option_automatic_index == 0
        read_image_value = (Image.new("RGB", (cover.width, cover.height), color="blue"), b"")
        mock_read_image = mocker.patch("albums.checks.check_front_cover_dimensions.read_image", return_value=read_image_value)
        mock_unlink = mocker.patch("albums.checks.check_front_cover_dimensions.unlink")
        mock_update_picture_files = mocker.patch("albums.checks.check_front_cover_dimensions.update_picture_files")
        m_open = mock_open()
        with patch("builtins.open", m_open):
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_read_image.call_count == 1
        assert mock_unlink.call_args_list == [call(Path(album.path) / "folder.jpg")]
        assert mock_update_picture_files.call_count == 1
        assert mock_update_picture_files.call_args.args == (True, 1, {"folder.png": Picture(PictureType.COVER_FRONT, "image/png", 0, 0, 0, b"")})
        mock_handle = m_open.return_value
        image_data_written = mock_handle.write.call_args[0][0]
        m_open.assert_has_calls([call(Path(".") / album.path / "folder.png", "wb")])
        new_cover = Image.open(io.BytesIO(image_data_written))
        assert new_cover.width == new_cover.height == min(cover.width, cover.height)

    def test_cover_not_square_enough_png_file(self, mocker):
        cover = Picture(PictureType.COVER_FRONT, "image/png", 1000, 800, 0, b"", "", None, 999, 0, True)
        album = Album("foo" + os.sep, [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"))], [], [], {"folder.png": cover}, 1)
        ctx = Context()
        ctx.db = True
        result = CheckFrontCoverDimensions(ctx).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (1000x800)"
        assert result.fixer
        assert len(result.fixer.options) == 1
        assert result.fixer.option_automatic_index == 0
        read_image_value = (Image.new("RGB", (cover.width, cover.height), color="blue"), b"")
        mocker.patch("albums.checks.check_front_cover_dimensions.read_image", return_value=read_image_value)
        mock_update_picture_files = mocker.patch("albums.checks.check_front_cover_dimensions.update_picture_files")
        m_open = mock_open()
        with patch("builtins.open", m_open):
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_update_picture_files.call_count == 1
        assert mock_update_picture_files.call_args.args == (True, 1, {"folder.png": Picture(PictureType.COVER_FRONT, "image/png", 0, 0, 0, b"")})
        mock_handle = m_open.return_value
        image_data_written = mock_handle.write.call_args[0][0]
        m_open.assert_has_calls([call(Path(".") / album.path / "folder.png", "wb")])
        new_cover = Image.open(io.BytesIO(image_data_written))
        assert new_cover.width == new_cover.height == min(cover.width, cover.height)

    def test_cover_not_square_enough_extreme(self, mocker):
        cover = Picture(PictureType.COVER_FRONT, "image/jpeg", 1000, 500, 0, b"")
        album = Album("foo" + os.sep, [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [cover])])
        result = CheckFrontCoverDimensions(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (1000x500)"
        assert result.fixer is None  # too unsquare to fix

    def test_cover_dimensions_too_small(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 10, 10, 0, b"")])])
        result = CheckFrontCoverDimensions(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT image is too small (10x10)"

    def test_cover_dimensions_too_large(self):
        album = Album("", [Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 9001, 9001, 0, b"")])])
        result = CheckFrontCoverDimensions(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT image is too large (9001x9001)"
