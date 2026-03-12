import os

import pytest
import xxhash

from albums.database.models import AlbumEntity, TrackEntity, TrackPictureEntity, TrackTagEntity
from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger, BasicTag
from albums.tagger.types import Picture, PictureType

from ..fixtures.create_library import create_library, make_image_data

track = TrackEntity(
    filename="1.ogg",
    tags=[
        TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"),
        TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="1"),
        TrackTagEntity(tag=BasicTag.ARTIST, value="C"),
        TrackTagEntity(tag=BasicTag.TITLE, value="one"),
        TrackTagEntity(tag=BasicTag.ALBUM, value="foobar"),
    ],
    pictures=[
        TrackPictureEntity(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT),
        TrackPictureEntity(picture_info=PictureInfo("image/jpeg", 300, 300, 24, 1, b""), picture_type=PictureType.COVER_BACK),
    ],
)
album = AlbumEntity(path="foobar" + os.sep, tracks=[track])


class TestOggVorbis:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestOggVorbis.library = create_library("tagger_mp3", [album])
        TestOggVorbis.tagger = AlbumTagger(TestOggVorbis.library / album.path)

    def test_read_oggvorbis(self):
        with TestOggVorbis.tagger.open(track.filename) as file:
            scan = file.scan()

        assert scan.pictures[0].type == PictureType.COVER_FRONT
        assert scan.pictures[0].picture_info.mime_type == "image/png"
        assert scan.pictures[0].picture_info.width == scan.pictures[0].picture_info.height == 400

        assert scan.pictures[1].type == PictureType.COVER_BACK
        assert scan.pictures[1].picture_info.mime_type == "image/jpeg"
        assert scan.pictures[1].picture_info.width == scan.pictures[1].picture_info.height == 300

        tags = dict(scan.tags)
        assert tags[BasicTag.ARTIST] == ("C",)
        assert tags[BasicTag.TITLE] == ("one",)
        assert tags[BasicTag.ALBUM] == ("foobar",)
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("1",)

    def test_remove_one_ogg_vorbis_pic(self):
        with TestOggVorbis.tagger.open(track.filename) as file:
            scan = file.scan()

        assert len(scan.pictures) == 2
        assert scan.pictures[0].type == PictureType.COVER_FRONT
        assert scan.pictures[0].picture_info.mime_type == "image/png"
        assert scan.pictures[0].picture_info.width == scan.pictures[0].picture_info.height == 400
        front = scan.pictures[0]
        assert scan.pictures[1].type == PictureType.COVER_BACK
        back = scan.pictures[1]

        with TestOggVorbis.tagger.open(track.filename) as file:
            file.remove_picture(front)

        with TestOggVorbis.tagger.open(track.filename) as file:
            scan = file.scan()

        assert scan.pictures == (back,)

    def test_replace_one_ogg_vorbis_pic(self):
        with TestOggVorbis.tagger.open(track.filename) as file:
            scan = file.scan()

        assert len(scan.pictures) == 2
        assert scan.pictures[0].type == PictureType.COVER_FRONT
        front = scan.pictures[0]
        assert scan.pictures[1].type == PictureType.COVER_BACK
        back = scan.pictures[1]

        image_data = make_image_data(600, 600, "JPEG")
        pic_info = PictureInfo("image/jpeg", 600, 600, 24, len(image_data), xxhash.xxh32_digest(image_data))
        replacement = Picture(pic_info, PictureType.FISH, "")

        with TestOggVorbis.tagger.open(track.filename) as file:
            file.remove_picture(front)
            file.add_picture(replacement, image_data)

        with TestOggVorbis.tagger.open(track.filename) as file:
            scan = file.scan()

        assert set(scan.pictures) == {replacement, back}
