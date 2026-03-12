import io
import os
from pathlib import Path
from unittest.mock import call, mock_open, patch

from PIL import Image

from albums.app import Context
from albums.checks.picture.check_cover_dimensions import CheckCoverDimensions
from albums.database.models import AlbumEntity, PictureFileEntity, TrackEntity, TrackPictureEntity
from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import Picture, PictureType, TaggerFile

from ...fixtures.create_library import make_image_data


class TestCheckCoverDimensions:
    def test_cover_square_enough(self):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1.flac",
                    pictures=[TrackPictureEntity(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT)],
                )
            ],
        )
        result = CheckCoverDimensions(Context()).check(album)
        assert result is None

    def test_cover_square_enough_not_unique(self):
        pic1 = TrackPictureEntity(picture_info=PictureInfo("image/png", 401, 400, 24, 1, b"1111"), picture_type=PictureType.COVER_FRONT)
        pic2 = TrackPictureEntity(picture_info=PictureInfo("image/png", 402, 400, 24, 1, b"2222"), picture_type=PictureType.COVER_FRONT)
        album = AlbumEntity(
            path="",
            tracks=[TrackEntity(filename="1.flac", pictures=[pic1]), TrackEntity(filename="2.flac", pictures=[pic2])],
        )
        result = CheckCoverDimensions(Context()).check(album)
        assert result is None

    def test_cover_not_square_enough_embedded(self, mocker):
        cover = TrackPictureEntity(picture_info=PictureInfo("image/jpeg", 800, 1000, 24, 1, b""), picture_type=PictureType.COVER_FRONT)
        album = AlbumEntity(path="foo" + os.sep, tracks=[TrackEntity(filename="1.flac", pictures=[cover])])
        ctx = Context()
        ctx.db = True
        result = CheckCoverDimensions(ctx).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (800x1000)"
        assert result.fixer
        assert len(result.fixer.options) == 1
        assert result.fixer.option_automatic_index == 0

        tagger = TaggerFile()
        image_data = make_image_data(cover.picture_info.width, cover.picture_info.height, "JPEG")
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_get_image_data = mocker.patch.object(tagger, "get_image_data", return_value=image_data)

        mocker.patch("albums.checks.picture.check_cover_dimensions.render_image_table", return_value=[[]])
        m_open = mock_open()
        with patch("builtins.open", m_open):
            assert result.fixer.get_table()
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_get_image_data.call_count == 1
        cover = album.picture_files[0]
        assert cover.filename == "cover.png"
        assert cover.cover_source
        assert cover.picture_info.mime_type == "image/png"

        mock_handle = m_open.return_value
        image_data_written = mock_handle.write.call_args[0][0]
        m_open.assert_has_calls([call(Path(".") / album.path / "cover.png", "wb")])
        new_cover = Image.open(io.BytesIO(image_data_written))
        assert new_cover.width == new_cover.height == min(cover.picture_info.width, cover.picture_info.height)

    def test_cover_not_square_enough_embedded_preserve_type(self, mocker):
        cover = TrackPictureEntity(picture_info=PictureInfo("image/jpeg", 800, 1000, 24, 1, b""), picture_type=PictureType.COVER_FRONT)
        album = AlbumEntity(path="foo" + os.sep, tracks=[TrackEntity(filename="1.flac", pictures=[cover])])
        ctx = Context()
        ctx.db = True
        ctx.config.checks[CheckCoverDimensions.name]["create_mime_type"] = ""
        result = CheckCoverDimensions(ctx).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (800x1000)"
        assert result.fixer
        assert result.fixer.option_automatic_index == 0

        tagger = TaggerFile()
        image_data = make_image_data(cover.picture_info.width, cover.picture_info.height, "JPEG")
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_get_image_data = mocker.patch.object(tagger, "get_image_data", return_value=image_data)

        mocker.patch("albums.checks.picture.check_cover_dimensions.render_image_table", return_value=[[]])
        m_open = mock_open()
        with patch("builtins.open", m_open):
            assert result.fixer.get_table()
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_get_image_data.call_count == 1
        cover = album.picture_files[0]
        assert cover.filename == "cover.jpg"
        assert cover.cover_source
        assert cover.picture_info.mime_type == "image/jpeg"

        mock_handle = m_open.return_value
        image_data_written = mock_handle.write.call_args[0][0]
        m_open.assert_has_calls([call(Path(".") / album.path / "cover.jpg", "wb")])
        new_cover = Image.open(io.BytesIO(image_data_written))
        assert new_cover.format == "JPEG"
        assert new_cover.width == new_cover.height == min(cover.picture_info.width, cover.picture_info.height)

    def test_cover_not_square_enough_jpg_file(self, mocker):
        picture_info = PictureInfo("image/jpeg", 1000, 800, 24, 1, b"")
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[TrackEntity(filename="1.flac")],
            picture_files=[PictureFileEntity(filename="folder.jpg", picture_info=picture_info, cover_source=True)],
        )
        ctx = Context()
        ctx.db = True
        result = CheckCoverDimensions(ctx).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (1000x800)"
        assert result.fixer
        assert len(result.fixer.options) == 1
        assert result.fixer.option_automatic_index == 0
        image_data = make_image_data(picture_info.width, picture_info.height, "JPEG")
        tagger = TaggerFile()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_get_image_data = mocker.patch.object(tagger, "get_image_data", return_value=image_data)
        mock_unlink = mocker.patch("albums.checks.picture.check_cover_dimensions.unlink")
        m_open = mock_open()

        with patch("builtins.open", m_open):
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_get_image_data.call_count == 1
        assert mock_unlink.call_args_list == [call(Path(album.path) / "folder.jpg")]
        assert len(album.picture_files) == 1
        assert album.picture_files[0].filename == "folder.png"
        assert album.picture_files[0].cover_source
        assert album.picture_files[0].picture_info.mime_type == "image/png"

        mock_handle = m_open.return_value
        image_data_written = mock_handle.write.call_args[0][0]
        m_open.assert_has_calls([call(Path(".") / album.path / "folder.png", "wb")])
        new_cover = Image.open(io.BytesIO(image_data_written))
        assert new_cover.width == new_cover.height == min(picture_info.width, picture_info.height)

    def test_cover_not_square_enough_png_file(self, mocker):
        cover_info = PictureInfo("image/png", 1000, 800, 24, 1, b"")
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[TrackEntity(filename="1.flac")],
            picture_files=[PictureFileEntity(filename="folder.png", picture_info=cover_info, cover_source=True)],
        )
        ctx = Context()
        ctx.db = True
        result = CheckCoverDimensions(ctx).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (1000x800)"
        assert result.fixer
        assert len(result.fixer.options) == 1
        assert result.fixer.option_automatic_index == 0
        image_data = make_image_data(cover_info.width, cover_info.height, "PNG")
        tagger = TaggerFile()
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_get_image_data = mocker.patch.object(tagger, "get_image_data", return_value=image_data)
        m_open = mock_open()

        with patch("builtins.open", m_open):
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_get_image_data.call_count == 1
        assert len(album.picture_files) == 1
        assert album.picture_files[0].filename == "folder.png"
        assert album.picture_files[0].cover_source
        assert album.picture_files[0].picture_info.mime_type == "image/png"

        mock_handle = m_open.return_value
        image_data_written = mock_handle.write.call_args[0][0]
        m_open.assert_has_calls([call(Path(".") / album.path / "folder.png", "wb")])
        new_cover = Image.open(io.BytesIO(image_data_written))
        assert new_cover.width == new_cover.height == min(cover_info.width, cover_info.height)

    def test_cover_not_square_enough_extreme(self, mocker):
        album = AlbumEntity(
            path="foo" + os.sep,
            tracks=[
                TrackEntity(
                    filename="1.flac",
                    pictures=[TrackPictureEntity(picture_info=PictureInfo("image/png", 1000, 500, 24, 1, b""), picture_type=PictureType.COVER_FRONT)],
                )
            ],
        )
        result = CheckCoverDimensions(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT is not square (1000x500)"
        assert result.fixer is None  # too unsquare to fix

    def test_cover_dimensions_too_small(self):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1.flac",
                    pictures=[TrackPictureEntity(picture_info=PictureInfo("image/png", 10, 10, 24, 1, b""), picture_type=PictureType.COVER_FRONT)],
                )
            ],
        )
        result = CheckCoverDimensions(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT image is too small (10x10)"

    def test_cover_dimensions_too_large(self):
        album = AlbumEntity(
            path="",
            tracks=[
                TrackEntity(
                    filename="1.flac",
                    pictures=[
                        TrackPictureEntity(picture_info=PictureInfo("image/png", 9001, 9001, 24, 1, b""), picture_type=PictureType.COVER_FRONT)
                    ],
                )
            ],
        )
        result = CheckCoverDimensions(Context()).check(album)
        assert result is not None
        assert result.message == "COVER_FRONT image is too large (9001x9001)"
