from pathlib import Path
from unittest.mock import call, mock_open, patch

from albums.app import Context
from albums.checks.picture.check_album_art import CheckAlbumArt
from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger
from albums.tagger.types import Picture, PictureType, StreamInfo, TaggerFile
from albums.types import Album, Track

from ...fixtures.create_library import make_image_data


class TestCheckAlbumArt:
    def test_album_art_ok(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [Picture(PictureInfo("image/jpeg", 400, 400, 24, 1024, b""), PictureType.COVER_FRONT, "")],
                )
            ],
        )
        result = CheckAlbumArt(Context()).check(album)
        assert result is None

    def test_album_art_format(self, mocker):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [Picture(PictureInfo("image/gif", 400, 400, 8, 1024, b""), PictureType.COVER_FRONT, "")],
                )
            ],
        )
        result = CheckAlbumArt(Context()).check(album)
        assert result is not None
        assert result.message == "embedded images (1) not in recommended format (image/gif)"
        assert result.fixer
        assert result.fixer.options == [">> Extract images to files and remove embedded"]
        assert result.fixer.option_automatic_index == 0

        tagger = TaggerFile()
        image_data = make_image_data(400, 400, "GIF")
        mock_tagger_open = mocker.patch.object(AlbumTagger, "open")
        mock_tagger_open.return_value.__enter__.return_value = tagger
        mock_get_image_data = mocker.patch.object(tagger, "get_image_data", return_value=image_data)

        m_open = mock_open()
        with patch("builtins.open", m_open):
            assert result.fixer.get_table()
            assert mock_get_image_data.call_count == 1
            result.fixer.fix(result.fixer.options[result.fixer.option_automatic_index])
        assert mock_get_image_data.call_count == 2
        mock_handle = m_open.return_value
        image_data_written = mock_handle.write.call_args[0][0]
        m_open.assert_has_calls([call(Path(".") / album.path / "cover.gif", "wb")])
        assert image_data_written == image_data

    def test_album_art_file_too_large(self):
        album = Album(
            "",
            [
                Track(
                    "1.flac",
                    {},
                    0,
                    0,
                    StreamInfo(1.5, 0, 0, "FLAC"),
                    [Picture(PictureInfo("image/jpeg", 400, 400, 24, 15 * 1024 * 1024, b""), PictureType.COVER_FRONT, "")],
                )
            ],
        )
        result = CheckAlbumArt(Context()).check(album)
        assert result is not None
        assert result.message == "embedded images (1) over the size limit (largest 15.0 MiB > 4.0 MiB)"
