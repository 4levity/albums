import os

import pytest
import xxhash

from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger, BasicTag
from albums.tagger.types import Picture, PictureType
from albums.types import Album, Track

from ..fixtures.create_library import create_library, make_image_data

track = Track(
    "1.aiff",
    {
        BasicTag.ARTIST: ("A",),
        BasicTag.TITLE: ("T",),
        BasicTag.ALBUM: ("baz",),
        BasicTag.ALBUMARTIST: ("baz+foo",),
        BasicTag.TRACKNUMBER: ("1",),
        BasicTag.TRACKTOTAL: ("3",),
        BasicTag.DISCNUMBER: ("2",),
        BasicTag.DISCTOTAL: ("2",),
    },
    0,
    0,
    None,
    [
        Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_FRONT, ""),
        Picture(PictureInfo("image/png", 400, 400, 24, 1, b""), PictureType.COVER_BACK, ""),
    ],
)
album = Album("baz" + os.sep, [track])


class TestAiff:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestAiff.library = create_library("tagger_aiff", [album])
        TestAiff.tagger = AlbumTagger(TestAiff.library / album.path)

    def test_read_write_aiff_tags(self):
        with TestAiff.tagger.open(track.filename) as file:
            scan = file.scan()
        assert len(scan.pictures) == 2
        assert any(pic.description.endswith(" ") for pic in scan.pictures)  # aiff frame hash was made unique by modifying description
        assert scan.pictures[0].type == PictureType.COVER_FRONT or scan.pictures[1].type == PictureType.COVER_FRONT
        assert scan.pictures[0].type == PictureType.COVER_BACK or scan.pictures[1].type == PictureType.COVER_BACK
        assert (
            scan.pictures[0].picture_info.width
            == scan.pictures[0].picture_info.height
            == scan.pictures[1].picture_info.width
            == scan.pictures[1].picture_info.height
            == 400
        )
        assert scan.pictures[0].picture_info.mime_type == scan.pictures[1].picture_info.mime_type == "image/png"
        tags = dict(scan.tags)
        assert tags[BasicTag.ARTIST] == track.tags[BasicTag.ARTIST]
        assert tags[BasicTag.ALBUMARTIST] == track.tags[BasicTag.ALBUMARTIST]
        assert tags[BasicTag.ALBUM] == track.tags[BasicTag.ALBUM]
        assert tags[BasicTag.TITLE] == track.tags[BasicTag.TITLE]

    def test_update_aiff_tags(self):
        TestAiff.tagger.set_basic_tags(
            TestAiff.library / album.path / track.filename,
            [(BasicTag.ARTIST, "a1"), (BasicTag.ALBUMARTIST, "a2"), (BasicTag.ALBUM, "a3"), (BasicTag.TITLE, "t")],
        )
        with TestAiff.tagger.open(track.filename) as file:
            scan = file.scan()
        tags = dict(scan.tags)
        assert tags[BasicTag.ARTIST] == ("a1",)
        assert tags[BasicTag.ALBUMARTIST] == ("a2",)
        assert tags[BasicTag.ALBUM] == ("a3",)
        assert tags[BasicTag.TITLE] == ("t",)

    def test_write_aiff_tracktotal(self):
        with TestAiff.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("3",)

        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKTOTAL, "02")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("02",)

        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKNUMBER, "3")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("3",)
        assert tags[BasicTag.TRACKTOTAL] == ("02",)

        # write both at once
        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKNUMBER, "2")
            file.set_tag(BasicTag.TRACKTOTAL, "3")
        with TestAiff.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("2",)
        assert tags[BasicTag.TRACKTOTAL] == ("3",)

        # remove total
        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKTOTAL, None)
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("2",)
        assert BasicTag.TRACKTOTAL not in tags

    def test_write_aiff_disctotal(self):
        with TestAiff.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("2",)

        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCTOTAL, "1")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("1",)

        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCNUMBER, "1")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("1",)
        assert tags[BasicTag.DISCTOTAL] == ("1",)

        # write both at once
        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCNUMBER, "2")
            file.set_tag(BasicTag.DISCTOTAL, "2")
        with TestAiff.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("2",)

        # remove total
        with TestAiff.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCTOTAL, None)
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert BasicTag.DISCTOTAL not in tags

    def test_remove_one_aiff_pic(self):
        with TestAiff.tagger.open(track.filename) as file:
            scan = file.scan()

        assert len(scan.pictures) == 2
        assert scan.pictures[0].type == PictureType.COVER_FRONT
        assert scan.pictures[1].type == PictureType.COVER_BACK
        assert (
            scan.pictures[0].picture_info.width
            == scan.pictures[0].picture_info.height
            == scan.pictures[1].picture_info.width
            == scan.pictures[1].picture_info.height
            == 400
        )
        assert scan.pictures[0].picture_info.mime_type == scan.pictures[1].picture_info.mime_type == "image/png"

        with TestAiff.tagger.open(track.filename) as file:
            file.remove_picture(scan.pictures[0])
        with TestAiff.tagger.open(track.filename) as file:
            scan = file.scan()

        assert len(scan.pictures) == 1
        assert scan.pictures[0].type == PictureType.COVER_BACK
        assert scan.pictures[0].picture_info.width == scan.pictures[0].picture_info.height == 400
        assert scan.pictures[0].picture_info.mime_type == "image/png"

    def test_replace_one_aiff_pic(self):
        with TestAiff.tagger.open(track.filename) as file:
            scan = file.scan()
        assert len(scan.pictures) == 2
        assert scan.pictures[0].type == PictureType.COVER_FRONT
        front = scan.pictures[0]
        assert scan.pictures[1].type == PictureType.COVER_BACK
        back = scan.pictures[1]

        image_data = make_image_data(600, 600, "JPEG")
        replacement = Picture(PictureInfo("image/jpeg", 600, 600, 24, len(image_data), xxhash.xxh32_digest(image_data)), PictureType.FISH, "")

        with TestAiff.tagger.open(track.filename) as file:
            file.remove_picture(front)
            file.add_picture(replacement, image_data)

        with TestAiff.tagger.open(track.filename) as file:
            scan = file.scan()
        assert set(scan.pictures) == {replacement, back}
