import os

import pytest
import xxhash

from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger, BasicTag
from albums.tagger.types import Picture, PictureType
from albums.types import Album, Track

from ..fixtures.create_library import create_library, make_image_data

track = Track(
    "1.ogg",
    {"tracknumber": ["1"], "tracktotal": ["1"], "artist": ["C"], "title": ["one"], "album": ["foobar"]},
    0,
    0,
    None,
    [
        Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_FRONT, "", ()),
        Picture(PictureInfo("image/jpeg", 300, 300, 24, 1, b""), PictureType.COVER_BACK, "", ()),
    ],
)
album = Album("foobar" + os.sep, [track])


class TestOggVorbis:
    @pytest.fixture(scope="function", autouse=True)
    def setup_cli_tests(self):
        TestOggVorbis.library = create_library("tagger_mp3", [album])
        TestOggVorbis.tagger = AlbumTagger(TestOggVorbis.library / album.path)

    def test_read_oggvorbis(self):
        with TestOggVorbis.tagger.open(track.filename) as file:
            scan = file.scan()

        assert scan.pictures[0].type == PictureType.COVER_FRONT
        assert scan.pictures[0].file_info.mime_type == "image/png"
        assert scan.pictures[0].file_info.width == scan.pictures[0].file_info.height == 400

        assert scan.pictures[1].type == PictureType.COVER_BACK
        assert scan.pictures[1].file_info.mime_type == "image/jpeg"
        assert scan.pictures[1].file_info.width == scan.pictures[1].file_info.height == 300

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
        assert scan.pictures[0].file_info.mime_type == "image/png"
        assert scan.pictures[0].file_info.width == scan.pictures[0].file_info.height == 400
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
        replacement = Picture(pic_info, PictureType.FISH, "", ())

        with TestOggVorbis.tagger.open(track.filename) as file:
            file.remove_picture(front)
            file.add_picture(replacement, image_data)

        with TestOggVorbis.tagger.open(track.filename) as file:
            scan = file.scan()

        assert set(scan.pictures) == {replacement, back}
