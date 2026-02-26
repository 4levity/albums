import io
import os
from pathlib import Path
from unittest.mock import call, mock_open, patch

from PIL import Image

from albums.app import Context
from albums.checks.picture.check_cover_embedded import CheckCoverEmbedded
from albums.tagger.provider import AlbumTagger
from albums.tagger.types import AlbumPicture, PictureInfo, PictureType, StreamInfo, TaggerFile
from albums.types import Album, Picture, Track

from ...fixtures.create_library import make_image_data


class TestCheckCoverEmbedded:
    def test_cover_embedded_ok(self):
        album = Album(
            "",
            [
                Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")]),
                Track("2.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")]),
            ],
        )
        result = CheckCoverEmbedded(Context()).check(album)
        assert result is None

    def test_cover_embedded_some(self, mocker):
        album = Album(
            "",
            [
                Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")]),
                Track("2.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC")),
            ],
        )
        album.album_id = 1
        ctx = Context()
        ctx.db = True
        result = CheckCoverEmbedded(ctx).check(album)
        assert result is not None
        assert "the cover can be extracted and marked as cover_source" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Extract embedded cover and mark as front cover source"]
        assert result.fixer.option_automatic_index == 0
        tagger = TaggerFile()
        image_data = make_image_data(400, 400, "PNG")
        mock_read_image = mocker.patch.object(tagger, "get_image_data", return_value=image_data)
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_update_picture_files = mocker.patch("albums.checks.picture.check_cover_embedded.update_picture_files")
        m_open = mock_open()
        with patch("builtins.open", m_open):
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_read_image.call_count == 1
        assert mock_update_picture_files.call_count == 1
        assert mock_update_picture_files.call_args.args == (True, 1, {"cover.png": Picture(PictureType.COVER_FRONT, "image/png", 0, 0, 0, b"")})
        m_open.assert_has_calls([call(Path(".") / album.path / "cover.png", "wb")])

        mock_handle = m_open.return_value
        image_data_written = mock_handle.write.call_args[0][0]
        assert image_data_written == image_data

    def test_cover_embedded_some_with_source(self, mocker):
        album = Album(
            "foo" + os.sep,
            [
                Track("1.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")]),
                Track("2.flac", {}, 0, 0, StreamInfo(1.5, 0, 0, "FLAC")),
            ],
            [],
            [],
            {"cover.png": Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"", "", None, 999, 0, True)},
        )
        album.album_id = 1
        ctx = Context()
        ctx.db = True
        result = CheckCoverEmbedded(ctx).check(album)
        assert result is not None
        assert "can re-embed from front cover source" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Embed new cover art in all tracks"]
        assert result.fixer.option_automatic_index == 0

        tagger = TaggerFile()
        image_data = make_image_data(400, 400, "PNG")
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_render_image_table = mocker.patch("albums.checks.picture.check_cover_embedded.render_image_table", return_value=[])
        mock_read_binary_file = mocker.patch("albums.checks.picture.check_cover_embedded.read_binary_file", return_value=image_data)
        mock_add_picture = mocker.patch.object(tagger, "add_picture")
        mock_remove_picture = mocker.patch.object(tagger, "remove_picture")

        mock_get_pictures = mocker.patch.object(tagger, "get_pictures")
        pic_found = [(AlbumPicture(PictureInfo("", 0, 0, 0, 0, b""), PictureType.COVER_FRONT, "", ()), b"")]
        mock_get_pictures.side_effect = [pic_found, []]

        table = result.fixer.get_table()
        assert mock_read_binary_file.call_count == 1
        assert mock_render_image_table.call_count == 1
        assert table == (["Front Cover Source cover.png", "Current Embedded Cover", "Preview New Embedded Cover"], [])

        result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_read_binary_file.call_count == 2
        assert mock_get_pictures.call_count == 2
        assert mock_add_picture.call_count == 2
        assert mock_add_picture.call_args_list[0][0][0].picture_type == PictureType.COVER_FRONT
        data0 = mock_add_picture.call_args_list[0][0][1]
        assert mock_add_picture.call_args_list[1][0][0].picture_type == PictureType.COVER_FRONT
        data1 = mock_add_picture.call_args_list[1][0][1]
        assert isinstance(data0, bytes)
        assert data0 == data1
        assert data0 != image_data
        image = Image.open(io.BytesIO(data0))
        assert image.format == "JPEG"

        assert mock_remove_picture.call_count == 1
        assert mock_remove_picture.call_args_list[0][0][0].picture_type == PictureType.COVER_FRONT

        # assert mock_replace_embedded_image.call_count == 1
        # assert mock_replace_embedded_image.call_args_list[0][0][0] == Path("foo") / album.tracks[0].filename
        # assert mock_replace_embedded_image.call_args_list[0][0][1] == "FLAC"
        # assert mock_replace_embedded_image.call_args_list[0][0][2] == album.tracks[0].pictures[0]

        # assert mock_add_embedded_image.call_count == 1
        # assert mock_add_embedded_image.call_args_list[0][0][0] == Path("foo") / album.tracks[1].filename
        # assert mock_add_embedded_image.call_args_list[0][0][1] == "FLAC"
        # pic: Picture = mock_add_embedded_image.call_args_list[0][0][2]
        # assert pic.picture_type == PictureType.COVER_FRONT
        # assert pic.format == "image/jpeg"
        # assert pic.width == pic.height == 400
