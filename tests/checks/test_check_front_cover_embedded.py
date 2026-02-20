import os
from pathlib import Path
from unittest.mock import call, mock_open, patch

from PIL import Image

from albums.app import Context
from albums.checks.check_front_cover_embedded import CheckFrontCoverEmbedded
from albums.types import Album, Picture, PictureType, Stream, Track


class TestCheckFrontCoverEmbedded:
    def test_cover_embedded_ok(self):
        album = Album(
            "",
            [
                Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")]),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")]),
            ],
        )
        result = CheckFrontCoverEmbedded(Context()).check(album)
        assert result is None

    def test_cover_embedded_some(self, mocker):
        album = Album(
            "",
            [
                Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")]),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC")),
            ],
        )
        album.album_id = 1
        ctx = Context()
        ctx.db = True
        result = CheckFrontCoverEmbedded(ctx).check(album)
        assert result is not None
        assert "the cover can be extracted and marked as front_cover_source" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Extract embedded cover and mark as front cover source"]
        assert result.fixer.option_automatic_index == 0
        read_image_value = (Image.new("RGB", (400, 400), color="blue"), b"file contents")
        mock_read_image = mocker.patch("albums.checks.check_front_cover_embedded.read_image", return_value=read_image_value)
        mock_update_picture_files = mocker.patch("albums.checks.check_front_cover_embedded.update_picture_files")
        m_open = mock_open()
        with patch("builtins.open", m_open):
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_read_image.call_count == 1
        assert mock_update_picture_files.call_count == 1
        assert mock_update_picture_files.call_args.args == (True, 1, {"cover.png": Picture(PictureType.COVER_FRONT, "image/png", 0, 0, 0, b"")})
        m_open.assert_has_calls([call(Path(".") / album.path / "cover.png", "wb")])

        mock_handle = m_open.return_value
        image_data_written = mock_handle.write.call_args[0][0]
        assert image_data_written == b"file contents"

    def test_cover_embedded_some_with_source(self, mocker):
        album = Album(
            "foo" + os.sep,
            [
                Track("1.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC"), [Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"")]),
                Track("2.flac", {}, 0, 0, Stream(1.5, 0, 0, "FLAC")),
            ],
            [],
            [],
            {"cover.png": Picture(PictureType.COVER_FRONT, "image/png", 400, 400, 0, b"", "", None, 999, 0, True)},
        )
        album.album_id = 1
        ctx = Context()
        ctx.db = True
        result = CheckFrontCoverEmbedded(ctx).check(album)
        assert result is not None
        assert "can re-embed from front cover source" in result.message
        assert result.fixer
        assert result.fixer.options == [">> Embed new cover art in all tracks"]
        assert result.fixer.option_automatic_index == 0

        read_image_value = (Image.new("RGB", (400, 400), color="blue"), b"file contents")
        mock_read_image = mocker.patch("albums.checks.check_front_cover_embedded.read_image", return_value=read_image_value)
        mock_replace_embedded_image = mocker.patch("albums.checks.check_front_cover_embedded.replace_embedded_image")
        mock_add_embedded_image = mocker.patch("albums.checks.check_front_cover_embedded.add_embedded_image")
        mock_render_image_table = mocker.patch("albums.checks.check_front_cover_embedded.render_image_table", return_value=[])

        table = result.fixer.get_table()
        assert mock_read_image.call_count == 1
        assert mock_render_image_table.call_count == 1
        assert table == (["Front Cover Source cover.png", "Current Embedded Cover", "Preview New Embedded Cover"], [])

        result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])

        assert mock_read_image.call_count == 2
        assert mock_replace_embedded_image.call_count == 1
        assert mock_replace_embedded_image.call_args_list[0][0][0] == Path("foo") / album.tracks[0].filename
        assert mock_replace_embedded_image.call_args_list[0][0][1] == "FLAC"
        assert mock_replace_embedded_image.call_args_list[0][0][2] == album.tracks[0].pictures[0]

        assert mock_add_embedded_image.call_count == 1
        assert mock_add_embedded_image.call_args_list[0][0][0] == Path("foo") / album.tracks[1].filename
        assert mock_add_embedded_image.call_args_list[0][0][1] == "FLAC"
        pic: Picture = mock_add_embedded_image.call_args_list[0][0][2]
        assert pic.picture_type == PictureType.COVER_FRONT
        assert pic.format == "image/jpeg"
        assert pic.width == pic.height == 400
