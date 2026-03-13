import os

import pytest
import xxhash

from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger, BasicTag
from albums.tagger.types import Picture, PictureType
from albums.types import Album, Track, TrackPicture

from ..fixtures.create_library import create_library, make_image_data

track = Track(
    filename="1.ogg",
    tag={
        BasicTag.ARTIST: "C",
        BasicTag.TITLE: "one",
        BasicTag.ALBUM: "foobar",
        BasicTag.ALBUMARTIST: "foo",
        BasicTag.TRACKNUMBER: "1",
        BasicTag.TRACKTOTAL: "2",
        BasicTag.DISCNUMBER: "3",
        BasicTag.DISCTOTAL: "4",
        BasicTag.GENRE: "Rock",
    },
    pictures=[
        TrackPicture(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b""), picture_type=PictureType.COVER_FRONT),
        TrackPicture(picture_info=PictureInfo("image/jpeg", 300, 300, 24, 1, b""), picture_type=PictureType.COVER_BACK),
    ],
)
album = Album(path="foobar" + os.sep, tracks=[track])


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
        assert tags[BasicTag.ALBUMARTIST] == ("foo",)
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("2",)
        assert tags[BasicTag.DISCNUMBER] == ("3",)
        assert tags[BasicTag.DISCTOTAL] == ("4",)
        assert tags[BasicTag.GENRE] == ("Rock",)

    def test_update_ogg_vorbis_tags(self):
        TestOggVorbis.tagger.set_basic_tags(
            TestOggVorbis.library / album.path / track.filename,
            [
                (BasicTag.ARTIST, "a1"),
                (BasicTag.TITLE, "t"),
                (BasicTag.ALBUM, "a3"),
                (BasicTag.ALBUMARTIST, "a2"),
                (BasicTag.TRACKNUMBER, "5"),
                (BasicTag.TRACKTOTAL, "6"),
                (BasicTag.DISCNUMBER, "7"),
                (BasicTag.DISCTOTAL, "8"),
                (BasicTag.GENRE, "Country"),
            ],
        )
        with TestOggVorbis.tagger.open(track.filename) as file:
            scan = file.scan()
        tags = dict(scan.tags)
        assert tags[BasicTag.ARTIST] == ("a1",)
        assert tags[BasicTag.TITLE] == ("t",)
        assert tags[BasicTag.ALBUM] == ("a3",)
        assert tags[BasicTag.ALBUMARTIST] == ("a2",)
        assert tags[BasicTag.TRACKNUMBER] == ("5",)
        assert tags[BasicTag.TRACKTOTAL] == ("6",)
        assert tags[BasicTag.DISCNUMBER] == ("7",)
        assert tags[BasicTag.DISCTOTAL] == ("8",)
        assert tags[BasicTag.GENRE] == ("Country",)

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
