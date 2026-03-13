import os

import pytest
from mutagen.mp3 import MP3

from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger, BasicTag
from albums.tagger.types import PictureType
from albums.types import Album, Tag, Track, TrackPicture

from ..fixtures.create_library import create_library

mp3track = Track(
    filename="1.mp3",
    tags=[
        Tag(tag=BasicTag.TITLE, value="T"),
        Tag(tag=BasicTag.TRACKNUMBER, value="1"),
        Tag(tag=BasicTag.TRACKTOTAL, value="3"),
    ],
    pictures=[TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT)],
)
mp3album = Album(path="baz" + os.sep, tracks=[mp3track])


class TestAlbumTagger:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
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
