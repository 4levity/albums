import os

import pytest
from mutagen.mp3 import MP3

from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger, BasicTag
from albums.tagger.types import Picture, PictureType
from albums.types import Album, Track

from ..fixtures.create_library import create_library

mp3track = Track(
    "1.mp3",
    {BasicTag.TITLE: ["T"], BasicTag.TRACKNUMBER: ["1"], BasicTag.TRACKTOTAL: ["3"]},
    0,
    0,
    None,
    [Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_FRONT, "", ())],
)
mp3album = Album("baz" + os.sep, [mp3track])


class TestAlbumTagger:
    @pytest.fixture(scope="function", autouse=True)
    def setup_cli_tests(self):
        TestAlbumTagger.library = create_library("album_tagger", [mp3album])

    def test_contextmanager_save(self, mocker):
        tagger = AlbumTagger(TestAlbumTagger.library / mp3album.path)
        mock_mp3_save = mocker.spy(MP3, "save")

        with tagger.open(mp3track.filename) as file:
            scan = file.scan()
            assert dict(scan.tags)[BasicTag.TRACKNUMBER] == ("1",)
        assert mock_mp3_save.call_count == 0

        with tagger.open(mp3track.filename) as file:
            assert len(scan.pictures) == 1
            file.get_image_data(scan.pictures[0])
        assert mock_mp3_save.call_count == 0

        with tagger.open(mp3track.filename) as file:
            file.set_tag(BasicTag.ALBUM, "baz")
        assert mock_mp3_save.call_count == 1

        with tagger.open(mp3track.filename) as file:
            assert dict(file.scan().tags)[BasicTag.ALBUM] == ("baz",)
            (picture, image_data) = next(file.get_pictures())
            file.remove_picture(picture)
        assert mock_mp3_save.call_count == 2

        with tagger.open(mp3track.filename) as file:
            assert len(file.scan().pictures) == 0
            file.add_picture(picture, image_data)
        assert mock_mp3_save.call_count == 3
