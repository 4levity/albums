import os

import pytest
from mutagen.mp3 import MP3

from albums.entities import Album, Track, TrackPicture
from albums.picture import PictureInfo
from albums.tagger import AlbumTagger, BasicField, PictureType

from ..fixtures.create_library import create_library

mp3track = Track(
    filename="1.mp3",
    tag={BasicField.TITLE: "T", BasicField.TRACKNUMBER: "1", BasicField.TRACKTOTAL: "3"},
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
            pictures = [pic for (pic, _) in file.get_pictures()]
            tags = dict(file.get_fields())
            assert tags[BasicField.TRACKNUMBER] == ("1",)
        assert mock_mp3_save.call_count == 0

        with tagger.open(mp3track.filename) as file:
            assert len(pictures) == 1
            file.get_image_data(pictures[0])
        assert mock_mp3_save.call_count == 0

        with tagger.open(mp3track.filename) as file:
            file.set_field(BasicField.ALBUM, "baz")
        assert mock_mp3_save.call_count == 1

        with tagger.open(mp3track.filename) as file:
            assert dict(file.get_fields())[BasicField.ALBUM] == ("baz",)
            (picture, image_data) = next(file.get_pictures())
            file.remove_picture(picture)
        assert mock_mp3_save.call_count == 2

        with tagger.open(mp3track.filename) as file:
            assert len(list(file.get_pictures())) == 0
            file.add_picture(picture, image_data)
        assert mock_mp3_save.call_count == 3
