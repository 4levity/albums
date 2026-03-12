import os

import pytest
import xxhash

from albums.database.models import AlbumEntity, TrackEntity, TrackPictureEntity, TrackTagEntity
from albums.picture.info import PictureInfo
from albums.tagger.folder import AlbumTagger, BasicTag
from albums.tagger.types import Picture, PictureType

from ..fixtures.create_library import create_library, make_image_data

track = TrackEntity(
    filename="1.m4a",
    tags=[
        TrackTagEntity(tag=BasicTag.ARTIST, value="A"),
        TrackTagEntity(tag=BasicTag.TITLE, value="T"),
        TrackTagEntity(tag=BasicTag.ALBUM, value="baz"),
        TrackTagEntity(tag=BasicTag.ALBUMARTIST, value="baz+foo"),
        TrackTagEntity(tag=BasicTag.TRACKNUMBER, value="1"),
        TrackTagEntity(tag=BasicTag.TRACKTOTAL, value="3"),
        TrackTagEntity(tag=BasicTag.DISCNUMBER, value="2"),
        TrackTagEntity(tag=BasicTag.DISCTOTAL, value="2"),
    ],
    pictures=[
        TrackPictureEntity(picture_info=PictureInfo("image/png", 400, 400, 24, 1, b"1111"), picture_type=PictureType.COVER_FRONT),
        TrackPictureEntity(
            picture_info=PictureInfo("image/jpeg", 401, 401, 24, 2, b"2222"), picture_type=PictureType.OTHER
        ),  # type ignored, logs a warning
    ],
)
album = AlbumEntity(path="baz" + os.sep, tracks=[track])


class TestM4a:
    @pytest.fixture(scope="function", autouse=True)
    def setup_tests(self):
        TestM4a.library = create_library("tagger_mp3", [album])
        TestM4a.tagger = AlbumTagger(TestM4a.library / album.path)

    def test_read_write_m4a_tags(self):
        with TestM4a.tagger.open(track.filename) as file:
            scan = file.scan()
        assert len(scan.pictures) == 2
        assert scan.pictures[0].type == PictureType.COVER_FRONT
        assert scan.pictures[0].picture_info.mime_type == "image/png"
        assert scan.pictures[0].picture_info.width == scan.pictures[0].picture_info.height == 400
        assert scan.pictures[1].type == PictureType.COVER_FRONT  # always
        assert scan.pictures[1].picture_info.mime_type == "image/jpeg"
        assert scan.pictures[1].picture_info.width == scan.pictures[1].picture_info.height == 401
        tags = dict(scan.tags)
        track_tags = track.tag_dict()
        assert tags[BasicTag.ARTIST] == tuple(track_tags[BasicTag.ARTIST])
        assert tags[BasicTag.ALBUMARTIST] == tuple(track_tags[BasicTag.ALBUMARTIST])
        assert tags[BasicTag.ALBUM] == tuple(track_tags[BasicTag.ALBUM])
        assert tags[BasicTag.TITLE] == tuple(track_tags[BasicTag.TITLE])

    def test_update_m4a_tags(self):
        TestM4a.tagger.set_basic_tags(
            TestM4a.library / album.path / track.filename,
            [(BasicTag.ARTIST, "a1"), (BasicTag.ALBUMARTIST, "a2"), (BasicTag.ALBUM, "a3"), (BasicTag.TITLE, "t")],
        )
        with TestM4a.tagger.open(track.filename) as file:
            scan = file.scan()
        tags = dict(scan.tags)
        assert tags[BasicTag.ARTIST] == ("a1",)
        assert tags[BasicTag.ALBUMARTIST] == ("a2",)
        assert tags[BasicTag.ALBUM] == ("a3",)
        assert tags[BasicTag.TITLE] == ("t",)

    def test_write_id3_tracktotal(self):
        with TestM4a.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("3",)

        with TestM4a.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKTOTAL, "02")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("1",)
        assert tags[BasicTag.TRACKTOTAL] == ("2",)  # tag cannot store leading 0

        with TestM4a.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKNUMBER, "3")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("3",)
        assert tags[BasicTag.TRACKTOTAL] == ("2",)

        # write both at once
        with TestM4a.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKNUMBER, "2")
            file.set_tag(BasicTag.TRACKTOTAL, "3")
        with TestM4a.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("2",)
        assert tags[BasicTag.TRACKTOTAL] == ("3",)

        # remove total
        with TestM4a.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.TRACKTOTAL, None)
            tags = dict(file.scan().tags)
        assert tags[BasicTag.TRACKNUMBER] == ("2",)
        assert BasicTag.TRACKTOTAL not in tags

    def test_write_id3_disctotal(self):
        with TestM4a.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("2",)

        with TestM4a.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCTOTAL, "1")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("1",)

        with TestM4a.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCNUMBER, "1")
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("1",)
        assert tags[BasicTag.DISCTOTAL] == ("1",)

        # write both at once
        with TestM4a.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCNUMBER, "2")
            file.set_tag(BasicTag.DISCTOTAL, "2")
        with TestM4a.tagger.open(track.filename) as file:
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert tags[BasicTag.DISCTOTAL] == ("2",)

        # remove total
        with TestM4a.tagger.open(track.filename) as file:
            file.set_tag(BasicTag.DISCTOTAL, None)
            tags = dict(file.scan().tags)
        assert tags[BasicTag.DISCNUMBER] == ("2",)
        assert BasicTag.DISCTOTAL not in tags

    def test_remove_one_m4a_pic(self):
        with TestM4a.tagger.open(track.filename) as file:
            scan = file.scan()

        assert len(scan.pictures) == 2
        assert scan.pictures[0].picture_info.width == scan.pictures[0].picture_info.height == 400
        assert scan.pictures[0].picture_info.mime_type == "image/png"
        assert scan.pictures[1].picture_info.mime_type == "image/jpeg"

        with TestM4a.tagger.open(track.filename) as file:
            file.remove_picture(scan.pictures[0])
        with TestM4a.tagger.open(track.filename) as file:
            scan = file.scan()

        assert len(scan.pictures) == 1
        assert scan.pictures[0].picture_info.width == scan.pictures[0].picture_info.height == 401
        assert scan.pictures[0].picture_info.mime_type == "image/jpeg"

    def test_replace_one_m4a_pic(self):
        with TestM4a.tagger.open(track.filename) as file:
            scan = file.scan()
        assert len(scan.pictures) == 2
        assert scan.pictures[0].picture_info.mime_type == "image/png"
        first = scan.pictures[0]
        assert scan.pictures[1].picture_info.mime_type == "image/jpeg"
        second = scan.pictures[1]

        image_data = make_image_data(600, 600, "JPEG")
        replacement = Picture(PictureInfo("image/jpeg", 600, 600, 24, len(image_data), xxhash.xxh32_digest(image_data)), PictureType.COVER_FRONT, "")

        with TestM4a.tagger.open(track.filename) as file:
            file.remove_picture(first)
            file.add_picture(replacement, image_data)

        with TestM4a.tagger.open(track.filename) as file:
            scan = file.scan()
        assert set(scan.pictures) == {replacement, second}
