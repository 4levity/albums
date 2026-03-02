import io
import os
from pathlib import Path
from unittest.mock import call, mock_open, patch

from PIL import Image

from albums.app import Context
from albums.checks.picture.check_cover_dimensions import CheckCoverDimensions
from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import Picture, PictureType, StreamInfo, TaggerFile
from albums.types import Album, PictureFile, Track

from ...fixtures.create_library import make_image_data


class TestCheckCoverDimensions:
    def test_cover_square_enough(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_FRONT, "", ())],
                )
            ],
        )
        result = CheckCoverDimensions(Context()).check(album)
        assert result is None

    def test_cover_square_enough_not_unique(self):
        pic1 = Picture(PictureInfo("image/png", 401, 400, 24, 1, b"1111"), PictureType.COVER_FRONT, "", ())
        pic2 = Picture(PictureInfo("image/png", 402, 400, 24, 1, b"2222"), PictureType.COVER_FRONT, "", ())
        album = Album(
            "",
            [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), [pic1]), Track("2.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), [pic2])],
        )
        result = CheckCoverDimensions(Context()).check(album)
        assert result is None

    def test_cover_not_square_enough_embedded(self, mocker):
        cover = Picture(PictureInfo("image/jpeg", 800, 1000, 24, 1, b""), PictureType.COVER_FRONT, "", ())
        album = Album("foo" + os.sep, [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), [cover])], [], [], {}, 1)
        ctx = Context()
        ctx.db = True
        result = CheckCoverDimensions(ctx).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (800x1000)"
        assert result.fixer
        assert len(result.fixer.options) == 1
        assert result.fixer.option_automatic_index == 0

        tagger = TaggerFile()
        image_data = make_image_data(cover.file_info.width, cover.file_info.height, "JPEG")
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_get_image_data = mocker.patch.object(tagger, "get_image_data", return_value=image_data)

        mocker.patch("albums.checks.picture.check_cover_dimensions.render_image_table", return_value=[[]])
        mock_update_picture_files = mocker.patch("albums.checks.picture.check_cover_dimensions.update_picture_files")
        m_open = mock_open()
        with patch("builtins.open", m_open):
            assert result.fixer.get_table()
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_get_image_data.call_count == 1
        assert mock_update_picture_files.call_count == 1
        assert mock_update_picture_files.call_args.args[0]
        assert mock_update_picture_files.call_args.args[1] == 1
        picture_files: dict[str, PictureFile] = mock_update_picture_files.call_args.args[2]
        assert "cover.png" in picture_files
        assert picture_files["cover.png"].cover_source
        assert picture_files["cover.png"].picture.type == PictureType.COVER_FRONT
        assert picture_files["cover.png"].picture.file_info.mime_type == "image/png"

        mock_handle = m_open.return_value
        image_data_written = mock_handle.write.call_args[0][0]
        m_open.assert_has_calls([call(Path(".") / album.path / "cover.png", "wb")])
        new_cover = Image.open(io.BytesIO(image_data_written))
        assert new_cover.width == new_cover.height == min(cover.file_info.width, cover.file_info.height)

    def test_cover_not_square_enough_embedded_preserve_type(self, mocker):
        cover = Picture(PictureInfo("image/jpeg", 800, 1000, 24, 1, b""), PictureType.COVER_FRONT, "", ())
        album = Album("foo" + os.sep, [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), [cover])], [], [], {}, 1)
        ctx = Context()
        ctx.db = True
        ctx.config.checks[CheckCoverDimensions.name]["create_mime_type"] = ""
        result = CheckCoverDimensions(ctx).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (800x1000)"
        assert result.fixer
        assert result.fixer.option_automatic_index == 0

        tagger = TaggerFile()
        image_data = make_image_data(cover.file_info.width, cover.file_info.height, "JPEG")
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_get_image_data = mocker.patch.object(tagger, "get_image_data", return_value=image_data)

        mocker.patch("albums.checks.picture.check_cover_dimensions.render_image_table", return_value=[[]])
        mock_update_picture_files = mocker.patch("albums.checks.picture.check_cover_dimensions.update_picture_files")
        m_open = mock_open()
        with patch("builtins.open", m_open):
            assert result.fixer.get_table()
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_get_image_data.call_count == 1
        assert mock_update_picture_files.call_count == 1
        assert mock_update_picture_files.call_args.args[0]
        assert mock_update_picture_files.call_args.args[1] == 1
        picture_files: dict[str, PictureFile] = mock_update_picture_files.call_args.args[2]
        assert "cover.jpg" in picture_files
        assert picture_files["cover.jpg"].cover_source
        assert picture_files["cover.jpg"].picture.type == PictureType.COVER_FRONT
        assert picture_files["cover.jpg"].picture.file_info.mime_type == "image/jpeg"

        mock_handle = m_open.return_value
        image_data_written = mock_handle.write.call_args[0][0]
        m_open.assert_has_calls([call(Path(".") / album.path / "cover.jpg", "wb")])
        new_cover = Image.open(io.BytesIO(image_data_written))
        assert new_cover.format == "JPEG"
        assert new_cover.width == new_cover.height == min(cover.file_info.width, cover.file_info.height)

    def test_cover_not_square_enough_jpg_file(self, mocker):
        cover = Picture(PictureInfo("image/jpeg", 1000, 800, 24, 1, b""), PictureType.COVER_FRONT, "", ())
        album = Album(
            "foo" + os.sep, [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"))], [], [], {"folder.jpg": PictureFile(cover, 999, True)}, 1
        )
        ctx = Context()
        ctx.db = True
        result = CheckCoverDimensions(ctx).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (1000x800)"
        assert result.fixer
        assert len(result.fixer.options) == 1
        assert result.fixer.option_automatic_index == 0
        image_data = make_image_data(cover.file_info.width, cover.file_info.height, "JPEG")
        mock_read_binary_file = mocker.patch("albums.checks.picture.check_cover_dimensions.read_binary_file", return_value=image_data)
        mock_unlink = mocker.patch("albums.checks.picture.check_cover_dimensions.unlink")
        mock_update_picture_files = mocker.patch("albums.checks.picture.check_cover_dimensions.update_picture_files")
        m_open = mock_open()

        with patch("builtins.open", m_open):
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_read_binary_file.call_count == 1
        assert mock_unlink.call_args_list == [call(Path(album.path) / "folder.jpg")]
        assert mock_update_picture_files.call_count == 1
        assert mock_update_picture_files.call_args.args[0]
        assert mock_update_picture_files.call_args.args[1] == 1
        picture_files: dict[str, PictureFile] = mock_update_picture_files.call_args.args[2]
        assert "folder.png" in picture_files
        assert picture_files["folder.png"].cover_source
        assert picture_files["folder.png"].picture.type == PictureType.COVER_FRONT
        assert picture_files["folder.png"].picture.file_info.mime_type == "image/png"

        mock_handle = m_open.return_value
        image_data_written = mock_handle.write.call_args[0][0]
        m_open.assert_has_calls([call(Path(".") / album.path / "folder.png", "wb")])
        new_cover = Image.open(io.BytesIO(image_data_written))
        assert new_cover.width == new_cover.height == min(cover.file_info.width, cover.file_info.height)

    def test_cover_not_square_enough_png_file(self, mocker):
        cover = Picture(PictureInfo("image/png", 1000, 800, 24, 1, b""), PictureType.COVER_FRONT, "", ())
        album = Album(
            "foo" + os.sep, [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"))], [], [], {"folder.png": PictureFile(cover, 999, True)}, 1
        )
        ctx = Context()
        ctx.db = True
        result = CheckCoverDimensions(ctx).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (1000x800)"
        assert result.fixer
        assert len(result.fixer.options) == 1
        assert result.fixer.option_automatic_index == 0
        image_data = make_image_data(cover.file_info.width, cover.file_info.height, "PNG")
        mock_read_binary_file = mocker.patch("albums.checks.picture.check_cover_dimensions.read_binary_file", return_value=image_data)
        mock_update_picture_files = mocker.patch("albums.checks.picture.check_cover_dimensions.update_picture_files")
        m_open = mock_open()

        with patch("builtins.open", m_open):
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_read_binary_file.call_count == 1
        assert mock_update_picture_files.call_count == 1
        assert mock_update_picture_files.call_args.args[0]
        assert mock_update_picture_files.call_args.args[1] == 1
        picture_files: dict[str, PictureFile] = mock_update_picture_files.call_args.args[2]
        assert "folder.png" in picture_files
        assert picture_files["folder.png"].cover_source
        assert picture_files["folder.png"].picture.type == PictureType.COVER_FRONT
        assert picture_files["folder.png"].picture.file_info.mime_type == "image/png"

        mock_handle = m_open.return_value
        image_data_written = mock_handle.write.call_args[0][0]
        m_open.assert_has_calls([call(Path(".") / album.path / "folder.png", "wb")])
        new_cover = Image.open(io.BytesIO(image_data_written))
        assert new_cover.width == new_cover.height == min(cover.file_info.width, cover.file_info.height)

    def test_cover_not_square_enough_extreme(self, mocker):
        cover = Picture(PictureInfo("image/png", 1000, 500, 24, 1, b""), PictureType.COVER_FRONT, "", ())
        album = Album("foo" + os.sep, [Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), [cover])])
        result = CheckCoverDimensions(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (1000x500)"
        assert result.fixer is None  # too unsquare to fix

    def test_cover_dimensions_too_small(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [Picture(PictureInfo("image/png", 10, 10, 24, 1, b""), PictureType.COVER_FRONT, "", ())],
                )
            ],
        )
        result = CheckCoverDimensions(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT image is too small (10x10)"

    def test_cover_dimensions_too_large(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [Picture(PictureInfo("image/png", 9001, 9001, 24, 1, b""), PictureType.COVER_FRONT, "", ())],
                )
            ],
        )
        result = CheckCoverDimensions(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT image is too large (9001x9001)"
